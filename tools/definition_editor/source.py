from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import Path

from webapp.path_safety import resolve_repo_path

from .fragments import expression_fragment
from .models import AuthoringCatalog, Definition, DefinitionDraft, DefinitionEdit, SourceSpan

GENERATED_ROOT = 'modular_aphelion/modules/content_tools/code'
GENERATED = {'outfit': f'{GENERATED_ROOT}/generated_outfits.dm', 'job': f'{GENERATED_ROOT}/generated_jobs.dm', 'id_trim': f'{GENERATED_ROOT}/generated_jobs.dm'}


def decode_source(data: bytes) -> tuple[str, str]:
	try:
		return data.decode('utf-8'), 'utf-8'
	except UnicodeDecodeError:
		return data.decode('latin-1'), 'latin-1'


def field_map(definition: Definition) -> dict[str, str]:
	return {field.name: field.expression for field in definition.fields if field.expression is not None}


def modular_owners(definition: Definition) -> dict[str, SourceSpan]:
	spans = [definition.source, *definition.occurrences]
	spans.extend(field.source for field in definition.fields if field.owner_type == definition.type_path)
	spans.extend(proc.source for proc in definition.procedures if proc.owner_type == definition.type_path)
	return {span.path: span for span in spans if span and span.path.startswith(('modular_nova/', 'modular_aphelion/')) and span.path not in GENERATED.values()}


def retired_flags(flags: str) -> str:
	suffix = ') & ~JOB_NEW_PLAYER_JOINABLE'
	if flags.startswith('(') and flags.endswith(suffix):
		try:
			expression_fragment(flags[1:-len(suffix)])
			return flags
		except ValueError:
			pass
	return f'({flags}) & ~JOB_NEW_PLAYER_JOINABLE'


def render_edit(edit: DefinitionEdit) -> str:
	lines = [edit.type_path]
	if edit.parent_type:
		lines.append(f'\tparent_type = {edit.parent_type}')
	for name, expression in edit.fields.items():
		lines.append(f'\t{name} = {expression}')
	lines.append('')
	for name, text in edit.procedures.items():
		prefixes = (f'{edit.type_path}/{name}(', f'{edit.type_path}/proc/{name}(')
		if not text.lstrip().startswith(prefixes):
			raise ValueError(f'Procedure {name} must use its complete header on {edit.type_path}.')
		lines.extend((text.rstrip(), ''))
	return '\n'.join(lines) + '\n'


def build_changes(root: Path, catalog: AuthoringCatalog, draft: DefinitionDraft) -> dict[str, tuple[bytes | None, bytes]]:
	definitions = {item.type_path: item for item in catalog.definitions}
	patches: dict[str, list[tuple[int, int, bytes]]] = defaultdict(list)
	appends: dict[str, list[str]] = defaultdict(list)
	originals: dict[str, bytes | None] = {}
	new_types: set[str] = set()
	begin = f'// BEGIN CONTENT TOOLS {draft.id}'
	end_marker = f'// END CONTENT TOOLS {draft.id}'

	def original(path: str, sha: str | None = None) -> bytes:
		if path not in originals:
			resolved = resolve_repo_path(root, Path(path))
			if resolved.relative_to(root.resolve()).as_posix() != path or '.git' in Path(path).parts:
				raise ValueError('Noncanonical source path.')
			originals[path] = resolved.read_bytes() if resolved.is_file() else None
		data = originals[path]
		if sha and (data is None or hashlib.sha256(data).hexdigest() != sha):
			raise ValueError('Game source changed since indexing; refresh the stale catalog.')
		return data or b''

	def owned_block(path: str) -> tuple[int, int] | None:
		data = original(path)
		starts = list(re.finditer(rb'(?m)^' + re.escape(begin.encode()) + rb'\r?$', data))
		ends = list(re.finditer(rb'(?m)^' + re.escape(end_marker.encode()) + rb'\r?$', data))
		if len(starts) != len(ends) or len(starts) > 1:
			raise ValueError('Generated record markers are damaged or duplicated; inspect the source.')
		if not starts:
			return None
		start, end = starts[0].start(), ends[0].start() + len(end_marker.encode())
		if end < start:
			raise ValueError('Invalid generated record boundaries.')
		return start, end

	def owns(edit: DefinitionEdit) -> bool:
		path = GENERATED[edit.kind]
		existing = definitions.get(edit.type_path)
		if existing is None:
			return False
		spans = [span for span in [existing.source, *existing.occurrences] if span and span.path == path]
		if not spans:
			return False
		block = owned_block(path)
		if block is None:
			return False
		for span in spans:
			data = original(path, span.sha256)
			line_start = data.rfind(b'\n', 0, span.start) + 1
			line_end = data.find(b'\n', span.end)
			tail = data[span.end:line_end if line_end >= 0 else len(data)].strip()
			if block[0] <= span.start < span.end <= block[1] and data[span.start:span.end] == edit.type_path.encode('ascii') and not data[line_start:span.start].strip() and (not tail or tail.startswith(b'//')):
				return True
		return False

	def patch(span: SourceSpan, text: str) -> None:
		data = original(span.path, span.sha256)
		if span.end > len(data):
			raise ValueError('Source range exceeds the indexed file.')
		_, encoding = decode_source(data)
		newline = '\r\n' if b'\r\n' in data else '\n'
		text = text.replace('\r\n', '\n').replace('\n', newline)
		patches[span.path].append((span.start, span.end, text.encode(encoding)))

	def update(edit: DefinitionEdit, base: Definition) -> None:
		owners = modular_owners(base)
		if not owners:
			raise ValueError('Update requires an owning modular definition; use Override for TG source.')
		if any(span and span.path in GENERATED.values() for span in [base.source, *(field.source for field in base.fields if field.owner_type == base.type_path), *(proc.source for proc in base.procedures if proc.owner_type == base.type_path)]):
			raise ValueError('Open the owning saved draft to update generated definitions.')
		if edit.target_file is not None and edit.target_file not in owners:
			raise ValueError('The selected destination is not an owning modular source file.')
		fields = {field.name: field for field in base.fields}
		procs = {proc.name: proc for proc in base.procedures}
		extra = edit.model_copy(update={'fields': {}, 'procedures': {}, 'parent_type': None})
		for name, expression in edit.fields.items():
			field = fields.get(name)
			if field is None:
				raise ValueError(f'Unknown field {name}; fields must exist in the selected type hierarchy.')
			if field.owner_type == base.type_path and field.source:
				if not field.editable:
					raise ValueError(f'Field {name} is not editable: its source is ambiguous or generated by a macro.')
				if not field.source.path.startswith(('modular_nova/', 'modular_aphelion/')):
					extra.fields[name] = expression
				else:
					patch(field.source, expression)
			else:
				extra.fields[name] = expression
		for name, text in edit.procedures.items():
			render_edit(edit.model_copy(update={'fields': {}, 'procedures': {name: text}}))
			proc = procs.get(name)
			if proc and proc.owner_type == base.type_path and proc.source:
				if not proc.editable:
					raise ValueError(f'Procedure {name} has no unambiguous editable source range.')
				if proc.source.path.startswith(('modular_nova/', 'modular_aphelion/')):
					patch(proc.source, text)
				else:
					extra.procedures[name] = text
			else:
				extra.procedures[name] = text
		if extra.fields or extra.procedures:
			if not edit.target_file and len(owners) != 1:
				raise ValueError('Choose the owning modular file for newly overridden fields or procedures.')
			owner = owners[edit.target_file] if edit.target_file else next(iter(owners.values()))
			original(owner.path, owner.sha256)
			appends[owner.path].append(render_edit(extra))

	for edit in draft.edits:
		base = definitions.get(edit.source_type or edit.type_path)
		if edit.operation in ('create', 'replace'):
			if edit.type_path in new_types or edit.type_path in definitions and not owns(edit):
				raise ValueError(f'Type {edit.type_path} already exists.')
			new_types.add(edit.type_path)
			if not edit.parent_type or edit.parent_type not in definitions and edit.parent_type not in new_types:
				raise ValueError('New definitions require a known parent type.')
		else:
			if base is None or base.type_path != edit.type_path or base.kind != edit.kind:
				raise ValueError('The selected definition does not match the edit identity.')
		if edit.operation == 'update':
			assert base is not None
			update(edit, base)
		else:
			# A replacement inheriting from the old job must keep its original flags
			# when retirement changes the parent's joinability in the same change set.
			if edit.operation == 'replace' and edit.kind == 'job' and edit.old_job_selection == 'retire' and edit.parent_type == edit.source_type:
				flags = edit.fields.get('job_flags', field_map(base).get('job_flags') if base else None)
				if not flags:
					raise ValueError('Replacement requires resolved selection flags or an explicit job_flags value.')
				# Canonical save sorts field keys. Keep preserved flags in the same
				# position before and after application reconciliation persists them.
				fields = {name: value for name, value in edit.fields.items() if name != 'job_flags'}
				edit = edit.model_copy(update={'fields': {**fields, 'job_flags': flags}})
			appends[GENERATED[edit.kind]].append(render_edit(edit))
		if edit.operation == 'replace':
			if base is None or base.kind != edit.kind:
				raise ValueError('Replacement source definition is missing or incompatible.')
			refs = {ref.id: ref for definition in catalog.definitions for ref in definition.references}
			for ref_id in edit.reference_ids:
				ref = refs.get(ref_id)
				if not ref or not ref.editable or ref.target_type != base.type_path:
					raise ValueError('Selected reference is missing, ambiguous, or not safely editable.')
				data = original(ref.source.path, ref.source.sha256)
				if data[ref.source.start:ref.source.end].decode('ascii') != base.type_path:
					raise ValueError('Reference no longer identifies an exact physical type-path token.')
				patch(ref.source, edit.type_path)
			if edit.kind == 'job' and edit.old_job_selection == 'retire':
				flags = field_map(base).get('job_flags')
				if not flags:
					raise ValueError('Cannot safely retire a job with unresolved selection flags.')
				retire = DefinitionEdit(kind='job', operation='override', type_path=base.type_path, fields={'job_flags': retired_flags(flags)})
				if modular_owners(base):
					retire.target_file = edit.target_file
					update(retire, base)
				else:
					appends[GENERATED['job']].append(render_edit(retire))

	for path in appends:
		original(path)
		if path in GENERATED.values():
			block = owned_block(path)
			text = begin + '\n' + '\n'.join(appends[path]) + end_marker
			if block:
				data = original(path)
				_, encoding = decode_source(data)
				newline = '\r\n' if b'\r\n' in data else '\n'
				patches[path].append((*block, text.replace('\n', newline).encode(encoding)))
				appends[path] = []
			else:
				appends[path] = [text + '\n']
	changes: dict[str, tuple[bytes | None, bytes]] = {}
	for path in sorted(set(patches) | set(appends)):
		data = original(path)
		ordered = sorted(patches[path])
		if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:], strict=False)):
			raise ValueError('Draft edits overlap the same physical source; resolve them before validation.')
		for start, end, replacement in reversed(ordered):
			data = data[:start] + replacement + data[end:]
		if appends[path]:
			_, encoding = decode_source(data)
			newline = '\r\n' if b'\r\n' in data else '\n'
			text = '\n'.join(appends[path]).replace('\r\n', '\n').replace('\n', newline)
			data = data.rstrip(b'\r\n') + newline.encode() * 2 + text.encode(encoding)
		if data != originals[path]:
			changes[path] = originals[path], data
	return changes

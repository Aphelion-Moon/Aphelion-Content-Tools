from __future__ import annotations

from collections import defaultdict

from .models import AuthoringCatalog, Definition


def values(definition: Definition) -> dict[str, object]:
	return {field.name: field.value for field in definition.fields}


def _registrations(catalog: AuthoringCatalog) -> dict[tuple[str, str], set[str]]:
	result: dict[tuple[str, str], set[str]] = defaultdict(set)
	for definition in catalog.definitions:
		if definition.kind != 'job' or definition.type_path == '/datum/job':
			continue
		fields = values(definition)
		for field in ('title', 'config_tag'):
			value = fields.get(field)
			if isinstance(value, str) and value:
				result[field, value].add(definition.type_path)
		for field in ('alternate_titles', 'alt_titles'):
			aliases = fields.get(field)
			if isinstance(aliases, dict):
				entries = aliases.get('entries')
				aliases = [entry.get('key') for entry in entries if isinstance(entry, dict)] if isinstance(entries, list) else []
			if isinstance(aliases, list):
				for alias in aliases:
					if isinstance(alias, str):
						result['title', alias].add(definition.type_path)
	return result


def validate_candidate(base: AuthoringCatalog, candidate: AuthoringCatalog, edited: set[str]) -> list[str]:
	old = _registrations(base)
	for (kind, value), owners in _registrations(candidate).items():
		if len(owners) > 1 and (owners & edited or owners != old.get((kind, value), set())):
			raise ValueError(f'Job {kind}/alias {value!r} collides across registered jobs: {", ".join(sorted(owners))}. Retiring selection does not remove registration.')
	definitions = {item.type_path: item for item in candidate.definitions}
	for type_path in edited:
		definition = definitions.get(type_path)
		if not definition:
			raise ValueError(f'Candidate did not define {type_path}.')
		fields = values(definition)
		joinable = next((item.value for item in candidate.constants if item.name == 'JOB_NEW_PLAYER_JOINABLE' and item.value_known), None)
		flags = fields.get('job_flags')
		if definition.kind == 'job' and isinstance(joinable, int) and isinstance(flags, int) and flags & joinable:
			for field in ('title', 'config_tag'):
				if not isinstance(fields.get(field), str) or not fields[field]:
					raise ValueError(f'Selectable station job {type_path} requires a resolved {field}.')
			if not fields.get('outfit'):
				raise ValueError(f'Selectable station job {type_path} requires an outfit.')
		for field in ('outfit', 'plasmaman_outfit', 'vox_outfit', 'akula_outfit', 'id_trim', 'job', 'jobtype'):
			value = fields.get(field)
			if isinstance(value, str) and value.startswith('/') and value not in definitions:
				raise ValueError(f'{type_path}.{field} references missing type {value}.')
	return list(candidate.diagnostics)

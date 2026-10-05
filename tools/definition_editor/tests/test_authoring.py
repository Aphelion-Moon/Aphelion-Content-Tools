from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.definition_editor.models import AuthoringCatalog, DefinitionDraft
from tools.definition_editor.source import build_changes
from tools.definition_editor.storage import DraftStore
from tools.lore_editor.write_coordinator import RecordConflict

SOURCE = b'// untouched\r\n/datum/outfit/example\r\n\tname = "Original" // keep\r\n\tback = /obj/item/storage/backpack\r\n'
FILE = 'modular_nova/modules/example/outfit.dm'


def catalog() -> AuthoringCatalog:
	start = SOURCE.index(b'"Original"')
	sha = hashlib.sha256(SOURCE).hexdigest()
	return AuthoringCatalog.model_validate({'schema_version': 1, 'analyzer_version': 'fixture', 'input_files': [{'path': FILE, 'sha256': sha}], 'definitions': [
		{'type_path': '/datum/outfit', 'kind': 'outfit', 'parent_type': '/datum'},
		{'type_path': '/datum/outfit/example', 'kind': 'outfit', 'parent_type': '/datum/outfit', 'source': {'path': FILE, 'start': 14, 'end': 35, 'sha256': sha}, 'fields': [
			{'name': 'name', 'expression': '"Original"', 'value': 'Original', 'owner_type': '/datum/outfit/example', 'editable': True, 'source': {'path': FILE, 'start': start, 'end': start + 10, 'sha256': sha}}
		]}
	]})


def draft(operation: str = 'update') -> DefinitionDraft:
	return DefinitionDraft.model_validate({'id': 'test-outfit', 'kind': 'outfit', 'catalog_id': 'fixture', 'edits': [{'kind': 'outfit', 'operation': operation, 'source_type': '/datum/outfit/example', 'type_path': '/datum/outfit/example', 'fields': {'name': '"Updated"'}}]})


class DefinitionAuthoringTests(unittest.TestCase):
	def test_replacement_migrates_only_selected_verified_reference(self) -> None:
		from tools.definition_editor.models import DefinitionReference, SourceSpan
		data = catalog()
		path = 'modular_aphelion/modules/example/consumer.dm'
		content = b'// preserved\r\nvar/first = /datum/outfit/example\r\nvar/second = /datum/outfit/example\r\n'
		start = content.index(b'/datum/outfit/example')
		data.definitions[1].references = [DefinitionReference(id='selected', target_type='/datum/outfit/example', source=SourceSpan(path=path, start=start, end=start + len('/datum/outfit/example'), sha256=hashlib.sha256(content).hexdigest()), editable=True)]
		record = draft('replace')
		record.edits[0].type_path = '/datum/outfit/replacement'
		record.edits[0].parent_type = '/datum/outfit/example'
		record.edits[0].reference_ids = ['selected']
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			(root / path).parent.mkdir(parents=True)
			(root / path).write_bytes(content)
			changes = build_changes(root, data, record)
			self.assertEqual(changes[path][1], content.replace(b'/datum/outfit/example', b'/datum/outfit/replacement', 1))

	def test_replacement_with_retained_selection_does_not_emit_retirement(self) -> None:
		from tools.definition_editor.models import Definition, DefinitionEdit
		from tools.definition_editor.source import GENERATED
		data = catalog()
		data.definitions.append(Definition(type_path='/datum/job/old', kind='job'))
		record = DefinitionDraft(id='replacement', kind='job', catalog_id='fixture', edits=[DefinitionEdit(kind='job', operation='replace', source_type='/datum/job/old', type_path='/datum/job/new', parent_type='/datum/job/old', old_job_selection='retain')])
		with tempfile.TemporaryDirectory() as temporary:
			output = build_changes(Path(temporary), data, record)[GENERATED['job']][1]
			self.assertNotIn(b'~JOB_NEW_PLAYER_JOINABLE', output)

	def test_retirement_mask_is_stable_across_repeated_application(self) -> None:
		from tools.definition_editor.source import retired_flags
		flags = '(JOB_NEW_PLAYER_JOINABLE | JOB_EQUIP_RANK)'
		first = retired_flags(flags)
		self.assertEqual(retired_flags(first), first)

	def test_appending_an_inherited_override_requires_an_explicit_owner_if_ambiguous(self) -> None:
		from tools.definition_editor.models import SourceSpan
		data = catalog()
		definition = data.definitions[1]
		definition.fields[0].owner_type = '/datum/outfit'
		other = 'modular_aphelion/modules/example/outfit.dm'
		definition.occurrences.append(SourceSpan(path=other, start=0, end=1, sha256=hashlib.sha256(SOURCE).hexdigest()))
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			for path in (FILE, other):
				(root / path).parent.mkdir(parents=True)
				(root / path).write_bytes(SOURCE)
			with self.assertRaisesRegex(ValueError, 'Choose the owning'):
				build_changes(root, data, draft())
			record = draft()
			record.edits[0].target_file = other
			self.assertEqual(set(build_changes(root, data, record)), {other})

	def test_modular_reopening_can_be_updated_without_touching_tg_origin(self) -> None:
		from tools.definition_editor.models import SourceSpan
		data = catalog()
		definition = data.definitions[1]
		assert definition.source
		definition.occurrences = [definition.source]
		definition.source = SourceSpan(path='code/original.dm', start=0, end=1, sha256='0' * 64)
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			(root / FILE).parent.mkdir(parents=True)
			(root / FILE).write_bytes(SOURCE)
			self.assertEqual(set(build_changes(root, data, draft())), {FILE})
	def test_fragments_cannot_smuggle_unrelated_top_level_declarations(self) -> None:
		from tools.definition_editor.models import DefinitionEdit
		for values in (
			{'fields': {'name': '"Selected"\n/world\n\tname = "Unexpected"'}},
			{'fields': {'name': '"Selected"\n\tback = /obj/item'}},
			{'procedures': {'pre_equip': '/datum/outfit/example/pre_equip(mob/living/carbon/human/H)\n\treturn\n/world/New()\n\treturn'}},
		):
			with self.subTest(values=values), self.assertRaises(ValueError):
				DefinitionEdit(kind='outfit', operation='override', type_path='/datum/outfit/example', **values)

	def test_multiline_expression_retains_comments_and_nested_lists(self) -> None:
		from tools.definition_editor.models import DefinitionEdit
		value = 'list(\n\t/obj/item = 2, // note\n\t/obj/item/test = 1\n)'
		edit = DefinitionEdit(kind='outfit', operation='override', type_path='/datum/outfit/example', fields={'backpack_contents': value})
		self.assertEqual(edit.fields['backpack_contents'], value)
	def test_retiring_parent_does_not_retire_replacement_job(self) -> None:
		from tools.definition_editor.models import Definition, DefinitionEdit, DefinitionField
		from tools.definition_editor.source import GENERATED
		data = catalog()
		data.definitions.append(Definition(type_path='/datum/job/old', kind='job', fields=[DefinitionField(name='job_flags', expression='JOB_NEW_PLAYER_JOINABLE | JOB_EQUIP_RANK', owner_type='/datum/job/old')]))
		record = DefinitionDraft(id='replacement', kind='job', catalog_id='fixture', edits=[DefinitionEdit(kind='job', operation='replace', source_type='/datum/job/old', type_path='/datum/job/new', parent_type='/datum/job/old', old_job_selection='retire')])
		with tempfile.TemporaryDirectory() as temporary:
			output = build_changes(Path(temporary), data, record)[GENERATED['job']][1]
			new_definition = output.split(b'/datum/job/new\n')[1].split(b'\n\n')[0]
			self.assertIn(b'job_flags = JOB_NEW_PLAYER_JOINABLE | JOB_EQUIP_RANK', new_definition)
			self.assertIn(b'& ~JOB_NEW_PLAYER_JOINABLE', output)
	def test_reconciled_retiring_replacement_is_byte_identical_after_save(self) -> None:
		from tools.definition_editor.models import Definition, DefinitionEdit, DefinitionField, SourceSpan
		from tools.definition_editor.source import GENERATED, retired_flags
		flags = 'JOB_NEW_PLAYER_JOINABLE | JOB_EQUIP_RANK'
		data = catalog()
		old = Definition(type_path='/datum/job/old', kind='job', fields=[DefinitionField(name='job_flags', expression=flags, owner_type='/datum/job/old')])
		data.definitions.append(old)
		record = DefinitionDraft(id='replacement', kind='job', catalog_id='fixture', edits=[DefinitionEdit(kind='job', operation='replace', source_type=old.type_path, type_path='/datum/job/new', parent_type=old.type_path, old_job_selection='retire', fields={'title': '"New Job"', 'alt_titles': 'list()', 'config_tag': '"new_job"'})])
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			store = DraftStore(root)
			saved = store.save(record, expected_hash=None)
			record = store.get('job', record.id).draft
			path = GENERATED['job']
			first = build_changes(root, data, record)[path][1]
			(root / path).parent.mkdir(parents=True)
			(root / path).write_bytes(first)
			start = first.index(record.edits[0].type_path.encode())
			data.definitions.append(Definition(type_path=record.edits[0].type_path, kind='job', parent_type=old.type_path, occurrences=[SourceSpan(path=path, start=start, end=start + len(record.edits[0].type_path), sha256=hashlib.sha256(first).hexdigest())]))
			old.fields[0].expression = retired_flags(flags)
			# Application reconciliation persists the replacement's original flags.
			record.edits[0].fields['job_flags'] = flags
			store.save(record, expected_hash=saved.record_hash)
			reconciled = store.get('job', record.id).draft
			self.assertEqual(build_changes(root, data, reconciled), {})

	def test_generated_record_is_regenerated_without_duplicate_definitions(self) -> None:
		from tools.definition_editor.models import Definition, SourceSpan
		from tools.definition_editor.source import GENERATED
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			data = catalog()
			record = draft('create')
			record.edits[0].type_path = '/datum/outfit/new_outfit'
			record.edits[0].parent_type = '/datum/outfit'
			path = GENERATED['outfit']
			first = build_changes(root, data, record)[path][1]
			(root / path).parent.mkdir(parents=True)
			(root / path).write_bytes(first)
			data.definitions.append(Definition(type_path=record.edits[0].type_path, kind='outfit', parent_type='/datum/outfit', occurrences=[SourceSpan(path=path, start=first.index(record.edits[0].type_path.encode()), end=first.index(record.edits[0].type_path.encode()) + len(record.edits[0].type_path), sha256=hashlib.sha256(first).hexdigest())]))
			record.edits[0].fields['name'] = '"Again"'
			second = build_changes(root, data, record)[path][1]
			self.assertEqual(second.count(b'/datum/outfit/new_outfit'), 1)
			self.assertIn(b'"Again"', second)
			self.assertNotIn(b'"Updated"', second)

	def test_generated_output_cannot_be_adopted_by_an_unrelated_record(self) -> None:
		from tools.definition_editor.models import Definition, SourceSpan
		from tools.definition_editor.source import GENERATED
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			data = catalog()
			record = draft('create')
			record.edits[0].type_path = '/datum/outfit/new_outfit'
			record.edits[0].parent_type = '/datum/outfit'
			path = GENERATED['outfit']
			first = build_changes(root, data, record)[path][1]
			(root / path).parent.mkdir(parents=True)
			(root / path).write_bytes(first)
			data.definitions.append(Definition(type_path=record.edits[0].type_path, kind='outfit', occurrences=[SourceSpan(path=path, start=first.index(record.edits[0].type_path.encode()), end=first.index(record.edits[0].type_path.encode()) + len(record.edits[0].type_path), sha256=hashlib.sha256(first).hexdigest())]))
			record.id = 'test'  # A prefix of test-outfit must not match its marker lines.
			with self.assertRaisesRegex(ValueError, 'already exists'):
				build_changes(root, data, record)
	def test_modular_patch_changes_only_expression_preserving_comments_and_crlf(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			(root / FILE).parent.mkdir(parents=True)
			(root / FILE).write_bytes(SOURCE)
			changes = build_changes(root, catalog(), draft())
			self.assertEqual(changes[FILE], (SOURCE, SOURCE.replace(b'"Original"', b'"Updated"')))

	def test_source_drift_refuses_patch(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			(root / FILE).parent.mkdir(parents=True)
			(root / FILE).write_bytes(SOURCE + b'// external')
			with self.assertRaisesRegex(ValueError, 'changed|stale'):
				build_changes(root, catalog(), draft())

	def test_create_rejects_existing_identity(self) -> None:
		with tempfile.TemporaryDirectory() as temporary, self.assertRaisesRegex(ValueError, 'already exists'):
			build_changes(Path(temporary), catalog(), draft('create'))

	def test_macro_or_ambiguous_source_cannot_be_patched(self) -> None:
		data = catalog()
		data.definitions[1].fields[0].editable = False
		with tempfile.TemporaryDirectory() as temporary, self.assertRaisesRegex(ValueError, 'editable|ambiguous'):
			build_changes(Path(temporary), data, draft())

	def test_canonical_draft_save_detects_concurrent_edit(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			store = DraftStore(Path(temporary))
			first = store.save(draft(), expected_hash=None)
			changed = draft()
			changed.edits[0].fields['name'] = '"Second"'
			store.save(changed, expected_hash=first.record_hash)
			with self.assertRaises(RecordConflict):
				store.save(draft(), expected_hash=first.record_hash)
			self.assertEqual(store.get('outfit', 'test-outfit').draft.edits[0].fields['name'], '"Second"')

	def test_source_inspection_uses_a_qualified_declaration_when_semantic_location_is_absent(self) -> None:
		from tools.definition_editor.inspection import source_excerpt
		from tools.definition_editor.models import SourceSpan
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			(root / FILE).parent.mkdir(parents=True)
			(root / FILE).write_bytes(SOURCE)
			definition = catalog().definitions[1].model_copy(update={'source': None})
			definition.occurrences = [SourceSpan(path=FILE, start=14, end=35, sha256=hashlib.sha256(SOURCE).hexdigest())]
			result = source_excerpt(root, definition, 'fixture', None)
			self.assertIn('/datum/outfit/example', result.text)
			self.assertEqual(result.path, FILE)

	def test_generated_reference_token_cannot_claim_an_existing_definition(self) -> None:
		from tools.definition_editor.models import Definition, SourceSpan
		from tools.definition_editor.source import GENERATED
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			data = catalog()
			record = draft('create')
			record.edits[0].type_path = '/datum/outfit/external'
			record.edits[0].parent_type = '/datum/outfit'
			content = b'// BEGIN CONTENT TOOLS test-outfit\n/datum/outfit/other\n\tparent_type = /datum/outfit/external\n// END CONTENT TOOLS test-outfit\n'
			path = GENERATED['outfit']
			(root / path).parent.mkdir(parents=True)
			(root / path).write_bytes(content)
			start = content.index(b'/datum/outfit/external')
			data.definitions.append(Definition(type_path=record.edits[0].type_path, kind='outfit', occurrences=[SourceSpan(path=path, start=start, end=start+len(record.edits[0].type_path), sha256=hashlib.sha256(content).hexdigest())]))
			with self.assertRaisesRegex(ValueError, 'already exists'):
				build_changes(root, data, record)

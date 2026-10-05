from __future__ import annotations

import unittest

from tools.definition_editor.models import Definition
from tools.definition_editor.query import query_definitions
from tools.definition_editor.tests.test_authoring import catalog


class DefinitionQueryTests(unittest.TestCase):
	def test_special_roles_do_not_inherit_station_selection_classification(self) -> None:
		from tools.definition_editor.models import DefinitionConstant, DefinitionField
		from tools.definition_editor.query import classified
		data = catalog()
		data.constants = [DefinitionConstant(name='JOB_CREW_MEMBER', value=8, value_known=True), DefinitionConstant(name='JOB_NEW_PLAYER_JOINABLE', value=16, value_known=True)]
		role = Definition(type_path='/datum/job/ghost_role', kind='job', fields=[DefinitionField(name='job_flags', value=0, value_known=True, owner_type='/datum/job/ghost_role')])
		self.assertEqual(classified(role, data).job_category, 'special')
		self.assertFalse(classified(role, data).player_selectable)
		role.fields[0].value = 8
		self.assertEqual(classified(role, data).job_category, 'station')
		self.assertFalse(classified(role, data).player_selectable)

	def test_shared_search_returns_source_bound_definitions_and_saved_drafts(self) -> None:
		import tempfile
		from pathlib import Path
		from unittest.mock import Mock

		from tools.definition_editor.storage import DraftStore
		from tools.definition_editor.tests.test_authoring import draft
		from webapp.application_search import search_application
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			DraftStore(root).save(draft(), expected_hash=None)
			store = Mock()
			store.read.return_value = ('snapshot-bound', catalog(), 'revision')
			report = search_application(root, store, 'outfit', tables=['outfit_definitions'], limit=20, context=None)
			definition = next(row for row in report.results if row['id'] == '/datum/outfit/example')
			self.assertEqual(definition['navigation']['catalog_id'], 'snapshot-bound')
			self.assertTrue(any(row['navigation']['record_kind'] == 'definition_draft' for row in report.results))
			self.assertEqual(report.semantic_mode, 'keyword-only')

	def test_subtype_picker_follows_explicit_parent_not_lexical_prefix(self) -> None:
		data = catalog()
		data.definitions.extend([
			Definition(type_path='/datum/outfit/unrelated', kind='outfit', parent_type='/datum'),
			Definition(type_path='/custom/outfit', kind='outfit', parent_type='/datum/outfit'),
		])
		paths = [item.type_path for item in query_definitions(data, 'outfit', subtype_of='/datum/outfit')]
		self.assertIn('/custom/outfit', paths)
		self.assertNotIn('/datum/outfit/unrelated', paths)

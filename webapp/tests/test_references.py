from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.lore_editor.write_coordinator import repository_write_lock
from webapp.references import add_reference, list_references, remove_reference
from webapp.store.lifecycle import read_projection


class ReferencesTests(unittest.TestCase):
	def test_definition_reference_requires_and_retains_catalog_provenance(self) -> None:
		payload = {'tool': 'outfit-editor', 'kind': 'definition', 'key': '/datum/outfit/test', 'label': 'Test'}
		with self.assertRaisesRegex(ValueError, 'provenance'):
			add_reference(self.repo_root, payload)
		created = add_reference(self.repo_root, {**payload, 'catalog_id': 'catalog-bound'})
		self.assertEqual(created['catalog_id'], 'catalog-bound')
		self.assertEqual(list_references(self.repo_root)[0]['catalog_id'], 'catalog-bound')

	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp_dir.cleanup)
		self.repo_root = Path(self.temp_dir.name)

	def test_add_list_and_remove_a_reference(self) -> None:
		created = add_reference(self.repo_root, {
			"tool": "lore-editor",
			"kind": "catalog_target",
			"key": "/obj/item/radio",
			"label": "Radio",
		})
		self.assertEqual(created["tool"], "lore-editor")
		self.assertTrue(created["id"])

		references = list_references(self.repo_root)
		self.assertEqual([reference["id"] for reference in references], [created["id"]])

		remove_reference(self.repo_root, created["id"])
		self.assertEqual(list_references(self.repo_root), [])

	def test_reference_mutations_use_the_repository_write_lock(self) -> None:
		with patch("webapp.references.repository_write_lock", wraps=repository_write_lock) as lock_spy:
			created = add_reference(self.repo_root, {
				"tool": "graph",
				"kind": "graph_node",
				"key": "module:aphelion:fixture",
				"label": "Fixture",
			})
			remove_reference(self.repo_root, created["id"])

		self.assertEqual(lock_spy.call_count, 2)

	def test_add_reference_rejects_an_unknown_tool(self) -> None:
		with self.assertRaises(ValueError):
			add_reference(self.repo_root, {
				"tool": "not-a-real-tool",
				"kind": "file",
				"key": "some/path.dm",
				"label": "path.dm",
			})

	def test_add_reference_rejects_an_unknown_kind(self) -> None:
		with self.assertRaises(ValueError):
			add_reference(self.repo_root, {
				"tool": "graph",
				"kind": "not-a-real-kind",
				"key": "module:aphelion:x",
				"label": "x",
			})

	def test_add_reference_requires_a_label_and_key(self) -> None:
		with self.assertRaises(ValueError):
			add_reference(self.repo_root, {"tool": "graph", "kind": "graph_node", "key": ""})

	def test_remove_reference_rejects_an_unknown_id(self) -> None:
		with self.assertRaises(ValueError):
			remove_reference(self.repo_root, "does-not-exist")

	def test_list_references_orders_by_creation_time(self) -> None:
		first = add_reference(self.repo_root, {"tool": "file-management", "kind": "file", "key": "a.dm", "label": "a.dm"})
		second = add_reference(self.repo_root, {"tool": "file-management", "kind": "file", "key": "b.dm", "label": "b.dm"})

		references = list_references(self.repo_root)

		self.assertEqual([reference["id"] for reference in references], [first["id"], second["id"]])

	def test_reference_change_does_not_mutate_an_existing_read_snapshot(self) -> None:
		created = add_reference(self.repo_root, {"tool": "file-management", "kind": "file", "key": "a.dm", "label": "a.dm"})
		with read_projection(self.repo_root):
			remove_reference(self.repo_root, created["id"])
			self.assertEqual([reference["id"] for reference in list_references(self.repo_root)], [created["id"]])
		self.assertEqual(list_references(self.repo_root), [])


if __name__ == "__main__":
	unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.lore_editor.source import load_corpus
from tools.lore_editor.tests.store_helpers import seed_override, seed_targets
from webapp.store.schema import encode


class LoadCorpusTests(unittest.TestCase):
	def make_repo(self) -> tempfile.TemporaryDirectory[str]:
		return tempfile.TemporaryDirectory()

	def test_load_corpus_pins_legacy_table_reads_to_one_store(self) -> None:
		with self.make_repo() as temp_dir:
			repo_root = Path(temp_dir)
			pinned_store = repo_root / "webapp" / "store" / "projections" / "pinned"
			store_dirs = []
			catalog_row = {"id": "/obj/item/radio", "raw_json": encode({"type_path": "/obj/item/radio", "label": "Radio"})}
			override_row = {"id": "items.radio", "group": "items", "raw_json": encode({"id": "items.radio", "type_path": "/obj/item/radio"})}

			class FakeTable:
				pass

			def fake_table(_repo_root, _name, *, store_dir=None):
				store_dirs.append(store_dir)
				return FakeTable()

			with (
				patch("tools.lore_editor.source.db.store_path", return_value=pinned_store),
				patch("tools.lore_editor.source.table", side_effect=fake_table),
				patch("tools.lore_editor.source.db.all_rows", side_effect=[[catalog_row], [override_row]]),
			):
				corpus = load_corpus(repo_root)

			self.assertEqual(len(corpus.targets), 1)
			self.assertEqual(len(corpus.entries), 1)
			self.assertEqual(store_dirs, [pinned_store, pinned_store])

	def test_load_corpus_orders_entries_by_relative_source_path(self) -> None:
		with self.make_repo() as temp_dir:
			repo_root = Path(temp_dir)
			seed_targets(repo_root, [])
			seed_override(repo_root, "zeta-second", {"id": "zeta.second", "type_path": "/obj/item/b"})
			seed_override(repo_root, "alpha-first", {"id": "alpha.first", "type_path": "/obj/item/a"})
			seed_override(repo_root, "alpha-first", {"id": "alpha.third", "type_path": "/obj/item/c"})

			corpus = load_corpus(repo_root)

			self.assertEqual(
				sorted(entry.entry_id for entry in corpus.entries),
				["alpha.first", "alpha.third", "zeta.second"],
			)
			source_paths_by_id = {entry.entry_id: str(entry.source_path).replace("\\", "/") for entry in corpus.entries}
			self.assertEqual(source_paths_by_id["alpha.first"], "tools/lore_editor/content/overrides/alpha-first.json")
			self.assertEqual(source_paths_by_id["alpha.third"], "tools/lore_editor/content/overrides/alpha-first.json")
			self.assertEqual(source_paths_by_id["zeta.second"], "tools/lore_editor/content/overrides/zeta-second.json")

	def test_load_corpus_keeps_target_catalog_for_an_override_free_repo(self) -> None:
		with self.make_repo() as temp_dir:
			repo_root = Path(temp_dir)
			seed_targets(repo_root, [
				{
					"type_path": "/obj/item/radio",
					"label": "radio",
					"editable_root": "/obj/item",
					"parent_type": "/obj/item",
					"field_profile": "atom_like",
					"base_values": {"name": "radio", "description": "radio"},
					"icon_metadata": {},
				},
			])

			corpus = load_corpus(repo_root)

			self.assertEqual(corpus.entries, ())
			self.assertEqual(len(corpus.targets), 1)
			self.assertEqual(corpus.targets[0].type_path, "/obj/item/radio")

	def test_load_corpus_parses_optional_special_description_overrides(self) -> None:
		with self.make_repo() as temp_dir:
			repo_root = Path(temp_dir)
			seed_targets(repo_root, [])
			seed_override(repo_root, "items", {
				"id": "items.radio",
				"type_path": "/obj/item/radio",
				"special_desc_requirement": "syndicate",
				"special_desc": "A covert communications device.",
			})

			entry = load_corpus(repo_root).entries[0]

			self.assertEqual(entry.special_desc_requirement, "syndicate")
			self.assertEqual(entry.special_desc, "A covert communications device.")


if __name__ == "__main__":
	unittest.main()

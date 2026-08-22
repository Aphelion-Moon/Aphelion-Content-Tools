from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from tools.lore_editor.tests.store_helpers import seed_override, seed_targets
from webapp.store import db
from webapp.store.schema import decode, table

ITEMS_SOURCE_FILE = "tools/lore_editor/content/overrides/items.json"
GENERATED_PATH = "tools/lore_editor/stages/current/generated_lore_overrides.dm"


class ApiWriteTests(unittest.TestCase):
	def make_repo(self) -> Path:
		temp_dir = tempfile.TemporaryDirectory()
		self.addCleanup(temp_dir.cleanup)
		repo_root = Path(temp_dir.name)
		seed_targets(repo_root, [{
			"type_path": "/obj/item/radio",
			"label": "Radio",
			"field_profile": "atom_like",
		}])
		seed_override(repo_root, "items", {
			"id": "items.radio",
			"type_path": "/obj/item/radio",
			"name": "Old radio",
		})
		return repo_root

	def override_row(self, repo_root: Path, entry_id: str):
		return db.get_row(table(repo_root, "overrides"), f"id = '{entry_id}'")

	def test_save_entry_validates_writes_atomically_and_generates_dm(self) -> None:
		from tools.lore_editor.api import save_entry

		repo_root = self.make_repo()
		result = save_entry(
			repo_root,
			entry_id="items.radio",
			source_file=ITEMS_SOURCE_FILE,
			entry={
				"id": "items.radio",
				"type_path": "/obj/item/radio",
				"name": "New radio",
				"description": "A rewritten handset.",
			},
		)

		self.assertEqual(result["id"], "items.radio")
		self.assertEqual(decode(self.override_row(repo_root, "items.radio"))["name"], "New radio")
		self.assertIn('name = "New radio"', (repo_root / GENERATED_PATH).read_text(encoding="utf-8"))

	def test_save_entry_persists_special_description_overrides(self) -> None:
		from tools.lore_editor.api import save_entry

		repo_root = self.make_repo()
		result = save_entry(
			repo_root,
			entry_id="items.radio",
			source_file=ITEMS_SOURCE_FILE,
			entry={
				"id": "items.radio",
				"type_path": "/obj/item/radio",
				"special_desc_requirement": "syndicate",
				"special_desc": "A covert communications device.",
			},
		)

		self.assertEqual(result["special_desc_requirement"], "syndicate")
		self.assertEqual(result["special_desc"], "A covert communications device.")
		stored = decode(self.override_row(repo_root, "items.radio"))
		self.assertEqual(stored["special_desc_requirement"], "syndicate")
		self.assertEqual(stored["special_desc"], "A covert communications device.")
		generated = (repo_root / GENERATED_PATH).read_text(encoding="utf-8")
		self.assertIn("special_desc_requirement = EXAMINE_CHECK_SYNDICATE", generated)
		self.assertIn('special_desc = "A covert communications device."', generated)

	def test_save_entry_rejects_invalid_candidate_without_modifying_source_or_generated(self) -> None:
		from tools.lore_editor.api import save_entry

		repo_root = self.make_repo()
		original_row = self.override_row(repo_root, "items.radio")
		generated_path = repo_root / GENERATED_PATH
		generated_path.parent.mkdir(parents=True, exist_ok=True)
		generated_path.write_bytes(b"original generated\n")

		with self.assertRaisesRegex(ValueError, "type_path"):
			save_entry(
				repo_root,
				entry_id="items.radio",
				source_file=ITEMS_SOURCE_FILE,
				entry={
					"id": "items.radio",
					"type_path": "/obj/item/not_in_catalog",
					"name": "Bad radio",
				},
			)

		self.assertEqual(self.override_row(repo_root, "items.radio"), original_row)
		self.assertEqual(generated_path.read_bytes(), b"original generated\n")

	def test_save_entry_rejects_source_path_traversal(self) -> None:
		from tools.lore_editor.api import save_entry

		repo_root = self.make_repo()
		with self.assertRaises(ValueError):
			save_entry(
				repo_root,
				entry_id="items.radio",
				source_file="tools/lore_editor/content/overrides/../targets.json",
				entry={"id": "items.radio", "type_path": "/obj/item/radio"},
			)

	def test_save_entry_creates_a_new_entry_in_an_existing_group(self) -> None:
		from tools.lore_editor.api import save_entry

		repo_root = self.make_repo()
		seed_targets(repo_root, [
			{"type_path": "/obj/item/radio", "label": "Radio", "field_profile": "atom_like"},
			{"type_path": "/obj/item/megaphone", "label": "Megaphone", "field_profile": "atom_like"},
		])

		save_entry(
			repo_root,
			entry_id="items.megaphone",
			source_file=ITEMS_SOURCE_FILE,
			entry={
				"id": "items.megaphone",
				"type_path": "/obj/item/megaphone",
				"name": "Station hailer",
			},
		)

		overrides = db.all_rows(table(repo_root, "overrides"), where="group = 'items'")
		self.assertEqual(len(overrides), 2)

	def test_save_entry_rejects_mismatched_source_file(self) -> None:
		from tools.lore_editor.api import save_entry

		repo_root = self.make_repo()
		with self.assertRaisesRegex(ValueError, "different source file"):
			save_entry(
				repo_root,
				entry_id="items.radio",
				source_file="tools/lore_editor/content/overrides/jobs.json",
				entry={"id": "items.radio", "type_path": "/obj/item/radio"},
			)
		self.assertEqual(decode(self.override_row(repo_root, "items.radio"))["name"], "Old radio")

	def test_create_entry_can_create_a_new_override_group(self) -> None:
		from tools.lore_editor.api import create_entry, list_entity_files

		repo_root = self.make_repo()
		seed_targets(repo_root, [
			{"type_path": "/obj/item/radio", "label": "Radio", "field_profile": "atom_like"},
			{"type_path": "/obj/item/megaphone", "label": "Megaphone", "field_profile": "atom_like"},
		])
		result = create_entry(
			repo_root,
			source_file="tools/lore_editor/content/overrides/languages.json",
			entry={
				"id": "languages.megaphone",
				"type_path": "/obj/item/megaphone",
				"name": "Common megaphone",
			},
		)

		self.assertEqual(result["id"], "languages.megaphone")
		self.assertEqual(decode(self.override_row(repo_root, "languages.megaphone"))["name"], "Common megaphone")
		self.assertIn("tools/lore_editor/content/overrides/languages.json", list_entity_files(repo_root))

	def test_create_entry_rejects_an_id_that_already_exists(self) -> None:
		from tools.lore_editor.api import create_entry

		repo_root = self.make_repo()
		with self.assertRaises(ValueError):
			create_entry(
				repo_root,
				source_file=ITEMS_SOURCE_FILE,
				entry={"id": "items.radio", "type_path": "/obj/item/radio", "name": "Duplicate"},
			)

	def test_create_entry_rejects_paths_outside_entity_groups(self) -> None:
		from tools.lore_editor.api import create_entry

		repo_root = self.make_repo()
		with self.assertRaises(ValueError):
			create_entry(
				repo_root,
				source_file="tools/lore_editor/content/overrides/../groups.json",
				entry={"id": "bad", "type_path": "/obj/item/radio"},
			)

	def test_generation_failure_restores_source_and_generated_bytes(self) -> None:
		from tools.lore_editor.api import save_entry

		repo_root = self.make_repo()
		generated_path = repo_root / GENERATED_PATH
		generated_path.parent.mkdir(parents=True, exist_ok=True)
		generated_path.write_bytes(b"original generated\n")
		original_row = self.override_row(repo_root, "items.radio")

		with patch("tools.lore_editor.api.write_generated_dm", side_effect=ValueError("generation failed")):
			with self.assertRaisesRegex(ValueError, "generation failed"):
				save_entry(
					repo_root,
					entry_id="items.radio",
					source_file=ITEMS_SOURCE_FILE,
					entry={"id": "items.radio", "type_path": "/obj/item/radio", "name": "New radio"},
				)

		self.assertEqual(self.override_row(repo_root, "items.radio"), original_row)
		self.assertEqual(generated_path.read_bytes(), b"original generated\n")

	def test_delete_entry_removes_one_entry_from_a_shared_group(self) -> None:
		from tools.lore_editor.api import delete_entry

		repo_root = self.make_repo()
		seed_targets(repo_root, [
			{"type_path": "/obj/item/radio", "label": "Radio", "field_profile": "atom_like"},
			{"type_path": "/obj/item/megaphone", "label": "Megaphone", "field_profile": "atom_like"},
		])
		seed_override(repo_root, "items", {"id": "items.megaphone", "type_path": "/obj/item/megaphone", "name": "Old megaphone"})

		result = delete_entry(repo_root, entry_id="items.radio", source_file=ITEMS_SOURCE_FILE)

		self.assertEqual(result, {"deleted": True, "id": "items.radio"})
		self.assertIsNone(self.override_row(repo_root, "items.radio"))
		self.assertIsNotNone(self.override_row(repo_root, "items.megaphone"))

	def test_delete_entry_regenerates_the_dm_stage(self) -> None:
		from tools.lore_editor.api import delete_entry

		repo_root = self.make_repo()
		generated_path = repo_root / GENERATED_PATH

		delete_entry(repo_root, entry_id="items.radio", source_file=ITEMS_SOURCE_FILE)

		self.assertNotIn("Old radio", generated_path.read_text(encoding="utf-8"))

	def test_delete_entry_rejects_an_unknown_entry_id(self) -> None:
		from tools.lore_editor.api import delete_entry

		repo_root = self.make_repo()
		with self.assertRaisesRegex(ValueError, "was not found"):
			delete_entry(repo_root, entry_id="items.nonexistent", source_file=ITEMS_SOURCE_FILE)

	def test_delete_entry_rejects_source_path_traversal(self) -> None:
		from tools.lore_editor.api import delete_entry

		repo_root = self.make_repo()
		with self.assertRaises(ValueError):
			delete_entry(
				repo_root,
				entry_id="items.radio",
				source_file="tools/lore_editor/content/overrides/../targets.json",
			)

	def test_delete_entry_failure_restores_the_row_and_generated_bytes(self) -> None:
		from tools.lore_editor.api import delete_entry

		repo_root = self.make_repo()
		generated_path = repo_root / GENERATED_PATH
		generated_path.parent.mkdir(parents=True, exist_ok=True)
		generated_path.write_bytes(b"original generated\n")
		original_row = self.override_row(repo_root, "items.radio")

		with patch("tools.lore_editor.api.write_generated_dm", side_effect=ValueError("generation failed")):
			with self.assertRaisesRegex(ValueError, "generation failed"):
				delete_entry(repo_root, entry_id="items.radio", source_file=ITEMS_SOURCE_FILE)

		self.assertEqual(self.override_row(repo_root, "items.radio"), original_row)
		self.assertEqual(generated_path.read_bytes(), b"original generated\n")


if __name__ == "__main__":
	unittest.main()

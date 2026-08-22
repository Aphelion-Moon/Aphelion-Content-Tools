from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.lore_editor.tests.store_helpers import seed_group, seed_override, seed_targets


class ApiReadTests(unittest.TestCase):
	def make_repo(self) -> Path:
		temp_dir = tempfile.TemporaryDirectory()
		self.addCleanup(temp_dir.cleanup)
		repo_root = Path(temp_dir.name)
		seed_targets(repo_root, [
			{
				"type_path": "/obj/item/radio",
				"label": "Handheld Radio",
				"editable_root": "/obj/item/radio",
				"parent_type": "/obj/item",
				"field_profile": "atom_like",
				"base_values": {"name": "base radio", "description": "Base description."},
				"icon_metadata": {},
			},
			{
				"type_path": "/obj/item/megaphone",
				"label": "Megaphone",
				"editable_root": "/obj/item/megaphone",
				"parent_type": "/obj/item",
				"field_profile": "atom_like",
				"base_values": {"name": "base megaphone", "description": "Base hailer."},
				"icon_metadata": {},
			},
		])
		seed_override(repo_root, "jobs", {"id": "jobs.megaphone", "type_path": "/obj/item/megaphone", "name": "job hailer"})
		seed_override(repo_root, "items", {
			"id": "items.radio",
			"type_path": "/obj/item/radio",
			"name": "lore radio",
			"special_desc_requirement": "none",
			"special_desc": "A radio with a hidden note.",
		})
		return repo_root

	def test_list_catalog_and_entries_are_stable_and_source_relative(self) -> None:
		from tools.lore_editor.api import list_catalog, list_entries

		repo_root = self.make_repo()
		targets = list_catalog(repo_root)
		entries = list_entries(repo_root)

		self.assertEqual([target["type_path"] for target in targets], ["/obj/item/megaphone", "/obj/item/radio"])
		self.assertEqual([entry["id"] for entry in entries], ["jobs.megaphone", "items.radio"])
		self.assertEqual(entries[1]["source_file"], "tools/lore_editor/content/overrides/items.json")
		self.assertEqual(entries[1]["base_name"], "base radio")
		self.assertEqual(entries[1]["special_desc_requirement"], "none")
		self.assertEqual(entries[1]["special_desc"], "A radio with a hidden note.")
		self.assertNotIn(str(repo_root), json.dumps(entries))

	def test_entry_filters_preserve_source_order(self) -> None:
		from tools.lore_editor.api import list_entries

		repo_root = self.make_repo()
		self.assertEqual([entry["id"] for entry in list_entries(repo_root, query="radio")], ["items.radio"])
		self.assertEqual([entry["id"] for entry in list_entries(repo_root, category="jobs")], ["jobs.megaphone"])

	def test_review_response_supports_bounded_pages(self) -> None:
		from tools.lore_editor.api import list_review_response

		repo_root = self.make_repo()
		response = list_review_response(repo_root, limit=1)

		self.assertEqual(len(response["entries"]), 1)
		self.assertEqual(response["matched_entry_count"], 2)
		self.assertEqual(response["returned_entry_count"], 1)
		self.assertTrue(response["has_more"])

	def test_review_catalog_index_is_reused_until_catalog_or_groups_change(self) -> None:
		from unittest.mock import patch

		from tools.lore_editor.api import list_review_response

		repo_root = self.make_repo()
		with patch("tools.lore_editor.api.classify_target_details", wraps=None) as classify:
			list_review_response(repo_root)
			first_call_count = classify.call_count
			list_review_response(repo_root)
			self.assertEqual(classify.call_count, first_call_count)

			seed_group(repo_root, {"id": "items", "label": "Items", "color": "#9614d0", "keywords": [], "type_path_prefixes": ["/obj/item"]})
			list_review_response(repo_root)
			self.assertEqual(classify.call_count, first_call_count + 2)


if __name__ == "__main__":
	unittest.main()

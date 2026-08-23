from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.lore_editor import api
from tools.lore_editor.api import (
	groups_response,
	list_review_response,
	save_group_response,
	save_review_response,
)
from tools.lore_editor.records import canonical_record_hash, record_path
from tools.lore_editor.tests.store_helpers import seed_group, seed_override, seed_review, seed_targets
from webapp.store import db
from webapp.store.metadata import activate_projection, new_projection_metadata, projection_path, write_projection_marker


class ReviewApiTests(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.repo_root = Path(self.temp_dir.name)
		seed_targets(self.repo_root, [
			{
				"type_path": "/datum/language/common",
				"label": "Common",
				"field_profile": "named_datum",
				"base_values": {"name": "Common", "description": "Used by Nanotrasen crews."},
			},
			{
				"type_path": "/obj/item/radio",
				"label": "Radio",
				"field_profile": "atom_like",
				"base_values": {"name": "Radio", "description": "A standard radio."},
			},
		])
		seed_override(self.repo_root, "items", {
			"id": "items.radio",
			"type_path": "/obj/item/radio",
			"name": "Override radio",
		})
		seed_group(self.repo_root, {
			"id": "languages",
			"label": "Languages",
			"color": "#60a5fa",
			"type_path_prefixes": ["/datum/language"],
		})
		seed_group(self.repo_root, {
			"id": "nanotrasen",
			"label": "Nanotrasen",
			"color": "#34d399",
			"keywords": ["nanotrasen"],
		})
		seed_review(self.repo_root, "/datum/language/common", {
			"status": "reviewed",
			"reviewed_by": "Zoe",
			"reviewed_at": "2026-08-20T12:00:00+00:00",
			"notes": "Base language is acceptable.",
		})

	def tearDown(self) -> None:
		self.temp_dir.cleanup()

	def test_review_items_join_override_review_and_groups(self) -> None:
		response = list_review_response(self.repo_root)
		by_type = {entry["type_path"]: entry for entry in response["entries"]}
		self.assertEqual(by_type["/datum/language/common"]["status"], "reviewed")
		self.assertEqual(by_type["/datum/language/common"]["groups"], ["languages", "nanotrasen"])
		self.assertEqual(
			by_type["/datum/language/common"]["group_match_reasons"]["nanotrasen"],
			["keyword 'nanotrasen' in description"],
		)
		self.assertEqual(by_type["/obj/item/radio"]["status"], "overridden")
		self.assertTrue(by_type["/obj/item/radio"]["has_override"])
		self.assertEqual(response["status_counts"]["reviewed"], 1)
		self.assertEqual(response["status_counts"]["overridden"], 1)

	def test_review_filters_and_sort_are_deterministic(self) -> None:
		filtered = list_review_response(self.repo_root, query="nanotrasen", groups=("languages",), statuses=("reviewed",), sort="type_path")
		self.assertEqual([entry["type_path"] for entry in filtered["entries"]], ["/datum/language/common"])
		sorted_by_status = list_review_response(self.repo_root, sort="status")
		self.assertEqual([entry["status"] for entry in sorted_by_status["entries"]], ["reviewed", "overridden"])

	def test_group_and_review_write_responses_update_the_feed(self) -> None:
		created = save_group_response(self.repo_root, {
			"id": "frontier-cults",
			"label": "Frontier Cults",
			"color": "#f59e0b",
			"keywords": ["cult"],
			"type_path_prefixes": [],
			"assignments": ["/obj/item/radio"],
		})
		self.assertEqual(created["group"]["id"], "frontier-cults")
		self.assertEqual(created["group"]["record_hash"], canonical_record_hash({
			"id": "frontier-cults",
			"label": "Frontier Cults",
			"color": "#f59e0b",
			"keywords": ["cult"],
			"type_path_prefixes": [],
			"keyword_scope": ["name", "description", "label"],
		}))
		reviewed = save_review_response(self.repo_root, "/obj/item/radio", {
			"status": "reviewed",
			"reviewed_by": "Mara",
			"notes": "Radio is acceptable as-is.",
		})
		self.assertEqual(reviewed["review"]["status"], "reviewed")
		self.assertEqual(
			reviewed["review"]["record_hash"],
			canonical_record_hash({
				"type_path": "/obj/item/radio",
				"status": "reviewed",
				"reviewed_by": "Mara",
				"reviewed_at": reviewed["review"]["reviewed_at"],
				"notes": "Radio is acceptable as-is.",
			}),
		)
		response = list_review_response(self.repo_root, groups=("frontier-cults",), statuses=("overridden",))
		self.assertEqual([entry["type_path"] for entry in response["entries"]], ["/obj/item/radio"])

	def test_needs_attention_is_a_writer_action(self) -> None:
		flagged = save_review_response(self.repo_root, "/obj/item/radio", {
			"status": "needs-attention",
			"reviewed_by": "Mara",
			"notes": "Confirm whether this is still Nanotrasen-owned.",
		})
		self.assertEqual(flagged["review"]["status"], "needs-attention")
		response = list_review_response(self.repo_root, statuses=("needs-attention",))
		self.assertEqual([entry["type_path"] for entry in response["entries"]], ["/obj/item/radio"])

	def test_catalog_suppression_requires_explicit_toggles_and_preserves_icon_metadata(self) -> None:
		seed_targets(
			self.repo_root,
			[
				{
					"type_path": "/obj/item/radio",
					"label": "Radio",
					"field_profile": "atom_like",
					"base_values": {"name": "Radio", "description": "A standard radio."},
					"icon_metadata": {"icon": {"file": "icons/obj/radio.dmi", "state": "radio", "available_states": ["radio"]}},
				},
				{
					"type_path": "/obj/item/radio/directional/east",
					"label": "Radio",
					"field_profile": "atom_like",
					"parent_type": "/obj/item/radio",
					"editable_root": "/obj/item/radio",
					"base_values": {"name": "Radio", "description": "A standard radio."},
					"icon_metadata": {},
				},
				{
					"type_path": "/obj/item/radio/redundant",
					"label": "Radio",
					"field_profile": "atom_like",
					"parent_type": "/obj/item/radio",
					"editable_root": "/obj/item/radio",
					"base_values": {"name": "Radio", "description": "A standard radio."},
					"icon_metadata": {},
				},
			],
		)
		visible = list_review_response(self.repo_root)
		self.assertEqual([entry["type_path"] for entry in visible["entries"]], ["/obj/item/radio"])
		included = list_review_response(self.repo_root, include_directional=True, include_redundant=True)
		by_type = {entry["type_path"]: entry for entry in included["entries"]}
		self.assertEqual(by_type["/obj/item/radio"]["icon_metadata"]["icon"]["state"], "radio")
		self.assertTrue(by_type["/obj/item/radio/directional/east"]["directional"])
		self.assertTrue(by_type["/obj/item/radio/redundant"]["redundant"])

	def test_unknown_filter_values_are_rejected(self) -> None:
		with self.assertRaises(ValueError):
			list_review_response(self.repo_root, sort="newest-first")

	def test_repeated_queries_reuse_the_cached_review_snapshot(self) -> None:
		list_review_response(self.repo_root)
		with patch.object(api, "_build_review_entries_snapshot", wraps=api._build_review_entries_snapshot) as build_spy:
			list_review_response(self.repo_root, query="nanotrasen")
			list_review_response(self.repo_root, sort="status")
			list_review_response(self.repo_root, statuses=("reviewed",))
			build_spy.assert_not_called()

		save_review_response(self.repo_root, "/obj/item/radio", {
			"status": "reviewed",
			"reviewed_by": "Mara",
			"notes": "Confirmed.",
		})
		with patch.object(api, "_build_review_entries_snapshot", wraps=api._build_review_entries_snapshot) as build_spy:
			response = list_review_response(self.repo_root)
			build_spy.assert_called_once()
			by_type = {entry["type_path"]: entry for entry in response["entries"]}
			self.assertEqual(by_type["/obj/item/radio"]["review"]["status"], "reviewed")

	def test_projection_activation_invalidates_caches_without_an_in_process_generation_change(self) -> None:
		with patch.object(db, "current_generation", return_value=0):
			list_review_response(self.repo_root)
			metadata = new_projection_metadata("external-worker-revision")
			destination = projection_path(self.repo_root, metadata.generation_id)
			shutil.copytree(db.store_path(self.repo_root), destination)
			write_projection_marker(self.repo_root, metadata)
			activate_projection(self.repo_root, metadata)

			with patch.object(api, "_build_review_entries_snapshot", wraps=api._build_review_entries_snapshot) as build_spy:
				list_review_response(self.repo_root)
				build_spy.assert_called_once()

	def test_groups_response_includes_counts(self) -> None:
		response = groups_response(self.repo_root)
		self.assertEqual([group["id"] for group in response["groups"]], ["languages", "nanotrasen"])
		self.assertEqual(response["counts"]["languages"], 1)
		self.assertTrue(all(len(group["record_hash"]) == 64 for group in response["groups"]))
		self.assertEqual(response["assignment_record_hashes"], {})

	def test_review_feed_exposes_the_review_record_hash(self) -> None:
		response = list_review_response(self.repo_root)
		by_type = {entry["type_path"]: entry for entry in response["entries"]}
		review = by_type["/datum/language/common"]["review"]
		self.assertEqual(review["record_hash"], canonical_record_hash({
			"type_path": "/datum/language/common",
			"status": "reviewed",
			"reviewed_by": "Zoe",
			"reviewed_at": "2026-08-20T12:00:00+00:00",
			"notes": "Base language is acceptable.",
		}))

	def test_projection_failure_returns_a_stale_state_without_undoing_the_review(self) -> None:
		with patch("tools.lore_editor.api.reconcile_projection", side_effect=RuntimeError("projection failed")):
			response = save_review_response(self.repo_root, "/obj/item/radio", {
				"status": "reviewed",
				"reviewed_by": "Zoe",
				"notes": "Canonical decision",
			})

		self.assertFalse(response["projection"]["current"])
		self.assertIn("projection failed", response["projection"]["reason"])
		self.assertTrue(record_path(self.repo_root, "review", "/obj/item/radio").is_file())


if __name__ == "__main__":
	unittest.main()

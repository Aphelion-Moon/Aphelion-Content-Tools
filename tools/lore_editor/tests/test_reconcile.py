from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.lore_editor.reconcile import materialize_legacy_records, reconcile_projection, scan_canonical_records
from tools.lore_editor.records import atomic_write_record, record_path
from tools.lore_editor.taxonomy import load_groups, load_reviews
from tools.lore_editor.tests.store_helpers import seed_override
from webapp.api.app import create_app
from webapp.store import db
from webapp.store.db import store_path
from webapp.store.metadata import backup_projection, projection_status, restore_projection
from webapp.store.schema import decode, table
from webapp.tests.http_client import TestClient


class ReconcileProjectionTests(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp_dir.cleanup)
		self.repo_root = Path(self.temp_dir.name)

	def test_fresh_workspace_projects_canonical_writer_records(self) -> None:
		atomic_write_record(record_path(self.repo_root, "group", "items"), {
			"id": "items",
			"label": "Items",
			"color": "#ffffff",
			"keywords": ["item"],
			"type_path_prefixes": ["/obj/item"],
		})
		atomic_write_record(record_path(self.repo_root, "override", "items.radio"), {
			"id": "items.radio",
			"type_path": "/obj/item/radio",
			"name": "Frontier radio",
		})
		atomic_write_record(record_path(self.repo_root, "review", "/obj/item/radio"), {
			"type_path": "/obj/item/radio",
			"status": "reviewed",
			"reviewed_by": "Zoe",
			"reviewed_at": "2026-08-22T12:00:00+00:00",
			"notes": "Ready",
		})
		atomic_write_record(record_path(self.repo_root, "assignment", "/obj/item/radio"), {
			"type_path": "/obj/item/radio",
			"group_ids": ["items"],
		})

		result = reconcile_projection(self.repo_root)

		self.assertEqual(result.counts, {"overrides": 1, "groups": 1, "reviews": 1, "assignments": 1})
		self.assertEqual(load_groups(self.repo_root).assignments["/obj/item/radio"], ("items",))
		self.assertEqual(load_reviews(self.repo_root)["/obj/item/radio"].notes, "Ready")
		override_row = db.get_row_by_key(table(self.repo_root, "overrides"), "id", "items.radio")
		self.assertEqual(decode(override_row)["name"], "Frontier radio")

	def test_fastapi_startup_reconciles_canonical_records_before_serving(self) -> None:
		atomic_write_record(record_path(self.repo_root, "group", "items"), {
			"id": "items",
			"label": "Items",
			"color": "#ffffff",
			"keywords": ["item"],
			"type_path_prefixes": ["/obj/item"],
		})

		with TestClient(create_app(self.repo_root)) as client:
			response = client.get("/api/groups")

		self.assertEqual(response.status_code, 200)
		self.assertEqual([group["id"] for group in response.json()["groups"]], ["items"])

	def test_absent_canonical_kind_does_not_delete_legacy_store_records(self) -> None:
		seed_override(self.repo_root, "items", {
			"id": "items.radio",
			"type_path": "/obj/item/radio",
			"name": "Database-only radio",
		})
		atomic_write_record(record_path(self.repo_root, "group", "items"), {
			"id": "items",
			"label": "Items",
			"color": "#ffffff",
			"keywords": [],
			"type_path_prefixes": [],
		})

		reconcile_projection(self.repo_root)

		stored = db.get_row_by_key(table(self.repo_root, "overrides"), "id", "items.radio")
		self.assertEqual(decode(stored)["name"], "Database-only radio")

	def test_materializing_a_legacy_kind_exports_every_store_record_before_activation(self) -> None:
		seed_override(self.repo_root, "items", {
			"id": "items.radio",
			"type_path": "/obj/item/radio",
			"name": "Database-only radio",
		})
		seed_override(self.repo_root, "items", {
			"id": "items.megaphone",
			"type_path": "/obj/item/megaphone",
			"name": "Database-only megaphone",
		})

		written = materialize_legacy_records(self.repo_root, "override")

		self.assertEqual(
			{path.name for path in written},
			{"items.radio.json", "items.megaphone.json"},
		)
		self.assertEqual(
			json.loads(record_path(self.repo_root, "override", "items.radio").read_text(encoding="utf-8"))["name"],
			"Database-only radio",
		)
		reconcile_projection(self.repo_root)
		self.assertEqual(table(self.repo_root, "overrides").count_rows(), 2)

	def test_add_update_and_git_delete_each_activate_a_complete_new_generation(self) -> None:
		path = record_path(self.repo_root, "group", "items")
		original = {"id": "items", "label": "Items", "color": "#fff", "keywords": [], "type_path_prefixes": []}
		updated = {**original, "label": "Updated Items"}
		atomic_write_record(path, original)

		first = reconcile_projection(self.repo_root)
		first_path = store_path(self.repo_root)
		atomic_write_record(path, updated)
		second = reconcile_projection(self.repo_root)
		second_path = store_path(self.repo_root)
		self.assertNotEqual(first_path, second_path)
		self.assertNotEqual(first.content_revision, second.content_revision)
		self.assertEqual(decode(db.get_row_by_key(table(self.repo_root, "groups"), "id", "items"))["label"], "Updated Items")

		path.unlink()
		third = reconcile_projection(self.repo_root)
		self.assertEqual(third.counts["groups"], 0)
		self.assertIsNone(db.get_row_by_key(table(self.repo_root, "groups"), "id", "items"))

	def test_interrupted_build_keeps_the_previous_projection_readable(self) -> None:
		path = record_path(self.repo_root, "group", "items")
		original = {"id": "items", "label": "Items", "color": "#fff", "keywords": [], "type_path_prefixes": []}
		atomic_write_record(path, original)
		reconcile_projection(self.repo_root)
		previous_path = store_path(self.repo_root)
		atomic_write_record(path, {**original, "label": "Interrupted update"})

		with (
			patch("tools.lore_editor.reconcile.db.sync_snapshot", side_effect=RuntimeError("interrupted")),
			self.assertRaisesRegex(RuntimeError, "interrupted"),
		):
			reconcile_projection(self.repo_root)

		self.assertEqual(store_path(self.repo_root), previous_path)
		stored = db.get_row_by_key(table(self.repo_root, "groups"), "id", "items")
		self.assertEqual(decode(stored)["label"], "Items")

	def test_corrupt_active_generation_falls_back_to_the_previous_projection(self) -> None:
		path = record_path(self.repo_root, "group", "items")
		original = {"id": "items", "label": "Items", "color": "#fff", "keywords": [], "type_path_prefixes": []}
		atomic_write_record(path, original)
		reconcile_projection(self.repo_root)
		first_path = store_path(self.repo_root)
		atomic_write_record(path, {**original, "label": "Second generation"})
		reconcile_projection(self.repo_root)
		second_path = store_path(self.repo_root)
		self.assertNotEqual(first_path, second_path)

		(second_path / "projection.json").write_text("not json", encoding="utf-8")

		self.assertEqual(store_path(self.repo_root), first_path)
		stored = db.get_row_by_key(table(self.repo_root, "groups"), "id", "items")
		self.assertEqual(decode(stored)["label"], "Items")

	def test_invalid_active_generation_id_falls_back_to_the_previous_projection(self) -> None:
		path = record_path(self.repo_root, "group", "items")
		original = {"id": "items", "label": "Items", "color": "#fff", "keywords": [], "type_path_prefixes": []}
		atomic_write_record(path, original)
		reconcile_projection(self.repo_root)
		first_path = store_path(self.repo_root)
		atomic_write_record(path, {**original, "label": "Second generation"})
		reconcile_projection(self.repo_root)
		second_path = store_path(self.repo_root)
		self.assertNotEqual(first_path, second_path)

		active_pointer = self.repo_root / "webapp" / "store" / "active-projection.json"
		payload = json.loads(active_pointer.read_text(encoding="utf-8"))
		payload["generation_id"] = "invalid/path"
		active_pointer.write_text(json.dumps(payload), encoding="utf-8")

		self.assertEqual(store_path(self.repo_root), first_path)

	def test_backup_and_restore_are_labeled_projection_snapshots(self) -> None:
		path = record_path(self.repo_root, "group", "items")
		original = {"id": "items", "label": "Items", "color": "#fff", "keywords": [], "type_path_prefixes": []}
		atomic_write_record(path, original)
		reconcile_projection(self.repo_root)
		backup_path = self.repo_root / "backups" / "before-edit"
		backup_projection(self.repo_root, backup_path, label="before-edit")
		atomic_write_record(path, {**original, "label": "Changed"})
		reconcile_projection(self.repo_root)

		restored = restore_projection(self.repo_root, backup_path)

		self.assertEqual(restored.revision.state, "stale")
		stored = db.get_row_by_key(table(self.repo_root, "groups"), "id", "items")
		self.assertEqual(decode(stored)["label"], "Items")

	def test_content_change_marks_the_active_projection_out_of_date_until_reconciled(self) -> None:
		path = record_path(self.repo_root, "group", "items")
		original = {"id": "items", "label": "Items", "color": "#fff", "keywords": [], "type_path_prefixes": []}
		atomic_write_record(path, original)
		reconcile_projection(self.repo_root)
		current_revision = scan_canonical_records(self.repo_root).content_revision
		self.assertTrue(projection_status(self.repo_root, current_revision).current)

		atomic_write_record(path, {**original, "label": "Changed on branch"})
		changed_revision = scan_canonical_records(self.repo_root).content_revision
		self.assertFalse(projection_status(self.repo_root, changed_revision).current)


if __name__ == "__main__":
	unittest.main()

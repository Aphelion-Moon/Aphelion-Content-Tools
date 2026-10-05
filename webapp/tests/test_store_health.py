from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.lore_editor.reconcile import reconcile_projection
from tools.lore_editor.records import atomic_write_record, record_path
from tools.lore_editor.tests.store_helpers import legacy_table
from webapp.git_adapter import GameSourceRevision
from webapp.store import db
from webapp.store.health import store_health
from webapp.store.metadata import ActiveProjection, projection_status
from webapp.store.schema import TABLE_SCHEMAS, encode


class StoreHealthTests(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp_dir.cleanup)
		self.repo_root = Path(self.temp_dir.name)

	def test_health_does_not_initialize_the_embedding_model(self) -> None:
		with patch("webapp.store.embeddings._load_model", side_effect=AssertionError("health must not load models")):
			health = store_health(self.repo_root)
		self.assertIn(health["semantic_search"]["mode"], ("hybrid", "keyword-only"))

	def test_graph_health_reads_only_compact_metadata(self) -> None:
		from webapp.store.health import _game_dataset_health

		manifest = {"game_repo_revision": "game-revision", "format_version": 1, "snapshot_sha256": "graph-hash", "source_sha256": "source-hash", "source_observation": "observation"}
		with patch("webapp.store.health.db.get_row_by_key", return_value={"raw_json": encode(manifest)}) as read:
			health = _game_dataset_health(self.repo_root, "graph", "game-revision", store_dir=self.repo_root / "store", selected_source=GameSourceRevision("game", "game-revision", False, "observation"))
		self.assertTrue(health["current"])
		self.assertEqual(read.call_args.args[2], "graph-health")

	def test_explicitly_unavailable_source_is_not_observed_again(self) -> None:
		with patch("webapp.store.health.observe_game_source", side_effect=AssertionError("do not retry in the same tick")):
			health = store_health(self.repo_root, self.repo_root / "game", game_source=None)
		self.assertFalse(health["workspace"]["current"])
		self.assertIsNone(health["workspace"]["selected_game_revision"])

	def test_catalog_without_verified_source_is_not_current_at_matching_head(self) -> None:
		from webapp.store.health import _game_dataset_health

		manifest = {"game_repo_revision": "game-revision", "format_version": 1, "snapshot_sha256": "catalog-hash"}
		with patch("webapp.store.health.db.get_row_by_key", return_value={"raw_json": encode(manifest)}):
			health = _game_dataset_health(self.repo_root, "catalog", "game-revision", store_dir=self.repo_root / "store", selected_source=GameSourceRevision("game", "game-revision", False, "observation"))
		self.assertFalse(health["current"])
		self.assertIn("unverified", health["reason"])

	def test_reports_zero_rows_for_every_table_on_a_fresh_store(self) -> None:
		health = store_health(self.repo_root)
		self.assertEqual(health["total_rows"], 0)
		self.assertEqual(set(health["tables"]), set(TABLE_SCHEMAS))
		self.assertTrue(all(count == 0 for count in health["tables"].values()))
		self.assertIsNone(health["last_write_time"])
		self.assertEqual(health["disk_bytes"], 0)
		self.assertFalse((self.repo_root / "webapp/store").exists())

	def test_last_write_time_is_none_when_the_store_directory_does_not_exist_at_all(self) -> None:
		from webapp.store.health import _directory_stats

		empty_size, empty_last_write = _directory_stats(self.repo_root / "does-not-exist")
		self.assertEqual(empty_size, 0)
		self.assertIsNone(empty_last_write)

	def test_binds_all_health_table_reads_to_one_store_generation(self) -> None:
		pinned_store = self.repo_root / "webapp" / "store" / "projections" / "pinned"
		store_dirs = []

		class RecordingTable:
			def count_rows(self):
				return 0

		def fake_table(_repo_root, _name, *, store_dir=None):
			store_dirs.append(store_dir)
			return RecordingTable()

		with (
			patch("webapp.store.health.selected_projection", return_value=ActiveProjection(None, pinned_store)),
			patch("webapp.store.health.table", side_effect=fake_table),
			patch("webapp.store.health.observe_game_source", return_value=GameSourceRevision("game", "game-revision", False, "observation")),
			patch("webapp.store.health.db.get_row_by_key", return_value=None),
		):
			health = store_health(self.repo_root, self.repo_root / "game")

		self.assertEqual(health["total_rows"], 0)
		self.assertEqual(store_dirs, [pinned_store] * (len(TABLE_SCHEMAS) + 2))
		self.assertEqual(health["projection"]["path"], str(pinned_store))

	def test_projection_status_reads_the_active_pointer_once(self) -> None:
		pinned_store = self.repo_root / "webapp" / "store" / "data"
		with patch("webapp.store.metadata.active_projection", return_value=ActiveProjection(None, pinned_store)) as active_spy:
			status = projection_status(self.repo_root, "revision")

		self.assertFalse(status.current)
		self.assertEqual(status.path, pinned_store)
		active_spy.assert_called_once_with(self.repo_root)

	def test_reports_row_counts_disk_size_and_a_last_write_time_after_a_write(self) -> None:
		targets = legacy_table(self.repo_root, "catalog_targets")
		db.upsert_rows(targets, "id", [
			{"id": "a", "type_path": "/a", "raw_json": encode({"label": "A"}), "text": "alpha"},
			{"id": "b", "type_path": "/b", "raw_json": encode({"label": "B"}), "text": "beta"},
		])

		health = store_health(self.repo_root)
		self.assertEqual(health["tables"]["catalog_targets"], 2)
		self.assertEqual(health["total_rows"], 2)
		self.assertGreater(health["disk_bytes"], 0)
		self.assertIsNotNone(health["last_write_time"])

	def test_last_write_time_is_read_from_disk_not_an_in_memory_counter(self) -> None:
		"""Tool runs execute inside a separate worker process (see `webapp/store_worker.py`) from
		whatever calls `store_health` (the main HTTP server) -- an in-memory timestamp kept by one
		process would never see the other's writes, so this must come from on-disk file mtimes instead."""
		targets = legacy_table(self.repo_root, "catalog_targets")
		db.upsert_rows(targets, "id", [{"id": "a", "type_path": "/a", "raw_json": encode({}), "text": "alpha"}])

		# Simulate "a different process wrote this": drop this process's in-memory generation state and
		# confirm store_health still reports a last-write time purely from what's on disk.
		db._generation = 0
		health = store_health(self.repo_root)
		self.assertIsNotNone(health["last_write_time"])

	def test_reports_visible_keyword_only_mode_when_embeddings_are_unavailable(self) -> None:
		with patch("webapp.store.embeddings._model", None):
			health = store_health(self.repo_root)

		self.assertEqual(health["semantic_search"]["mode"], "keyword-only")
		self.assertEqual(health["semantic_search"]["model_id"], "BAAI/bge-small-en-v1.5")
		self.assertTrue(health["semantic_search"]["reason"])

	def test_reports_whether_the_projection_matches_canonical_content(self) -> None:
		path = record_path(self.repo_root, "group", "items")
		payload = {"id": "items", "label": "Items", "color": "#fff", "keywords": [], "type_path_prefixes": []}
		atomic_write_record(path, payload)
		reconcile_projection(self.repo_root)

		self.assertTrue(store_health(self.repo_root)["projection"]["current"])
		atomic_write_record(path, {**payload, "label": "Changed"})
		changed = store_health(self.repo_root)["projection"]
		self.assertFalse(changed["current"])
		self.assertIn("Canonical content changed", changed["reason"])


if __name__ == "__main__":
	unittest.main()

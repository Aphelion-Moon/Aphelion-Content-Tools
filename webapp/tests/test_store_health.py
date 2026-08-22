from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from webapp.store import db
from webapp.store.health import store_health
from webapp.store.schema import TABLE_SCHEMAS, encode, table


class StoreHealthTests(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp_dir.cleanup)
		self.repo_root = Path(self.temp_dir.name)

	def test_reports_zero_rows_for_every_table_on_a_fresh_store(self) -> None:
		# `store_health` opens every table via `table()`, which lazily creates it if it doesn't exist yet
		# (see `get_or_create_table`) -- so even a never-written-to store already has on-disk table
		# directories by the time health is checked, and a `last_write_time` reflecting their creation.
		health = store_health(self.repo_root)
		self.assertEqual(health["total_rows"], 0)
		self.assertEqual(set(health["tables"]), set(TABLE_SCHEMAS))
		self.assertTrue(all(count == 0 for count in health["tables"].values()))
		self.assertIsNotNone(health["last_write_time"])

	def test_last_write_time_is_none_when_the_store_directory_does_not_exist_at_all(self) -> None:
		from webapp.store.health import _directory_stats

		empty_size, empty_last_write = _directory_stats(self.repo_root / "does-not-exist")
		self.assertEqual(empty_size, 0)
		self.assertIsNone(empty_last_write)

	def test_reports_row_counts_disk_size_and_a_last_write_time_after_a_write(self) -> None:
		targets = table(self.repo_root, "catalog_targets")
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
		targets = table(self.repo_root, "catalog_targets")
		db.upsert_rows(targets, "id", [{"id": "a", "type_path": "/a", "raw_json": encode({}), "text": "alpha"}])

		# Simulate "a different process wrote this": drop this process's in-memory generation state and
		# confirm store_health still reports a last-write time purely from what's on disk.
		db._generation = 0
		health = store_health(self.repo_root)
		self.assertIsNotNone(health["last_write_time"])


if __name__ == "__main__":
	unittest.main()

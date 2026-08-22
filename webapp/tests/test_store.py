from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from webapp.store import db, search
from webapp.store.schema import decode, encode, table


class StoreTests(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp_dir.cleanup)
		self.repo_root = Path(self.temp_dir.name)

	def test_upsert_then_get_and_list(self) -> None:
		targets = table(self.repo_root, "catalog_targets")
		db.upsert_rows(targets, "id", [
			{"id": "/obj/item/radio", "type_path": "/obj/item/radio", "raw_json": encode({"type_path": "/obj/item/radio", "label": "Radio"}), "text": "Radio radio device"},
		])
		row = db.get_row(targets, "id = '/obj/item/radio'")
		self.assertIsNotNone(row)
		self.assertEqual(decode(row)["label"], "Radio")
		self.assertEqual(len(db.all_rows(targets)), 1)

	def test_upsert_is_an_update_when_the_key_already_exists(self) -> None:
		targets = table(self.repo_root, "catalog_targets")
		db.upsert_rows(targets, "id", [
			{"id": "a", "type_path": "/a", "raw_json": encode({"label": "Old"}), "text": "old"},
		])
		db.upsert_rows(targets, "id", [
			{"id": "a", "type_path": "/a", "raw_json": encode({"label": "New"}), "text": "new"},
		])
		self.assertEqual(len(db.all_rows(targets)), 1)
		row = db.get_row(targets, "id = 'a'")
		self.assertEqual(decode(row)["label"], "New")

	def test_replace_all_rows_clears_and_rewrites(self) -> None:
		nodes = table(self.repo_root, "graph_nodes")
		db.replace_all_rows(nodes, [
			{"id": "n1", "kind": "module", "path": "modular_aphelion/modules/x", "raw_json": encode({"id": "n1"}), "text": "n1"},
		])
		self.assertEqual(len(db.all_rows(nodes)), 1)
		db.replace_all_rows(nodes, [
			{"id": "n2", "kind": "module", "path": "modular_aphelion/modules/y", "raw_json": encode({"id": "n2"}), "text": "n2"},
		])
		rows = db.all_rows(nodes)
		self.assertEqual([row["id"] for row in rows], ["n2"])

	def test_delete_removes_a_row(self) -> None:
		overrides = table(self.repo_root, "overrides")
		db.upsert_rows(overrides, "id", [
			{"id": "o1", "type_path": "/obj/item/radio", "group": "items", "raw_json": encode({"id": "o1"}), "text": "radio override"},
		])
		overrides.delete("id = 'o1'")
		self.assertEqual(db.all_rows(overrides), [])

	def test_search_finds_keyword_matches_across_requested_tables(self) -> None:
		targets = table(self.repo_root, "catalog_targets")
		db.upsert_rows(targets, "id", [
			{"id": "/obj/item/radio", "type_path": "/obj/item/radio", "raw_json": encode({"label": "Radio"}), "text": "Radio a device used to project your voice"},
			{"id": "/obj/item/megaphone", "type_path": "/obj/item/megaphone", "raw_json": encode({"label": "Megaphone"}), "text": "Megaphone a loud voice projector"},
		])
		hits = search.search(self.repo_root, "megaphone", tables=["catalog_targets"])
		self.assertTrue(any(hit["id"] == "/obj/item/megaphone" for hit in hits))

	def test_search_rejects_an_unknown_table(self) -> None:
		with self.assertRaises(ValueError):
			search.search(self.repo_root, "radio", tables=["not_a_real_table"])

	def test_search_returns_nothing_for_a_blank_query(self) -> None:
		self.assertEqual(search.search(self.repo_root, "   "), [])

	def test_sync_snapshot_only_embeds_new_or_changed_rows(self) -> None:
		targets = table(self.repo_root, "catalog_targets")
		db.sync_snapshot(targets, "id", [
			{"id": "a", "type_path": "/a", "raw_json": encode({"label": "A"}), "text": "alpha"},
			{"id": "b", "type_path": "/b", "raw_json": encode({"label": "B"}), "text": "bravo"},
		])
		self.assertEqual(len(db.all_rows(targets)), 2)

		with patch("webapp.store.db.embed_texts", wraps=db.embed_texts) as embed_spy:
			db.sync_snapshot(targets, "id", [
				{"id": "a", "type_path": "/a", "raw_json": encode({"label": "A"}), "text": "alpha"},  # unchanged
				{"id": "b", "type_path": "/b", "raw_json": encode({"label": "B2"}), "text": "bravo two"},  # changed
				{"id": "c", "type_path": "/c", "raw_json": encode({"label": "C"}), "text": "charlie"},  # new
			])
			embedded_texts = [text for call in embed_spy.call_args_list for text in call.args[0]]
			self.assertEqual(sorted(embedded_texts), ["bravo two", "charlie"])

		rows = {row["id"]: decode(row) for row in db.all_rows(targets)}
		self.assertEqual(set(rows), {"a", "b", "c"})
		self.assertEqual(rows["b"]["label"], "B2")

	def test_sync_snapshot_deletes_rows_absent_from_the_new_snapshot(self) -> None:
		targets = table(self.repo_root, "catalog_targets")
		db.sync_snapshot(targets, "id", [
			{"id": "a", "type_path": "/a", "raw_json": encode({}), "text": "alpha"},
			{"id": "b", "type_path": "/b", "raw_json": encode({}), "text": "bravo"},
		])
		db.sync_snapshot(targets, "id", [
			{"id": "a", "type_path": "/a", "raw_json": encode({}), "text": "alpha"},
		])
		self.assertEqual([row["id"] for row in db.all_rows(targets)], ["a"])

	def test_sync_snapshot_chunks_and_reports_progress(self) -> None:
		targets = table(self.repo_root, "catalog_targets")
		rows = [
			{"id": str(i), "type_path": f"/{i}", "raw_json": encode({}), "text": f"item {i}"}
			for i in range(5)
		]
		progress_calls = []
		db.sync_snapshot(targets, "id", rows, chunk_size=2, on_progress=lambda done, total: progress_calls.append((done, total)))

		self.assertEqual(progress_calls, [(2, 5), (4, 5), (5, 5)])
		self.assertEqual(len(db.all_rows(targets)), 5)

	def test_sync_snapshot_skips_embedding_entirely_when_nothing_changed(self) -> None:
		targets = table(self.repo_root, "catalog_targets")
		db.sync_snapshot(targets, "id", [
			{"id": "a", "type_path": "/a", "raw_json": encode({}), "text": "alpha"},
		])
		with patch("webapp.store.db.embed_texts") as embed_spy:
			db.sync_snapshot(targets, "id", [
				{"id": "a", "type_path": "/a", "raw_json": encode({}), "text": "alpha"},
			])
			embed_spy.assert_not_called()

	def test_optimize_all_tables_calls_optimize_once_per_table(self) -> None:
		from webapp.store.schema import TABLE_SCHEMAS

		# Seed one table so `get_or_create_table` has already created every table by the time optimize
		# runs (it creates any table it hasn't seen yet, same as every other store entry point).
		for name in TABLE_SCHEMAS:
			table(self.repo_root, name)

		with patch("lancedb.table.LanceTable.optimize") as optimize_spy:
			names = db.optimize_all_tables(self.repo_root)

		self.assertEqual(names, list(TABLE_SCHEMAS))
		self.assertEqual(optimize_spy.call_count, len(TABLE_SCHEMAS))

	def test_optimize_all_tables_reports_progress_per_table(self) -> None:
		from webapp.store.schema import TABLE_SCHEMAS

		for name in TABLE_SCHEMAS:
			table(self.repo_root, name)

		progress_calls = []
		with patch("lancedb.table.Table.optimize"):
			db.optimize_all_tables(self.repo_root, on_progress=lambda name, done, total: progress_calls.append((name, done, total)))

		self.assertEqual(len(progress_calls), len(TABLE_SCHEMAS))
		self.assertEqual(progress_calls[-1][1:], (len(TABLE_SCHEMAS), len(TABLE_SCHEMAS)))


if __name__ == "__main__":
	unittest.main()

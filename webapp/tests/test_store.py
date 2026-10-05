from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa

from tools.lore_editor.records import atomic_write_record, record_path
from tools.lore_editor.tests.store_helpers import legacy_table
from webapp.store import db, search
from webapp.store.embeddings import EmbeddingStatus
from webapp.store.generations import staged_projection
from webapp.store.schema import CATALOG_TARGETS_SCHEMA, decode, encode, table
from webapp.store.search import SearchContext


class StoreTests(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp_dir.cleanup)
		self.repo_root = Path(self.temp_dir.name)

	def test_connections_check_cross_process_updates_on_every_read(self) -> None:
		with patch("webapp.store.db.lancedb.connect", return_value=object()) as connect:
			db.connect(self.repo_root)
		connect.assert_called_once_with(
			str(db.store_path(self.repo_root)),
			read_consistency_interval=timedelta(0),
		)

	def test_open_table_observes_a_write_from_another_process(self) -> None:
		connection = db.connect(self.repo_root)
		table = connection.create_table("freshness", data=[{"id": "initial"}])
		script = (
			"import lancedb,sys; "
			"table=lancedb.connect(sys.argv[1]).open_table('freshness'); "
			"table.add([{'id':'external'}])"
		)
		subprocess.run(
			[sys.executable, "-c", script, str(db.store_path(self.repo_root))],
			check=True,
			capture_output=True,
			text=True,
		)
		self.assertEqual({row["id"] for row in table.search().to_list()}, {"initial", "external"})

	def test_upsert_then_get_and_list(self) -> None:
		targets = legacy_table(self.repo_root, "catalog_targets")
		db.upsert_rows(targets, "id", [
			{"id": "/obj/item/radio", "type_path": "/obj/item/radio", "raw_json": encode({"type_path": "/obj/item/radio", "label": "Radio"}), "text": "Radio radio device"},
		])
		row = db.get_row(targets, "id = '/obj/item/radio'")
		self.assertIsNotNone(row)
		self.assertEqual(decode(row)["label"], "Radio")
		self.assertEqual(len(db.all_rows(targets)), 1)

	def test_schema_upgrade_happens_in_a_stage_without_modifying_the_source(self) -> None:
		connection = db.connect(self.repo_root)
		connection.create_table(
			"catalog_targets",
			schema=pa.schema([
				pa.field("id", pa.string()),
				pa.field("type_path", pa.string()),
				pa.field("raw_json", pa.string()),
				db.TEXT_FIELD,
				db.CONTENT_HASH_FIELD,
				db.VECTOR_FIELD,
			]),
		)

		opened = table(self.repo_root, "catalog_targets")

		self.assertNotIn("record_hash", opened.schema.names)
		self.assertNotIn("embedding_hash", opened.schema.names)
		with staged_projection(self.repo_root, content_revision="migration", changed_tables=()):
			pass
		upgraded = table(self.repo_root, "catalog_targets")
		self.assertIn("record_hash", upgraded.schema.names)
		self.assertIn("embedding_hash", upgraded.schema.names)
		self.assertNotIn("record_hash", connection.open_table("catalog_targets").schema.names)

	def test_upsert_is_an_update_when_the_key_already_exists(self) -> None:
		targets = legacy_table(self.repo_root, "catalog_targets")
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
		nodes = legacy_table(self.repo_root, "graph_nodes")
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
		overrides = legacy_table(self.repo_root, "overrides")
		db.upsert_rows(overrides, "id", [
			{"id": "o1", "type_path": "/obj/item/radio", "group": "items", "raw_json": encode({"id": "o1"}), "text": "radio override"},
		])
		overrides.delete("id = 'o1'")
		self.assertEqual(db.all_rows(overrides), [])

	def test_delete_row_by_key_treats_predicate_text_as_data(self) -> None:
		overrides = legacy_table(self.repo_root, "overrides")
		db.upsert_rows(overrides, "id", [
			{"id": "items.radio", "type_path": "/obj/item/radio", "group": "items", "raw_json": encode({"id": "items.radio"}), "text": "radio override"},
			{"id": "items.megaphone", "type_path": "/obj/item/megaphone", "group": "items", "raw_json": encode({"id": "items.megaphone"}), "text": "megaphone override"},
		])

		db.delete_row_by_key(overrides, "id", "missing' OR true OR id = 'items.radio")

		self.assertEqual(
			{row["id"] for row in db.all_rows(overrides)},
			{"items.radio", "items.megaphone"},
		)

	def test_search_finds_keyword_matches_across_requested_tables(self) -> None:
		targets = legacy_table(self.repo_root, "catalog_targets")
		db.upsert_rows(targets, "id", [
			{"id": "/obj/item/radio", "type_path": "/obj/item/radio", "raw_json": encode({"label": "Radio"}), "text": "Radio a device used to project your voice"},
			{"id": "/obj/item/megaphone", "type_path": "/obj/item/megaphone", "raw_json": encode({"label": "Megaphone"}), "text": "Megaphone a loud voice projector"},
		])
		hits = search.search(self.repo_root, "megaphone", tables=["catalog_targets"])
		self.assertTrue(any(hit["id"] == "/obj/item/megaphone" for hit in hits.results))

	def test_search_rejects_an_unknown_table(self) -> None:
		with self.assertRaises(ValueError):
			search.search(self.repo_root, "radio", tables=["not_a_real_table"])

	def test_search_returns_nothing_for_a_blank_query(self) -> None:
		report = search.search(self.repo_root, "   ")
		self.assertEqual(report.results, ())

	def test_search_pins_all_table_reads_to_one_store_generation(self) -> None:
		class EmptyQuery:
			def limit(self, _limit):
				return self

			def to_list(self):
				return []

		class RecordingTable:
			def search(self, _query, *, query_type):
				return EmptyQuery()

		pinned_store = self.repo_root / "webapp" / "store" / "projections" / "pinned"
		store_dirs = []

		def fake_table(_repo_root, _name, *, store_dir=None):
			store_dirs.append(store_dir)
			return RecordingTable()

		with (
			patch("webapp.store.search.store_path", return_value=pinned_store) as store_path_spy,
			patch("webapp.store.search.table", side_effect=fake_table),
			patch("webapp.store.search.embedding_status", return_value=EmbeddingStatus(False, "test-model", "offline")),
		):
			search.search(self.repo_root, "radio", tables=["catalog_targets", "groups"])

		store_path_spy.assert_called_once_with(self.repo_root)
		self.assertEqual(store_dirs, [pinned_store, pinned_store])

	def test_search_applies_one_global_limit_and_embeds_the_query_once(self) -> None:
		def fake_channels(_repo_root, name, _query, _limit, _query_vector, **_kwargs):
			rows = [
				{"id": f"{name}-{index}", "raw_json": encode({"id": f"{name}-{index}", "label": "Radio"}), "_score": 10 - index, "_distance": index / 10}
				for index in range(6)
			]
			return rows, rows

		with (
			patch("webapp.store.search.embedding_status", return_value=EmbeddingStatus(True, "test-model")),
			patch("webapp.store.search.embed_texts", return_value=[[0.0] * 384]) as embed_spy,
			patch("webapp.store.search._search_table_channels", side_effect=fake_channels),
		):
			report = search.search(self.repo_root, "radio", tables=["catalog_targets", "groups"], limit=6)

		self.assertEqual(len(report.results), 6)
		embed_spy.assert_called_once_with(["radio"])

	def test_search_context_boosts_related_close_matches_without_filtering_global_results(self) -> None:
		stronger = {
			"id": "stronger",
			"raw_json": encode({"id": "stronger", "label": "Radio station", "type_path": "/area/radio_station"}),
			"_score": 11.0,
			"_distance": 0.01,
		}
		unrelated = {
			"id": "unrelated",
			"raw_json": encode({"id": "unrelated", "label": "Radio handbook", "type_path": "/obj/item/book/radio"}),
			"_score": 10.0,
		}
		related = {
			"id": "related",
			"raw_json": encode({"id": "related", "label": "Radio headset", "type_path": "/obj/item/radio/headset"}),
			"_score": 9.9,
		}
		with (
			patch("webapp.store.search.embedding_status", return_value=EmbeddingStatus(True, "test-model")),
			patch("webapp.store.search.embed_texts", return_value=[[0.0] * 384]),
			patch("webapp.store.search._search_table_channels", return_value=([stronger, unrelated, related], [stronger])),
		):
			report = search.search(
				self.repo_root,
				"radio",
				tables=["catalog_targets"],
				context=SearchContext(type_path="/obj/item/radio"),
				limit=3,
			)

		self.assertEqual([result["id"] for result in report.results], ["stronger", "related", "unrelated"])
		self.assertGreater(report.results[1]["scores"]["context_boost"], 0)
		self.assertIsNotNone(report.results[1]["context_reason"])

	def test_search_uses_deterministic_table_priority_and_id_tie_breaking(self) -> None:
		rows = {
			"groups": [
				{"id": "zeta", "raw_json": encode({"id": "zeta"}), "_score": 1.0},
				{"id": "alpha", "raw_json": encode({"id": "alpha"}), "_score": 1.0},
			],
			"catalog_targets": [
				{"id": "target", "raw_json": encode({"id": "target"}), "_score": 1.0},
			],
		}

		def fake_channels(_repo_root, name, _query, _limit, _query_vector, **_kwargs):
			return rows[name], []

		with (
			patch("webapp.store.search.embedding_status", return_value=EmbeddingStatus(False, "test-model", "offline")),
			patch("webapp.store.search._search_table_channels", side_effect=fake_channels),
		):
			report = search.search(self.repo_root, "same", tables=["groups", "catalog_targets"], limit=3)

		self.assertEqual(
			[(result["table"], result["id"]) for result in report.results],
			[("catalog_targets", "target"), ("groups", "alpha"), ("groups", "zeta")],
		)

	def test_search_reports_keyword_only_mode_and_exact_navigation(self) -> None:
		row = {
			"id": "/obj/item/radio",
			"raw_json": encode({"label": "Radio", "type_path": "/obj/item/radio"}),
			"_score": 4.0,
		}
		with (
			patch("webapp.store.search.embedding_status", return_value=EmbeddingStatus(False, "test-model", "offline")),
			patch("webapp.store.search.embed_texts") as embed_spy,
			patch("webapp.store.search._search_table_channels", return_value=([row], [])),
		):
			report = search.search(self.repo_root, "radio", tables=["catalog_targets"])

		self.assertEqual(report.semantic_mode, "keyword-only")
		self.assertEqual(report.semantic_reason, "offline")
		embed_spy.assert_not_called()
		self.assertEqual(report.results[0]["scores"]["semantic_rrf"], 0)
		self.assertEqual(report.results[0]["navigation"]["route"], "/lore-editor")
		self.assertEqual(report.results[0]["navigation"]["type_path"], "/obj/item/radio")

	def test_graph_search_does_not_run_a_vector_channel_for_keyword_only_tables(self) -> None:
		class EmptyQuery:
			def limit(self, _limit):
				return self

			def to_list(self):
				return []

		class RecordingTable:
			def __init__(self) -> None:
				self.query_types = []

			def search(self, _query, *, query_type):
				self.query_types.append(query_type)
				return EmptyQuery()

		target = RecordingTable()
		with patch("webapp.store.search.table", return_value=target):
			search._search_table_channels(self.repo_root, "graph_nodes", "radio", 20, [0.0] * 384)

		self.assertEqual(target.query_types, ["fts"])

	def test_graph_only_search_does_not_embed_and_reports_keyword_only_mode(self) -> None:
		with (
			patch("webapp.store.search.embedding_status", return_value=EmbeddingStatus(True, "test-model", None)),
			patch("webapp.store.search.embed_texts") as embed_spy,
			patch("webapp.store.search._search_table_channels", return_value=([], [])),
		):
			report = search.search(self.repo_root, "radio", tables=["graph_nodes"])

		self.assertEqual(report.semantic_mode, "keyword-only")
		self.assertEqual(report.semantic_reason, "Selected tables use keyword search.")
		embed_spy.assert_not_called()

	def test_sync_snapshot_only_embeds_new_or_changed_rows(self) -> None:
		targets = legacy_table(self.repo_root, "catalog_targets")
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

	def test_sync_snapshot_updates_complete_records_without_reembedding_unchanged_text(self) -> None:
		targets = legacy_table(self.repo_root, "catalog_targets")
		db.sync_snapshot(targets, "id", [{
			"id": "a",
			"type_path": "/a",
			"raw_json": encode({"label": "A", "field_profile": "old"}),
			"text": "alpha",
		}])

		with patch("webapp.store.db.embed_texts") as embed_spy:
			db.sync_snapshot(targets, "id", [{
				"id": "a",
				"type_path": "/a",
				"raw_json": encode({"label": "A", "field_profile": "new"}),
				"text": "alpha",
			}])
			embed_spy.assert_not_called()

		row = db.get_row_by_key(targets, "id", "a")
		self.assertEqual(decode(row)["field_profile"], "new")

	def test_sync_snapshot_reembeds_when_the_embedding_model_changes(self) -> None:
		targets = legacy_table(self.repo_root, "catalog_targets")
		row = {"id": "a", "type_path": "/a", "raw_json": encode({"label": "A"}), "text": "alpha"}
		db.sync_snapshot(targets, "id", [row])

		with patch("webapp.store.db.embed_texts", wraps=db.embed_texts) as embed_spy:
			db.sync_snapshot(targets, "id", [row], embedding_model_id="test-model-v2")
			self.assertEqual([call.args[0] for call in embed_spy.call_args_list], [["alpha"]])

		stored = db.get_row_by_key(targets, "id", "a")
		self.assertEqual(stored["embedding_hash"], db.embedding_hash_for("alpha", "test-model-v2"))

	def test_rebuild_embeddings_preserves_vectors_when_the_model_is_unavailable(self) -> None:
		from webapp.store.cli import rebuild_embeddings
		from webapp.store.embeddings import EmbeddingUnavailableError

		targets = legacy_table(self.repo_root, "catalog_targets")
		db.upsert_rows(targets, "id", [
			{"id": "a", "type_path": "/a", "raw_json": encode({"label": "A"}), "text": "alpha"},
		])
		original_vector = db.get_row_by_key(targets, "id", "a")["vector"]

		with (
			patch("webapp.store.embeddings._load_model", return_value=None),
			self.assertRaises(EmbeddingUnavailableError),
		):
			rebuild_embeddings(self.repo_root)

		self.assertEqual(db.get_row_by_key(targets, "id", "a")["vector"], original_vector)

	def test_rebuild_embeddings_reconciles_external_canonical_changes_before_staging(self) -> None:
		from webapp.store import cli as store_cli

		atomic_write_record(record_path(self.repo_root, "group", "items"), {
			"id": "items",
			"label": "Items",
			"color": "#fff",
			"keywords": [],
			"type_path_prefixes": [],
		})
		with (
			patch.object(store_cli, "embeddings_available", return_value=True),
			patch.object(store_cli, "with_embeddings", side_effect=lambda rows: [
				{**row, "vector": [0.0] * 384} for row in rows
			]),
		):
			store_cli.rebuild_embeddings(self.repo_root)

		self.assertIsNotNone(db.get_row_by_key(table(self.repo_root, "groups"), "id", "items"))

	def test_rebuild_embeddings_reads_and_updates_one_bounded_chunk_at_a_time(self) -> None:
		from webapp.store import cli as store_cli

		rows = [
			{"id": str(index), "type_path": f"/{index}", "raw_json": encode({}), "text": f"item {index}"}
			for index in range(5)
		]

		class FakeQuery:
			def __init__(self, owner) -> None:
				self.owner = owner
				self.columns = None
				self.predicate = None

			def select(self, columns):
				self.columns = columns
				return self

			def where(self, predicate):
				self.predicate = predicate
				return self

			def to_list(self):
				if self.columns == ["id"]:
					return [{"id": row["id"]} for row in rows]
				if self.predicate is None:
					raise AssertionError("Rebuild loaded every full row in one query.")
				return self.owner.pending_chunks.pop(0)

		class FakeMerge:
			def when_matched_update_all(self):
				return self

			def when_not_matched_insert_all(self):
				return self

			def execute(self, values):
				self.values = values

		class FakeTable:
			def __init__(self) -> None:
				self.pending_chunks = [rows[:2], rows[2:4], rows[4:]]
				self.schema = type("Schema", (), {"names": [*rows[0], "vector"]})()
				self.merges = []

			def search(self):
				return FakeQuery(self)

			def merge_insert(self, key):
				merge = FakeMerge()
				self.merges.append(merge)
				return merge

		targets = FakeTable()
		progress = []
		with (
			patch.object(store_cli, "TABLE_SCHEMAS", {"catalog_targets": CATALOG_TARGETS_SCHEMA}),
			patch("webapp.store.schema.TABLE_SCHEMAS", {"catalog_targets": CATALOG_TARGETS_SCHEMA}),
			patch.object(store_cli, "KEYWORD_ONLY_TABLES", frozenset()),
			patch.object(store_cli, "SYNC_CHUNK_SIZE", 2),
			patch.object(store_cli, "writable_table", return_value=targets),
			patch.object(store_cli, "embeddings_available", return_value=True),
			patch.object(store_cli, "with_embeddings", side_effect=lambda values: [{**value, "vector": []} for value in values]),
		):
			counts = store_cli.rebuild_embeddings(
				self.repo_root,
				on_progress=lambda name, done, total: progress.append((name, done, total)),
			)

		self.assertEqual(counts, {"catalog_targets": 5})
		self.assertEqual(progress, [("catalog_targets", 2, 5), ("catalog_targets", 4, 5), ("catalog_targets", 5, 5)])
		self.assertEqual([len(merge.values) for merge in targets.merges], [2, 2, 1])

	def test_sync_snapshot_deletes_rows_absent_from_the_new_snapshot(self) -> None:
		targets = legacy_table(self.repo_root, "catalog_targets")
		db.sync_snapshot(targets, "id", [
			{"id": "a", "type_path": "/a", "raw_json": encode({}), "text": "alpha"},
			{"id": "b", "type_path": "/b", "raw_json": encode({}), "text": "bravo"},
		])
		db.sync_snapshot(targets, "id", [
			{"id": "a", "type_path": "/a", "raw_json": encode({}), "text": "alpha"},
		])
		self.assertEqual([row["id"] for row in db.all_rows(targets)], ["a"])

	def test_sync_snapshot_treats_stale_ids_as_data(self) -> None:
		targets = legacy_table(self.repo_root, "catalog_targets")
		malicious_id = "missing') OR true OR id IN ('a"
		initial_rows = [
			{"id": "a", "type_path": "/a", "raw_json": encode({}), "text": "alpha"},
			{"id": "b", "type_path": "/b", "raw_json": encode({}), "text": "bravo"},
			{"id": malicious_id, "type_path": "/malicious", "raw_json": encode({}), "text": "malicious"},
		]
		db.sync_snapshot(targets, "id", initial_rows)

		db.sync_snapshot(targets, "id", initial_rows[:2])

		self.assertEqual({row["id"] for row in db.all_rows(targets)}, {"a", "b"})

	def test_sync_snapshot_chunks_and_reports_progress(self) -> None:
		targets = legacy_table(self.repo_root, "catalog_targets")
		rows = [
			{"id": str(i), "type_path": f"/{i}", "raw_json": encode({}), "text": f"item {i}"}
			for i in range(5)
		]
		progress_calls = []
		db.sync_snapshot(targets, "id", rows, chunk_size=2, on_progress=lambda done, total: progress_calls.append((done, total)))

		self.assertEqual(progress_calls, [(2, 5), (4, 5), (5, 5)])
		self.assertEqual(len(db.all_rows(targets)), 5)

	def test_sync_snapshot_skips_embedding_entirely_when_nothing_changed(self) -> None:
		targets = legacy_table(self.repo_root, "catalog_targets")
		db.sync_snapshot(targets, "id", [
			{"id": "a", "type_path": "/a", "raw_json": encode({}), "text": "alpha"},
		])
		with patch("webapp.store.db.embed_texts") as embed_spy:
			db.sync_snapshot(targets, "id", [
				{"id": "a", "type_path": "/a", "raw_json": encode({}), "text": "alpha"},
			])
			embed_spy.assert_not_called()

	def test_sync_snapshot_can_store_keyword_only_rows_without_embedding(self) -> None:
		nodes = legacy_table(self.repo_root, "graph_nodes")
		with patch("webapp.store.db.embed_texts", side_effect=AssertionError("embedding should be skipped")):
			db.sync_snapshot(nodes, "id", [{
				"id": "file:code/radio.dm",
				"kind": "file",
				"path": "code/radio.dm",
				"raw_json": encode({"id": "file:code/radio.dm", "kind": "file"}),
				"text": "file code radio dm",
			}], embed=False)

		stored = db.get_row_by_key(nodes, "id", "file:code/radio.dm")
		self.assertEqual(stored["vector"], [0.0] * 384)

	def test_optimize_all_tables_calls_optimize_once_per_table(self) -> None:
		from webapp.store.schema import TABLE_SCHEMAS

		# Create explicit writable fixtures before the maintenance operation stages them.
		for name in TABLE_SCHEMAS:
			legacy_table(self.repo_root, name)

		with patch("lancedb.table.LanceTable.optimize") as optimize_spy:
			names = db.optimize_all_tables(self.repo_root)

		self.assertEqual(names, list(TABLE_SCHEMAS))
		self.assertEqual(optimize_spy.call_count, len(TABLE_SCHEMAS))

	def test_optimize_all_tables_reconciles_external_canonical_changes_before_staging(self) -> None:
		from webapp.store.schema import TABLE_SCHEMAS

		atomic_write_record(record_path(self.repo_root, "group", "items"), {
			"id": "items",
			"label": "Items",
			"color": "#fff",
			"keywords": [],
			"type_path_prefixes": [],
		})
		for name in TABLE_SCHEMAS:
			legacy_table(self.repo_root, name)

		with patch("lancedb.table.LanceTable.optimize"):
			db.optimize_all_tables(self.repo_root)

		self.assertIsNotNone(db.get_row_by_key(table(self.repo_root, "groups"), "id", "items"))

	def test_optimize_all_tables_reports_progress_per_table(self) -> None:
		from webapp.store.schema import TABLE_SCHEMAS

		for name in TABLE_SCHEMAS:
			legacy_table(self.repo_root, name)

		progress_calls = []
		with patch("lancedb.table.Table.optimize"):
			db.optimize_all_tables(self.repo_root, on_progress=lambda name, done, total: progress_calls.append((name, done, total)))

		self.assertEqual(len(progress_calls), len(TABLE_SCHEMAS))
		self.assertEqual(progress_calls[-1][1:], (len(TABLE_SCHEMAS), len(TABLE_SCHEMAS)))


if __name__ == "__main__":
	unittest.main()

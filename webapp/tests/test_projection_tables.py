from __future__ import annotations

import gc
import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from webapp.store import db, schema
from webapp.store.embeddings import EMBEDDING_MODEL_NAME
from webapp.store.generations import staged_projection
from webapp.store.health import store_health
from webapp.store.lifecycle import read_projection, retire_projections
from webapp.store.metadata import active_projection, backup_projection, restore_projection


class ProjectionTableTests(unittest.TestCase):
	def setUp(self) -> None:
		self.temporary = tempfile.TemporaryDirectory()
		self.addCleanup(self.temporary.cleanup)
		self.repo_root = Path(self.temporary.name)
		model = patch("webapp.store.embeddings._load_model", return_value=None)
		model.start()
		self.addCleanup(model.stop)

	def row(self, key: str) -> dict[str, object]:
		return {"id": key, "raw_json": schema.encode({"id": key}), "text": key}

	def legacy_table(self, name: str):
		return db.get_or_create_table(self.repo_root, name, schema.TABLE_SCHEMAS[name])

	def publish(self, revision: str, names: tuple[str, ...] = ("groups",)):
		with staged_projection(self.repo_root, content_revision=revision, changed_tables=names) as staged:
			for name in names:
				db.sync_snapshot(schema.writable_table(self.repo_root, name, store_dir=staged.path), "id", [self.row(revision)], embed=False)
		return active_projection(self.repo_root)

	def test_missing_reads_do_not_create_a_store_or_table(self) -> None:
		self.assertIsNone(schema.table(self.repo_root, "groups"))
		self.assertEqual(db.all_rows(schema.table(self.repo_root, "groups")), [])
		self.assertIsNone(db.get_row_by_key(schema.table(self.repo_root, "groups"), "id", "missing"))
		self.assertFalse((self.repo_root / "webapp/store").exists())

	def test_published_read_handle_rejects_mutation(self) -> None:
		db.sync_snapshot(self.legacy_table("groups"), "id", [self.row("original")], embed=False)
		with staged_projection(self.repo_root, content_revision="first"):
			pass
		published = schema.table(self.repo_root, "groups")
		with self.assertRaisesRegex(Exception, "(?i)(read.only|checked.out|checkout|write|modif)"):
			published.delete("true")
		with self.assertRaisesRegex(AttributeError, "Read-only"):
			published.merge_insert("id")
		self.assertEqual([row["id"] for row in db.all_rows(published)], ["original"])

	def test_changed_table_is_copied_and_unchanged_table_keeps_its_owner(self) -> None:
		db.sync_snapshot(self.legacy_table("groups"), "id", [self.row("original")], embed=False)
		db.sync_snapshot(self.legacy_table("catalog_targets"), "id", [self.row("catalog")], embed=False)
		with staged_projection(self.repo_root, content_revision="first"):
			pass
		first = active_projection(self.repo_root)
		with staged_projection(self.repo_root, content_revision="second", changed_tables={"groups"}) as staged:
			db.sync_snapshot(schema.writable_table(self.repo_root, "groups", store_dir=staged.path), "id", [self.row("changed")], embed=False)
		second = active_projection(self.repo_root)
		self.assertFalse((second.path / "catalog_targets.lance").exists())
		self.assertEqual(second.metadata.table_owners["catalog_targets"], first.metadata.generation_id)
		self.assertEqual([row["id"] for row in db.all_rows(schema.table(self.repo_root, "catalog_targets"))], ["catalog"])
		self.assertEqual([row["id"] for row in db.all_rows(schema.table(self.repo_root, "groups", store_dir=first.path))], ["original"])
		self.assertEqual([row["id"] for row in db.all_rows(schema.table(self.repo_root, "groups"))], ["changed"])

	def test_backup_is_self_contained_after_table_owners_are_removed(self) -> None:
		db.sync_snapshot(self.legacy_table("groups"), "id", [self.row("original")], embed=False)
		with staged_projection(self.repo_root, content_revision="first"):
			pass
		with staged_projection(self.repo_root, content_revision="second", changed_tables=()):
			pass
		backup = self.repo_root / "backup"
		backup_projection(self.repo_root, backup, label="shared-tables")
		self.assertTrue((backup / "groups.lance").is_dir())
		# A different store cannot resolve any owner from the original repository.
		other_root = self.repo_root / "restored-workspace"
		restored = restore_projection(other_root, backup)
		self.assertEqual(restored.revision.state, "stale")
		self.assertEqual(set(restored.table_owners.values()), {restored.generation_id})
		self.assertEqual([row["id"] for row in db.all_rows(schema.table(other_root, "groups"))], ["original"])

	def test_stage_rejects_undeclared_writes_and_cannot_be_reopened_for_writing(self) -> None:
		with self.assertRaisesRegex(ValueError, "every semantic table"), staged_projection(
			self.repo_root, content_revision="partial", changed_tables={"groups"}, embeddings_rebuilt=True,
		):
			pass
		with (
			staged_projection(self.repo_root, content_revision="declared", changed_tables={"groups"}) as staged,
			self.assertRaisesRegex(ValueError, "not declared writable"),
		):
			schema.writable_table(self.repo_root, "catalog_targets", store_dir=staged.path)
		with self.assertRaisesRegex(ValueError, "not declared writable"):
			schema.writable_table(self.repo_root, "groups", store_dir=staged.path)
		with self.assertRaisesRegex(ValueError, "Published projection"):
			db.get_or_create_table(self.repo_root, "groups", schema.TABLE_SCHEMAS["groups"])

	def test_retained_writer_and_merge_builder_cannot_change_a_published_table(self) -> None:
		with staged_projection(self.repo_root, content_revision="held", changed_tables={"groups"}) as staged:
			held = schema.writable_table(self.repo_root, "groups", store_dir=staged.path)
			db.sync_snapshot(held, "id", [self.row("original")], embed=False)
			pending = held.merge_insert("id").when_matched_update_all().when_not_matched_insert_all()
		with self.assertRaisesRegex(Exception, "(?i)(read.only|checked.out|checkout|write|modif)"):
			held.delete("true")
		with self.assertRaisesRegex(Exception, "(?i)(read.only|checked.out|checkout|write|modif)"):
			pending.execute([{**self.row("late"), "vector": [0.0] * 384}])
		self.assertEqual([row["id"] for row in db.all_rows(schema.table(self.repo_root, "groups"))], ["original"])

	def test_partial_publication_preserves_old_vector_model_provenance_until_full_rebuild(self) -> None:
		from webapp.store import cli
		from webapp.store.metadata import projection_status

		with patch("webapp.store.metadata.EMBEDDING_MODEL_NAME", "previous-model"):
			first = self.publish("first", ("catalog_targets",))
		current = self.publish("changed", ("groups",))
		self.assertEqual(current.metadata.revision.embedding_model_id, "previous-model")
		self.assertFalse(projection_status(self.repo_root, "changed").current)
		self.assertEqual(current.metadata.table_owners["catalog_targets"], first.metadata.generation_id)
		with (
			patch.object(cli, "embeddings_available", return_value=True),
			patch.object(cli, "with_embeddings", side_effect=lambda rows: [{**row, "vector": [1.0] * 384} for row in rows]),
		):
			cli.rebuild_embeddings(self.repo_root)
		rebuilt = active_projection(self.repo_root)
		self.assertEqual(rebuilt.metadata.revision.embedding_model_id, EMBEDDING_MODEL_NAME)
		catalog_row = db.get_row_by_key(schema.table(self.repo_root, "catalog_targets"), "id", "first")
		self.assertEqual(catalog_row["vector"], [1.0] * 384)
		self.assertEqual(catalog_row["embedding_hash"], db.embedding_hash_for("first"))

	def test_health_counts_logical_tables_and_only_their_physical_files(self) -> None:
		self.publish("base", ("groups", "catalog_targets"))
		current = self.publish("changed")
		owners = current.metadata.table_owners
		root = current.path.parent
		expected_bytes = sum(
			path.stat().st_size
			for name, owner in owners.items()
			for path in (root / owner / f"{name}.lance").rglob("*") if path.is_file()
		)
		health = store_health(self.repo_root)
		self.assertEqual(health["total_rows"], 2)
		self.assertEqual(health["disk_bytes"], expected_bytes)
		self.assertNotIn("table_owners", health["projection"]["active"])

	def test_native_query_keeps_shared_physical_owner_without_retaining_its_old_dependencies(self) -> None:
		first = self.publish("first", ("groups",))
		second = self.publish("second", ("catalog_targets",))
		query = schema.table(self.repo_root, "catalog_targets").search()
		self.publish("third", ("groups", "catalog_targets"))
		self.publish("fourth", ("groups", "catalog_targets"))
		self.assertFalse(first.path.exists())
		self.assertTrue(second.path.exists())
		self.assertEqual([row["id"] for row in query.to_list()], ["second"])
		del query
		gc.collect()
		retire_projections(self.repo_root)
		self.assertFalse(second.path.exists())

	def test_logical_read_scope_keeps_old_shared_tables_across_publication(self) -> None:
		first = self.publish("first", ("catalog_targets",))
		second = self.publish("second", ("groups",))
		with read_projection(self.repo_root):
			self.publish("third", ("catalog_targets", "groups"))
			self.publish("fourth", ("catalog_targets", "groups"))
			self.assertTrue(first.path.exists())
			self.assertTrue(second.path.exists())
			self.assertEqual([row["id"] for row in db.all_rows(schema.table(self.repo_root, "catalog_targets"))], ["first"])
			self.assertEqual([row["id"] for row in db.all_rows(schema.table(self.repo_root, "groups"))], ["second"])
		retire_projections(self.repo_root)
		self.assertFalse(first.path.exists())
		self.assertFalse(second.path.exists())

	def test_cross_process_logical_lease_keeps_shared_owners(self) -> None:
		first = self.publish("first", ("catalog_targets",))
		second = self.publish("second", ("groups",))
		ready = self.repo_root / "reader-ready"
		script = "\n".join((
			"import sys",
			"from pathlib import Path",
			"from webapp.store.lifecycle import read_projection",
			"from webapp.store.metadata import projection_table_paths",
			"with read_projection(Path(sys.argv[1])) as pinned:",
			"    Path(sys.argv[2]).write_text(pinned.metadata.generation_id)",
			"    sys.stdin.readline()",
			"    assert len(projection_table_paths(Path(sys.argv[1]), pinned)) == 2",
		))
		process = subprocess.Popen(
			[sys.executable, "-W", "default", "-c", script, str(self.repo_root), str(ready)],
			stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
		)
		try:
			deadline = time.monotonic() + 10
			while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
				time.sleep(0.01)
			self.assertTrue(ready.exists(), "reader did not acquire its lease")
			self.publish("third", ("groups", "catalog_targets"))
			self.publish("fourth", ("groups", "catalog_targets"))
			self.assertTrue(first.path.exists())
			self.assertTrue(second.path.exists())
			output, _ = process.communicate(input="\n", timeout=10)
			self.assertEqual(process.returncode, 0, output)
			self.assertNotIn("ResourceWarning", output)
			retire_projections(self.repo_root)
			self.assertFalse(first.path.exists())
			self.assertFalse(second.path.exists())
		finally:
			if process.poll() is None:
				process.kill()
			process.communicate(timeout=5)

	def test_missing_declared_table_falls_back_to_previous_generation(self) -> None:
		previous = self.publish("previous")
		current = self.publish("current")
		marker = current.path / "projection.json"
		payload = json.loads(marker.read_text(encoding="utf-8"))
		payload["table_owners"]["catalog_targets"] = current.metadata.generation_id
		marker.write_text(json.dumps(payload), encoding="utf-8")
		(current.path.parent.parent / "active-projection.json").write_text(json.dumps(payload), encoding="utf-8")
		self.assertEqual(active_projection(self.repo_root), previous)

	def test_failed_backup_and_restore_remove_only_their_new_partial_destination(self) -> None:
		current = self.publish("base", ("groups", "catalog_targets"))
		backup = self.repo_root / "complete-backup"
		backup_projection(self.repo_root, backup, label="complete")
		copytree = shutil.copytree
		copies = 0

		def interrupted_copy(source, destination, *args, **kwargs):
			nonlocal copies
			if Path(source).suffix == ".lance":
				copies += 1
				if copies == 2:
					raise OSError("interrupted table copy")
			return copytree(source, destination, *args, **kwargs)

		failed_backup = self.repo_root / "failed-backup"
		with patch("webapp.store.metadata.shutil.copytree", side_effect=interrupted_copy), self.assertRaisesRegex(OSError, "interrupted table copy"):
			backup_projection(self.repo_root, failed_backup, label="incomplete")
		self.assertFalse(failed_backup.exists())
		original_directories = set(current.path.parent.iterdir())
		copies = 0
		with patch("webapp.store.metadata.shutil.copytree", side_effect=interrupted_copy), self.assertRaisesRegex(OSError, "interrupted table copy"):
			restore_projection(self.repo_root, backup)
		self.assertEqual(set(current.path.parent.iterdir()), original_directories)
		self.assertEqual(active_projection(self.repo_root), current)
		self.assertTrue((backup / "backup.json").is_file())

from __future__ import annotations

import gc
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from webapp.store import db
from webapp.store.generations import staged_projection
from webapp.store.lifecycle import read_projection, retire_projections
from webapp.store.metadata import active_projection_metadata, active_projection_path


class _Connection:
	pass


class ProjectionLifecycleTests(unittest.TestCase):
	def setUp(self) -> None:
		self.temporary = tempfile.TemporaryDirectory()
		self.addCleanup(self.temporary.cleanup)
		self.repo_root = Path(self.temporary.name)

	def publish(self, revision: str) -> Path:
		with staged_projection(self.repo_root, content_revision=revision) as staged:
			(staged.path / "fixture.txt").write_text(revision, encoding="utf-8")
		return staged.path

	def test_staging_retires_old_generations_but_keeps_previous_recovery(self) -> None:
		first = self.publish("first")
		second = self.publish("second")
		third = self.publish("third")

		self.assertFalse(first.exists())
		self.assertEqual((second / "fixture.txt").read_text(encoding="utf-8"), "second")
		self.assertEqual((third / "fixture.txt").read_text(encoding="utf-8"), "third")

	def test_connection_cache_evicts_least_recently_used_connection(self) -> None:
		with (
			patch.object(db, "_connections", OrderedDict()),
			patch.object(db, "MAX_CACHED_CONNECTIONS", 2, create=True),
			patch.object(db.lancedb, "connect", side_effect=lambda *_args, **_kwargs: _Connection()) as create,
		):
			first = db.connect(self.repo_root, store_dir=self.repo_root / "one")
			db.connect(self.repo_root, store_dir=self.repo_root / "two")
			self.assertIs(db.connect(self.repo_root, store_dir=self.repo_root / "one"), first)
			db.connect(self.repo_root, store_dir=self.repo_root / "three")
			db.connect(self.repo_root, store_dir=self.repo_root / "two")
			self.assertEqual(create.call_count, 4)

	def test_opening_a_retired_generation_does_not_recreate_it(self) -> None:
		missing = self.repo_root / "webapp/store/projections/retired"
		with (
			patch.object(db.lancedb, "connect", return_value=_Connection()) as create,
			self.assertRaises(FileNotFoundError),
		):
			db.connect(self.repo_root, store_dir=missing)
		create.assert_not_called()
		self.assertFalse(missing.exists())

	def test_review_response_uses_one_generation_for_rows_and_cache(self) -> None:
		from tools.lore_editor import api

		first = self.publish("first")
		observed = []
		cache_keys = []

		def load_corpus(root):
			observed.append(db.store_path(root))
			self.publish("second")
			self.publish("third")
			return object()

		def load_other(root):
			observed.append(db.store_path(root))
			return object()

		def snapshot(root, *_args, **_kwargs):
			cache_keys.append(api._store_cache_revision(root))
			return SimpleNamespace(
				review_entries=(), catalog_count=0, approved_count=0, review_count=0,
				status_counts={}, group_counts={}, groups_payload=(), issues_payload=(),
			)

		with (
			patch.object(api, "load_corpus", side_effect=load_corpus),
			patch.object(api, "load_groups", side_effect=load_other),
			patch.object(api, "load_reviews", side_effect=load_other),
			patch.object(api, "_review_entries_snapshot", side_effect=snapshot),
		):
			api.list_review_response(self.repo_root)

		self.assertEqual(observed, [first, first, first])
		self.assertEqual(cache_keys[0][1], first.name)

	def test_native_query_keeps_evicted_connection_generation_alive(self) -> None:
		with patch.object(db, "_connections", OrderedDict()):
			with staged_projection(self.repo_root, content_revision="native") as staged:
				connection = db.connect(self.repo_root, store_dir=staged.path)
				connection.create_table("fixture", data=[{"id": "old-row"}])
			first = staged.path
			query = connection.open_table("fixture").search()
			del connection
			db.discard_connection(first)
			self.publish("second")
			self.publish("third")

			self.assertTrue(first.exists())
			self.assertEqual(query.to_list(), [{"id": "old-row"}])
			del query
			gc.collect()
			retire_projections(self.repo_root)
			self.assertFalse(first.exists())

	def test_another_process_pin_survives_activation_and_is_reclaimed_after_exit(self) -> None:
		for crashed in (False, True):
			with self.subTest(crashed=crashed):
				first = self.publish("first")
				ready = self.repo_root / f"reader-ready-{crashed}"
				script = "\n".join((
					"import sys",
					"from pathlib import Path",
					"from webapp.store.lifecycle import read_projection",
					"with read_projection(Path(sys.argv[1])) as pinned:",
					"    Path(sys.argv[2]).write_text(str(pinned.path), encoding='utf-8')",
					"    sys.stdin.readline()",
					"    assert (pinned.path / 'fixture.txt').read_text(encoding='utf-8') == 'first'",
				))
				process = subprocess.Popen(
					[sys.executable, "-W", "default", "-c", script, str(self.repo_root), str(ready)],
					stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
				)
				try:
					deadline = time.monotonic() + 10
					while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
						time.sleep(0.01)
					self.assertTrue(ready.exists(), "reader did not acquire its projection lease")
					self.publish("second")
					self.publish("third")
					self.assertTrue(first.exists())
					if crashed:
						process.kill()
					output, _ = process.communicate(input=None if crashed else "\n", timeout=10)
					if not crashed:
						self.assertEqual(process.returncode, 0, output)
					self.assertNotIn("ResourceWarning", output)
					retire_projections(self.repo_root)
					self.assertFalse(first.exists())
				finally:
					if process.poll() is None:
						process.kill()
					process.communicate(timeout=5)

	def test_readers_do_not_wait_for_a_staged_writer(self) -> None:
		first = self.publish("first")
		staging = threading.Event()
		release = threading.Event()
		observed = []
		errors = []

		def writer():
			try:
				with staged_projection(self.repo_root, content_revision="second"):
					staging.set()
					if not release.wait(timeout=5):
						raise TimeoutError("reader was blocked by the writer")
			except Exception as exc:
				errors.append(exc)

		def reader():
			try:
				with read_projection(self.repo_root) as pinned:
					observed.append(pinned.path)
			except Exception as exc:
				errors.append(exc)

		writer_thread = threading.Thread(target=writer)
		reader_thread = threading.Thread(target=reader)
		writer_thread.start()
		try:
			self.assertTrue(staging.wait(timeout=3))
			reader_thread.start()
			reader_thread.join(timeout=2)
			self.assertFalse(reader_thread.is_alive())
			self.assertEqual(observed, [first])
		finally:
			release.set()
			writer_thread.join(timeout=5)
			if reader_thread.ident is not None:
				reader_thread.join(timeout=5)
		self.assertEqual(errors, [])

	def test_cleanup_failure_does_not_undo_activation_and_can_be_retried(self) -> None:
		first = self.publish("first")
		self.publish("second")
		with (
			patch("webapp.store.lifecycle.shutil.rmtree", side_effect=PermissionError("busy")),
			self.assertLogs("webapp.store.lifecycle", level="WARNING"),
		):
			third = self.publish("third")
		self.assertEqual(active_projection_path(self.repo_root), third)
		quarantined = first.parent / ".retired" / first.name
		self.assertTrue(quarantined.exists())
		retire_projections(self.repo_root)
		self.assertFalse(quarantined.exists())
		self.assertTrue(third.exists())

	def test_unknown_and_incomplete_directories_are_preserved(self) -> None:
		first = self.publish("first")
		incomplete = first.parent / "incomplete"
		incomplete.mkdir()
		unknown = first.parent / "unrecognized_directory"
		unknown.mkdir()
		(unknown / "keep.txt").write_text("keep", encoding="utf-8")
		self.publish("second")
		self.publish("third")
		self.assertTrue(incomplete.exists())
		self.assertEqual((unknown / "keep.txt").read_text(encoding="utf-8"), "keep")
		self.assertFalse(first.exists())

	def test_explicit_read_scope_preserves_its_generation_metadata(self) -> None:
		first = self.publish("first")
		expected = active_projection_metadata(self.repo_root)
		with read_projection(self.repo_root, store_dir=first) as pinned:
			self.assertEqual(pinned.metadata, expected)

	def test_busy_quarantine_entry_does_not_starve_later_removal(self) -> None:
		first = self.publish("aaa")
		second = self.publish("bbb")
		rmtree = shutil.rmtree

		def remove(path, *args, **kwargs):
			if path.name == first.name:
				raise PermissionError("still busy")
			return rmtree(path, *args, **kwargs)

		with (
			patch("webapp.store.lifecycle.MAX_RETIREMENTS_PER_WRITE", 1),
			patch("webapp.store.lifecycle.shutil.rmtree", side_effect=remove),
			self.assertLogs("webapp.store.lifecycle", level="WARNING"),
		):
			self.publish("ccc")
			self.publish("ddd")
		quarantine = first.parent / ".retired"
		self.assertTrue((quarantine / first.name).exists())
		self.assertFalse((quarantine / second.name).exists())

	def test_live_collection_keeps_revision_and_health_on_one_generation(self) -> None:
		from webapp.api.live import Broadcaster
		from webapp.git_adapter import WorkspaceRevision
		from webapp.store.lifecycle import selected_projection

		first = self.publish("first")

		def revision_read(root, _game_root):
			metadata = selected_projection(root).metadata
			self.publish("second")
			self.publish("third")
			return WorkspaceRevision(
				worktree_id="fixture", branch="main", head="head", content_revision="first",
				projection_revision=metadata.revision, projection_generation_id=metadata.generation_id,
			)

		with (
			patch("webapp.api.live.workspace_revision", side_effect=revision_read),
			patch("webapp.api.live.store_health", side_effect=lambda root, *_args, **_kwargs: {"path": str(db.store_path(root))}),
			patch("webapp.api.live.list_tools", return_value=[]),
			patch("webapp.api.live.list_active_runs", return_value=[]),
			patch("webapp.api.live.load_tool_registry", return_value=object()),
		):
			snapshot = Broadcaster(self.repo_root)._collect()
		self.assertEqual(snapshot["workspace_revision"]["projection_generation_id"], first.name)
		self.assertEqual(snapshot["health"]["path"], str(first))

	def test_workspace_revision_honors_the_enclosing_read_scope(self) -> None:
		from webapp.git_adapter import workspace_revision

		first = self.publish("first")
		with (
			read_projection(self.repo_root),
			patch("webapp.git_adapter._run_git", return_value=SimpleNamespace(stdout="fixture", returncode=0)),
		):
			self.publish("second")
			revision = workspace_revision(self.repo_root)
		self.assertEqual(revision.projection_generation_id, first.name)

	def test_alternate_spelling_cannot_bypass_a_generation_lease(self) -> None:
		first = self.publish("first")
		alternate = first.parent / "unused" / ".." / first.name
		with self.assertRaises(ValueError):
			db.connect(self.repo_root, store_dir=alternate)

	def test_directory_alias_does_not_escape_reader_or_retirement_containment(self) -> None:
		first = self.publish("first")
		outside = self.repo_root / "outside-projections"
		outside.mkdir()
		(outside / "keep.txt").write_text("keep", encoding="utf-8")
		alias = first.parent / "alias"
		if os.name == "nt":
			subprocess.run(
				["cmd.exe", "/d", "/c", "mklink", "/J", str(alias), str(outside)],
				check=True, capture_output=True, timeout=5,
			)
		else:
			alias.symlink_to(outside, target_is_directory=True)
		with self.assertRaises(ValueError):
			db.connect(self.repo_root, store_dir=alias)
		self.publish("second")
		self.publish("third")
		self.assertFalse(first.exists())
		self.assertTrue(alias.exists())
		self.assertEqual((outside / "keep.txt").read_text(encoding="utf-8"), "keep")

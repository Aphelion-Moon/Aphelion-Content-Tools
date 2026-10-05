from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.lore_editor.records import CONTENT_ROOT
from webapp import workspace_lock
from webapp.api import create_app
from webapp.api.live import Broadcaster
from webapp.tests.http_client import TestClient
from webapp.workspace_lock import WorkspaceLease, WorkspaceLeaseConflict


class WorkspaceLeaseTests(unittest.TestCase):
	def test_owner_read_recovers_from_a_transient_windows_replace_conflict(self) -> None:
		with patch.object(Path, 'read_text', side_effect=[PermissionError('sharing violation'), '{"session_id":"owner"}']):
			self.assertEqual(workspace_lock._read_owner(Path('lease.json')), {'session_id': 'owner'})

	def test_owner_write_recovers_when_a_reader_briefly_blocks_replacement(self) -> None:
		path = self.workspace / 'lease.json'
		replace = workspace_lock.os.replace
		with patch.object(workspace_lock.os, 'replace') as mocked:
			def attempt(source, target):
				if mocked.call_count == 1:
					raise PermissionError('sharing violation')
				return replace(source, target)
			mocked.side_effect = attempt
			workspace_lock._atomic_write_owner(path, {'session_id': 'owner'})
		self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'session_id': 'owner'})
		self.assertEqual(list(self.workspace.glob('*.tmp')), [])

	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp_dir.cleanup)
		self.workspace = Path(self.temp_dir.name) / "workspace"
		self.workspace.mkdir()

	def test_second_backend_cannot_acquire_the_same_resolved_workspace(self) -> None:
		first = WorkspaceLease(self.workspace, heartbeat_interval_seconds=0.02)
		second = WorkspaceLease(self.workspace, heartbeat_interval_seconds=0.02)
		first.acquire()
		self.addCleanup(first.release)

		with self.assertRaises(WorkspaceLeaseConflict) as raised:
			second.acquire()

		self.assertEqual(raised.exception.owner["session_id"], first.owner["session_id"])

	def test_release_allows_a_new_backend_to_acquire(self) -> None:
		first = WorkspaceLease(self.workspace)
		first.acquire()
		first.release()

		second = WorkspaceLease(self.workspace)
		second.acquire()
		self.addCleanup(second.release)
		self.assertTrue(second.acquired)

	def test_demonstrably_dead_owner_is_reclaimed(self) -> None:
		lease = WorkspaceLease(self.workspace)
		lease.lock_path.parent.mkdir(parents=True, exist_ok=True)
		lease.lock_path.write_text(json.dumps({
			"pid": 2_147_483_647,
			"process_start_identity": "dead",
			"workspace": str(self.workspace.resolve()),
			"session_id": "dead-session",
			"acquired_at": 1.0,
			"heartbeat_at": 1.0,
		}), encoding="utf-8")

		lease.acquire()
		self.addCleanup(lease.release)
		self.assertNotEqual(lease.owner["session_id"], "dead-session")

	def test_separate_worktrees_have_independent_leases(self) -> None:
		other_workspace = self.workspace.parent / "other-worktree"
		other_workspace.mkdir()
		first = WorkspaceLease(self.workspace)
		second = WorkspaceLease(other_workspace)
		first.acquire()
		second.acquire()
		self.addCleanup(first.release)
		self.addCleanup(second.release)
		self.assertNotEqual(first.lock_path, second.lock_path)

	def test_heartbeat_refreshes_owner_metadata(self) -> None:
		lease = WorkspaceLease(self.workspace, heartbeat_interval_seconds=0.01)
		lease.acquire()
		self.addCleanup(lease.release)
		initial = float(lease.owner["heartbeat_at"])
		deadline = time.monotonic() + 1.0
		while float(lease.owner["heartbeat_at"]) <= initial and time.monotonic() < deadline:
			time.sleep(0.01)
		self.assertGreater(float(lease.owner["heartbeat_at"]), initial)

	def test_fastapi_lifespan_owns_and_releases_the_workspace(self) -> None:
		first_app = create_app(self.workspace)
		second_app = create_app(self.workspace)
		with TestClient(first_app) as client:
			self.assertTrue(first_app.state.workspace_lease.acquired)
			lease_response = client.get("/api/workspace/lease")
			self.assertEqual(lease_response.status_code, 200)
			self.assertEqual(
				lease_response.json()["owner"]["session_id"],
				first_app.state.workspace_lease.session_id,
			)
			with self.assertRaises(WorkspaceLeaseConflict), TestClient(second_app):
				pass

		lease = WorkspaceLease(self.workspace)
		lease.acquire()
		lease.release()

	def test_startup_failure_releases_the_workspace_lease(self) -> None:
		(self.workspace / CONTENT_ROOT).mkdir(parents=True)
		app = create_app(self.workspace)
		with (
			patch("webapp.api.app.reconcile_projection", side_effect=RuntimeError("startup failed")),
			self.assertRaisesRegex(RuntimeError, "startup failed"),
			TestClient(app),
		):
			pass

		lease = WorkspaceLease(self.workspace)
		lease.acquire()
		lease.release()

	def test_startup_timer_is_joined_before_worker_shutdown(self) -> None:
		events: list[str] = []

		class RecordingTimer:
			def __init__(self, _interval: float, function, args: tuple[object, ...] = ()) -> None:
				events.append("timer-created")
				self.daemon = False
				self.function = function
				self.args = args

			def start(self) -> None:
				events.append("timer-start")

			def cancel(self) -> None:
				events.append("timer-cancel")

			def join(self, timeout: float | None = None) -> None:
				events.append("timer-join")
				self.function(*self.args)

		async def shutdown_broadcaster(_broadcaster: Broadcaster) -> None:
			events.append("broadcaster-shutdown")

		def shut_down_worker(_repo_root: Path) -> None:
			events.append("worker-shutdown")

		with (
			tempfile.TemporaryDirectory() as temporary_directory,
			patch("webapp.api.app.threading.Timer", RecordingTimer),
			patch("webapp.api.app.reconcile_projection"),
			patch("webapp.api.app.start_tool") as startup_optimize,
			patch("webapp.api.app.shut_down_worker", side_effect=shut_down_worker),
			patch.object(Broadcaster, "shutdown", new=shutdown_broadcaster),
		):
			app = create_app(Path(temporary_directory))
			with TestClient(app):
				pass

		self.assertIn("timer-cancel", events)
		self.assertIn("timer-join", events)
		self.assertLess(events.index("timer-cancel"), events.index("timer-join"))
		self.assertLess(events.index("timer-join"), events.index("worker-shutdown"))
		startup_optimize.assert_not_called()


if __name__ == "__main__":
	unittest.main()

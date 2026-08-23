from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from webapp import store_worker
from webapp.store_worker import JobCancelled, Worker, _RunOutputStream, pipe_address
from webapp.tooling import ToolDefinition

FAST_DEFINITION = ToolDefinition(
	id="fast", label="Fast", description="", tool_root="tools/lore_editor", commands=(("fast",),)
)
TWO_STEP_DEFINITION = ToolDefinition(
	id="two-step",
	label="Two step",
	description="",
	tool_root="tools/lore_editor",
	commands=(("step-one",), ("step-two",)),
)
GAME_REPO_DEFINITION = ToolDefinition(
	id="needs-game-repo",
	label="Needs game repo",
	description="",
	tool_root="tools/lore_editor",
	commands=(("scan",),),
	game_repo_commands=frozenset({"scan"}),
)


class WorkerExecutionTests(unittest.TestCase):
	"""Tests the worker's own job bookkeeping (status transitions, one-job-at-a-time serialization,
	cooperative cancellation) against a *fake* cli_main, so these stay fast and independent of any real
	tool's business logic. `webapp/tests/test_tooling.py` separately exercises the real worker process
	talking to the real lore_editor/content_graph/store CLIs over the actual IPC channel."""

	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.repo_root = Path(self.temp_dir.name)
		self.worker = Worker(self.repo_root)

	def tearDown(self) -> None:
		self.temp_dir.cleanup()

	def _wait_until_finished(self, run_id: str, timeout: float = 5.0) -> dict:
		deadline = time.monotonic() + timeout
		while time.monotonic() < deadline:
			current = self.worker.status(run_id)
			if current["status"] not in ("queued", "running"):
				return current
			time.sleep(0.02)
		self.fail("Job did not finish before the test deadline.")

	def test_a_successful_job_ends_up_succeeded_with_its_output_captured(self) -> None:
		def fake_main(argv: list[str]) -> int:
			print("hello from the fake tool")
			return 0

		with patch.object(store_worker, "_load_cli_main", return_value=fake_main):
			run = self.worker.start(FAST_DEFINITION, None)
			current = self._wait_until_finished(run["run_id"])
		self.assertEqual(current["status"], "succeeded")
		self.assertEqual(current["exit_code"], 0)
		self.assertIn("hello from the fake tool", current["output"])

	def test_a_nonzero_exit_code_marks_the_run_failed(self) -> None:
		def fake_main(argv: list[str]) -> int:
			return 3

		with patch.object(store_worker, "_load_cli_main", return_value=fake_main):
			run = self.worker.start(FAST_DEFINITION, None)
			current = self._wait_until_finished(run["run_id"])
		self.assertEqual(current["status"], "failed")
		self.assertEqual(current["exit_code"], 3)

	def test_an_unhandled_exception_marks_the_run_failed_and_records_the_message(self) -> None:
		def fake_main(argv: list[str]) -> int:
			raise RuntimeError("kaboom")

		with patch.object(store_worker, "_load_cli_main", return_value=fake_main):
			run = self.worker.start(FAST_DEFINITION, None)
			current = self._wait_until_finished(run["run_id"])
		self.assertEqual(current["status"], "failed")
		self.assertIn("kaboom", current["output"])

	def test_a_multi_command_definition_runs_each_command_in_order(self) -> None:
		calls: list[str] = []

		def fake_main(argv: list[str]) -> int:
			calls.append(argv[0])
			return 0

		with patch.object(store_worker, "_load_cli_main", return_value=fake_main):
			run = self.worker.start(TWO_STEP_DEFINITION, None)
			self._wait_until_finished(run["run_id"])
		self.assertEqual(calls, ["step-one", "step-two"])

	def test_game_repo_root_is_only_appended_for_game_repo_commands(self) -> None:
		captured: list[list[str]] = []

		def fake_main(argv: list[str]) -> int:
			captured.append(argv)
			return 0

		with patch.object(store_worker, "_load_cli_main", return_value=fake_main):
			run = self.worker.start(GAME_REPO_DEFINITION, Path("/some/game/repo"))
			self._wait_until_finished(run["run_id"])
		self.assertIn("--game-repo", captured[0])

		with patch.object(store_worker, "_load_cli_main", return_value=fake_main):
			run = self.worker.start(FAST_DEFINITION, Path("/some/game/repo"))
			self._wait_until_finished(run["run_id"])
		self.assertNotIn("--game-repo", captured[1])

	def test_stopping_a_running_job_marks_it_stopped_not_failed_or_succeeded(self) -> None:
		def fake_main(argv: list[str]) -> int:
			for i in range(50):
				print(f"tick {i}", flush=True)
				time.sleep(0.05)
			return 0

		with patch.object(store_worker, "_load_cli_main", return_value=fake_main):
			run = self.worker.start(FAST_DEFINITION, None)
			deadline = time.monotonic() + 5
			while time.monotonic() < deadline and "tick 0" not in self.worker.status(run["run_id"])["output"]:
				time.sleep(0.02)
			self.worker.stop(run["run_id"])
			current = self._wait_until_finished(run["run_id"])
			self.assertEqual(current["status"], "stopped")
			self.assertNotIn("tick 49", current["output"])  # genuinely interrupted, not left to finish

	def test_stopping_a_silent_python_job_does_not_wait_for_output(self) -> None:
		started = threading.Event()

		def fake_main(argv: list[str]) -> int:
			started.set()
			deadline = time.monotonic() + 5
			counter = 0
			while time.monotonic() < deadline:
				counter += 1
			return counter

		with patch.object(store_worker, "_load_cli_main", return_value=fake_main):
			run = self.worker.start(FAST_DEFINITION, None)
			self.assertTrue(started.wait(timeout=2))
			self.worker.stop(run["run_id"])
			current = self._wait_until_finished(run["run_id"], timeout=2)
			self.assertEqual(current["status"], "stopped")

	def test_jobs_against_the_same_worker_run_one_at_a_time(self) -> None:
		release = threading.Event()

		def fake_main(argv: list[str]) -> int:
			release.wait(timeout=5)
			return 0

		with patch.object(store_worker, "_load_cli_main", return_value=fake_main):
			run_a = self.worker.start(FAST_DEFINITION, None)
			deadline = time.monotonic() + 5
			while time.monotonic() < deadline and self.worker.status(run_a["run_id"])["status"] != "running":
				time.sleep(0.02)
			run_b = self.worker.start(FAST_DEFINITION, None)
			time.sleep(0.2)
			self.assertEqual(self.worker.status(run_b["run_id"])["status"], "queued")
			release.set()
			self.assertEqual(self._wait_until_finished(run_a["run_id"])["status"], "succeeded")
			self.assertEqual(self._wait_until_finished(run_b["run_id"])["status"], "succeeded")

	def test_status_and_stop_reject_an_unknown_run_id(self) -> None:
		with self.assertRaises(ValueError):
			self.worker.status("missing")
		with self.assertRaises(ValueError):
			self.worker.stop("missing")

	def test_list_active_reports_only_queued_or_running_runs_with_queued_at(self) -> None:
		release = threading.Event()

		def fake_main(argv: list[str]) -> int:
			release.wait(timeout=5)
			return 0

		with patch.object(store_worker, "_load_cli_main", return_value=fake_main):
			run = self.worker.start(FAST_DEFINITION, None)
			deadline = time.monotonic() + 5
			while time.monotonic() < deadline and self.worker.status(run["run_id"])["status"] != "running":
				time.sleep(0.02)

			active = self.worker.list_active()
			self.assertEqual(len(active), 1)
			self.assertEqual(active[0]["run_id"], run["run_id"])
			self.assertEqual(active[0]["tool_id"], FAST_DEFINITION.id)
			self.assertEqual(active[0]["status"], "running")
			self.assertIn("queued_at", active[0])
			self.assertNotIn("output", active[0])  # trimmed -- summaries don't need the full console text

			release.set()
			self._wait_until_finished(run["run_id"])
			self.assertEqual(self.worker.list_active(), [])

	def test_new_worker_recovers_an_interrupted_run_as_failed(self) -> None:
		with self.worker._runs_lock:
			self.worker._runs["interrupted"] = {
				"run_id": "interrupted",
				"tool_id": FAST_DEFINITION.id,
				"status": "running",
				"output": "",
				"exit_code": None,
				"log_path": "tools/logs/interrupted.log",
				"stop_requested": False,
				"queued_at": time.time(),
			}
			self.worker._persist_run_locked("interrupted")

		recovered = Worker(self.repo_root).status("interrupted")
		self.assertEqual(recovered["status"], "failed")
		self.assertIn("worker exited", recovered["output"].lower())


class RunOutputStreamTests(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.worker = Worker(Path(self.temp_dir.name))
		self.worker._runs["r1"] = {
			"run_id": "r1", "status": "running", "output": "", "stop_requested": False,
		}

	def tearDown(self) -> None:
		self.temp_dir.cleanup()

	def test_write_appends_to_the_runs_output(self) -> None:
		stream = _RunOutputStream(self.worker, "r1")
		stream.write("hello\n")
		self.assertIn("hello", self.worker.status("r1")["output"])

	def test_write_raises_job_cancelled_once_a_stop_has_been_requested(self) -> None:
		stream = _RunOutputStream(self.worker, "r1")
		stream.write("before stop\n")
		self.worker._runs["r1"]["stop_requested"] = True
		with self.assertRaises(JobCancelled):
			stream.write("after stop\n")
		# the triggering write is still captured before the raise -- nothing already printed is lost
		self.assertIn("after stop", self.worker.status("r1")["output"])


class BuildArgvTests(unittest.TestCase):
	def test_build_argv_appends_game_repo_only_for_matching_commands(self) -> None:
		repo_root = Path("/repo")
		game_repo_root = Path("/game")
		definition = ToolDefinition(
			id="x", label="", description="", tool_root="tools/lore_editor",
			commands=(("validate", "--check-generated"),),
			game_repo_commands=frozenset({"validate"}),
		)
		argv = store_worker._build_argv(repo_root, definition, 0, game_repo_root=game_repo_root)
		self.assertEqual(argv, ["validate", "--check-generated", "--repo-root", str(repo_root), "--game-repo", str(game_repo_root)])

	def test_build_argv_omits_game_repo_when_command_does_not_need_it(self) -> None:
		repo_root = Path("/repo")
		definition = ToolDefinition(id="y", label="", description="", tool_root="tools/lore_editor", commands=(("generate",),))
		argv = store_worker._build_argv(repo_root, definition, 0, game_repo_root=Path("/game"))
		self.assertEqual(argv, ["generate", "--repo-root", str(repo_root)])

	def test_build_argv_rejects_an_out_of_range_command_index(self) -> None:
		definition = ToolDefinition(id="z", label="", description="", tool_root="tools/lore_editor", commands=(("generate",),))
		with self.assertRaises(ValueError):
			store_worker._build_argv(Path("/repo"), definition, 5, game_repo_root=None)


class PipeAddressTests(unittest.TestCase):
	def test_pipe_address_is_unique_per_repo_root(self) -> None:
		address_a = pipe_address(Path("/a"))
		address_b = pipe_address(Path("/b"))
		self.assertNotEqual(address_a, address_b)
		self.assertTrue(address_a.startswith(r"\\.\pipe\aphelion-store-worker-"))

	def test_worker_rejects_a_request_claiming_another_repository(self) -> None:
		with tempfile.TemporaryDirectory() as temporary_directory:
			worker = Worker(Path(temporary_directory))
			with self.assertRaises(ValueError):
				store_worker._validate_request_repo(worker, {"repo_root": str(Path(temporary_directory) / "other")})


if __name__ == "__main__":
	unittest.main()

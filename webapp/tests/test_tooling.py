from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from tools.lore_editor.tests.store_helpers import seed_targets
from webapp import tooling
from webapp.tool_registry import load_tool_registry


def _synthetic_targets(count: int) -> list[dict[str, object]]:
	return [
		{
			"type_path": f"/obj/item/synthetic_{i}",
			"label": f"Synthetic item {i}",
			"editable_root": "/obj/item",
			"parent_type": "/obj/item",
			"field_profile": "atom_like",
			"base_values": {"name": f"synthetic item {i}", "description": f"A synthetic test item {i}."},
			"icon_metadata": {},
		}
		for i in range(count)
	]


class ToolingClientTests(unittest.TestCase):
	"""Exercises `webapp/tooling.py` as the IPC client to the real, persistent `webapp/store_worker.py`
	process -- these spawn a real worker subprocess (unlike `test_store_worker.py`, which fakes the CLI
	entry point to test the worker's own bookkeeping quickly), so they're the ones that actually prove
	the end-to-end architecture (a job really runs in a separate warm process, a stop really reaches it,
	a crash is really recovered from) works, not just each half in isolation."""

	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.repo_root = Path(self.temp_dir.name)
		self.definitions = load_tool_registry()
		seed_targets(self.repo_root, [
			{
				"type_path": "/obj/item/radio",
				"label": "Handheld Radio",
				"editable_root": "/obj/item/radio",
				"parent_type": "/obj/item",
				"field_profile": "atom_like",
				"base_values": {"name": "radio", "description": "A radio."},
				"icon_metadata": {},
			}
		])

	def tearDown(self) -> None:
		tooling.shut_down_worker(self.repo_root)
		self.temp_dir.cleanup()

	def _wait_for_completion(self, run_id: str, timeout: float = 30.0) -> dict:
		deadline = time.monotonic() + timeout
		while time.monotonic() < deadline:
			current = tooling.get_tool_run(run_id)
			if current["status"] not in ("queued", "running"):
				return current
			time.sleep(0.05)
		self.fail("Tool run did not finish before the test deadline.")

	def test_start_tool_rejects_an_unknown_tool_id_without_starting_a_worker(self) -> None:
		with self.assertRaises(ValueError):
			tooling.start_tool(self.repo_root, self.definitions, "not-a-real-tool")
		self.assertNotIn(str(self.repo_root.resolve()), tooling._workers)

	def test_generate_runs_to_completion_through_the_real_worker_process(self) -> None:
		run = tooling.start_tool(self.repo_root, self.definitions, "generate")
		self.assertIn(run["status"], {"queued", "running"})
		current = self._wait_for_completion(run["run_id"])
		self.assertEqual(current["status"], "succeeded")
		self.assertIn("Generated lore DM artifact", current["output"])
		self.assertTrue((self.repo_root / "tools/lore_editor/stages/current/generated_lore_overrides.dm").exists())

	def test_get_tool_run_and_stop_tool_reject_an_unknown_run_id(self) -> None:
		tooling.start_tool(self.repo_root, self.definitions, "generate")  # ensures a worker exists to ask
		with self.assertRaises(ValueError):
			tooling.get_tool_run("not-a-real-run")
		with self.assertRaises(ValueError):
			tooling.stop_tool("not-a-real-run")

	def test_stop_tool_interrupts_a_running_job_instead_of_letting_it_succeed(self) -> None:
		seed_targets(self.repo_root, _synthetic_targets(300))
		run = tooling.start_tool(self.repo_root, self.definitions, "rebuild-search-embeddings")
		time.sleep(1.0)
		stopped = tooling.stop_tool(run["run_id"])
		self.assertIn(stopped["status"], {"running", "stopped"})
		current = self._wait_for_completion(run["run_id"])
		self.assertEqual(current["status"], "stopped")

	def test_worker_respawns_transparently_after_a_crash(self) -> None:
		run = tooling.start_tool(self.repo_root, self.definitions, "generate")
		self._wait_for_completion(run["run_id"])

		handle = tooling._get_worker(self.repo_root)
		pid_before = handle.process.pid
		handle.process.kill()
		handle.process.wait(timeout=5)

		run2 = tooling.start_tool(self.repo_root, self.definitions, "generate")
		current2 = self._wait_for_completion(run2["run_id"])
		self.assertEqual(current2["status"], "succeeded")
		self.assertNotEqual(tooling._get_worker(self.repo_root).process.pid, pid_before)

	def test_jobs_against_the_same_repo_root_run_one_at_a_time(self) -> None:
		seed_targets(self.repo_root, _synthetic_targets(300))
		run_a = tooling.start_tool(self.repo_root, self.definitions, "rebuild-search-embeddings")
		run_b = tooling.start_tool(self.repo_root, self.definitions, "rebuild-search-embeddings")
		time.sleep(0.3)
		self.assertEqual(tooling.get_tool_run(run_b["run_id"])["status"], "queued")
		self.assertEqual(self._wait_for_completion(run_a["run_id"])["status"], "succeeded")
		self.assertEqual(self._wait_for_completion(run_b["run_id"])["status"], "succeeded")

	def test_shut_down_worker_is_a_quiet_no_op_when_no_worker_was_ever_started(self) -> None:
		other_temp_dir = tempfile.TemporaryDirectory()
		try:
			tooling.shut_down_worker(Path(other_temp_dir.name))
		finally:
			other_temp_dir.cleanup()

	def test_list_active_runs_never_spawns_a_worker_when_none_exists(self) -> None:
		other_temp_dir = tempfile.TemporaryDirectory()
		try:
			other_repo_root = Path(other_temp_dir.name)
			self.assertEqual(tooling.list_active_runs(other_repo_root), [])
			self.assertNotIn(str(other_repo_root.resolve()), tooling._workers)
		finally:
			other_temp_dir.cleanup()

	def test_list_active_runs_reports_a_real_job_in_progress_then_clears_after_it_finishes(self) -> None:
		seed_targets(self.repo_root, _synthetic_targets(300))
		run = tooling.start_tool(self.repo_root, self.definitions, "rebuild-search-embeddings")
		time.sleep(0.5)

		active = tooling.list_active_runs(self.repo_root)
		self.assertTrue(any(entry["run_id"] == run["run_id"] for entry in active))
		matching = next(entry for entry in active if entry["run_id"] == run["run_id"])
		self.assertEqual(matching["tool_id"], "rebuild-search-embeddings")
		self.assertIn("queued_at", matching)

		self._wait_for_completion(run["run_id"])
		self.assertEqual(tooling.list_active_runs(self.repo_root), [])


if __name__ == "__main__":
	unittest.main()

from __future__ import annotations

import gc
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import warnings
from pathlib import Path

from tools.testing.suite_process import run_command


class SuiteProcessTests(unittest.TestCase):
	def setUp(self) -> None:
		self.temporary_directory = tempfile.TemporaryDirectory()
		self.root = Path(self.temporary_directory.name)

	def tearDown(self) -> None:
		self.temporary_directory.cleanup()

	def run_python(self, source: str, *, timeout_seconds: float = 5, max_log_bytes: int = 4096):
		return run_command(
			name="fixture",
			command=(sys.executable, "-c", source),
			working_directory=self.root,
			log_path=self.root / "fixture.log",
			timeout_seconds=timeout_seconds,
			max_log_bytes=max_log_bytes,
		)

	def test_reports_success_and_captures_output(self) -> None:
		with warnings.catch_warnings(record=True) as caught:
			warnings.simplefilter("always", ResourceWarning)
			result = self.run_python("print('bounded pass')")
			gc.collect()

		self.assertEqual(result.status, "passed")
		self.assertEqual(result.exit_code, 0)
		self.assertIn("bounded pass", (self.root / "fixture.log").read_text(encoding="utf-8"))
		self.assertEqual([warning for warning in caught if warning.category is ResourceWarning], [])

	def test_reports_nonzero_exit_without_raising(self) -> None:
		result = self.run_python("import sys; print('bounded fail'); sys.exit(7)")

		self.assertEqual(result.status, "failed")
		self.assertEqual(result.exit_code, 7)

	def test_resource_warning_fails_an_otherwise_successful_command(self) -> None:
		result = self.run_python("import sys; sys.stderr.write('ResourceWarning: unclosed fixture\\n')")

		self.assertEqual(result.status, "resource_warning")
		self.assertTrue(result.resource_warning_detected)

	def test_times_out_and_terminates_the_process(self) -> None:
		result = self.run_python("import time; time.sleep(30)", timeout_seconds=0.2)

		self.assertEqual(result.status, "timed_out")
		self.assertIsNone(result.exit_code)
		self.assertLess(result.duration_seconds, 5)

	def test_caps_log_bytes_while_draining_process_output(self) -> None:
		result = self.run_python("print('x' * 100000)", max_log_bytes=128)
		log = (self.root / "fixture.log").read_bytes()

		self.assertEqual(result.status, "passed")
		self.assertTrue(result.log_truncated)
		self.assertLessEqual(len(log), 256)
		self.assertIn(b"log truncated", log)

	@unittest.skipUnless(os.name == "nt", "Exact child-tree ownership uses Windows Job Objects.")
	def test_reports_peak_process_tree_memory(self) -> None:
		result = self.run_python("payload = bytearray(1024 * 1024); print(len(payload))")

		self.assertIsNotNone(result.peak_memory_bytes)
		self.assertGreater(result.peak_memory_bytes or 0, 1024 * 1024)

	@unittest.skipUnless(os.name == "nt", "Exact child-tree ownership uses Windows Job Objects.")
	def test_timeout_terminates_a_spawned_child_process(self) -> None:
		child_pid_path = self.root / "child-pid.json"
		source = (
			"import json, pathlib, subprocess, sys, time; "
			"child=subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
			f"pathlib.Path({str(child_pid_path)!r}).write_text(json.dumps(child.pid)); "
			"time.sleep(30)"
		)

		result = self.run_python(source, timeout_seconds=1)
		child_pid = json.loads(child_pid_path.read_text(encoding="utf-8"))
		deadline = time.monotonic() + 5
		while time.monotonic() < deadline:
			completed = subprocess.run(
				[
					"powershell.exe",
					"-NoProfile",
					"-Command",
					f"if (Get-Process -Id {child_pid} -ErrorAction SilentlyContinue) {{ exit 1 }}",
				],
				check=False,
				capture_output=True,
			)
			if completed.returncode == 0:
				break
			time.sleep(0.1)

		self.assertEqual(result.status, "timed_out")
		self.assertEqual(completed.returncode, 0, "spawned child process survived suite timeout")

	def test_powershell_runner_reports_selected_suites_and_failure(self) -> None:
		powershell = shutil.which("pwsh") or shutil.which("powershell")
		if powershell is None:
			self.skipTest("PowerShell is required for the Windows suite runner.")
		tests = self.root / "fixture_tests"
		tests.mkdir()
		(tests / "__init__.py").write_text("", encoding="utf-8")
		(tests / "test_pass.py").write_text(
			"import unittest\n\nclass PassTest(unittest.TestCase):\n\tdef test_pass(self):\n\t\tself.assertTrue(True)\n",
			encoding="utf-8",
		)
		(tests / "test_fail.py").write_text(
			"import unittest\n\nclass FailTest(unittest.TestCase):\n\tdef test_fail(self):\n\t\tself.fail('synthetic failure')\n",
			encoding="utf-8",
		)
		manifest = self.root / "python-suites.json"
		manifest.write_text(
			json.dumps(
				{
					"schema_version": 1,
					"suites": [
						{
							"id": "pass",
							"description": "Passing fixture",
							"include": ["fixture_tests/test_pass.py"],
							"timeout_seconds": 10,
							"max_log_bytes": 4096,
						},
						{
							"id": "fail",
							"description": "Failing fixture",
							"include": ["fixture_tests/test_fail.py"],
							"timeout_seconds": 10,
							"max_log_bytes": 4096,
						},
					],
				}
			),
			encoding="utf-8",
		)
		script = Path(__file__).resolve().parents[1] / "run-python-suites.ps1"
		output = self.root / "results"

		passing = subprocess.run(
			[
				powershell,
				"-NoProfile",
				"-File",
				str(script),
				"-ManifestPath",
				str(manifest),
				"-RepositoryRoot",
				str(self.root),
				"-OutputRoot",
				str(output),
				"-Suite",
				"pass",
			],
			check=False,
			capture_output=True,
			text=True,
		)
		self.assertEqual(passing.returncode, 0, passing.stdout + passing.stderr)
		passing_summary = json.loads((output / "summary.json").read_text(encoding="utf-8-sig"))
		self.assertEqual([result["status"] for result in passing_summary["results"]], ["passed"])

		failing = subprocess.run(
			[
				powershell,
				"-NoProfile",
				"-File",
				str(script),
				"-ManifestPath",
				str(manifest),
				"-RepositoryRoot",
				str(self.root),
				"-OutputRoot",
				str(output),
			],
			check=False,
			capture_output=True,
			text=True,
		)
		self.assertEqual(failing.returncode, 1, failing.stdout + failing.stderr)
		failing_summary = json.loads((output / "summary.json").read_text(encoding="utf-8-sig"))
		self.assertEqual([result["status"] for result in failing_summary["results"]], ["passed", "failed"])

	def test_powershell_pytest_runner_keeps_tmp_path_under_output_root(self) -> None:
		powershell = shutil.which("pwsh") or shutil.which("powershell")
		if powershell is None:
			self.skipTest("PowerShell is required for the Windows suite runner.")
		pytest_check = subprocess.run(
			[sys.executable, "-m", "pytest", "--version"],
			check=False,
			capture_output=True,
			text=True,
		)
		if pytest_check.returncode != 0:
			self.skipTest("pytest is required for the pytest suite runner.")
		tests = self.root / "fixture_tests"
		tests.mkdir()
		(tests / "__init__.py").write_text("", encoding="utf-8")
		(tests / "test_tmp_path.py").write_text(
			"def test_tmp_path_is_writable(tmp_path):\n"
			"    marker = tmp_path / 'marker.txt'\n"
			"    marker.write_text('ok', encoding='utf-8')\n"
			"    assert marker.read_text(encoding='utf-8') == 'ok'\n",
			encoding="utf-8",
		)
		manifest = self.root / "python-suites.json"
		manifest.write_text(
			json.dumps(
				{
					"schema_version": 1,
					"suites": [{
						"id": "pytest_fixture",
						"runner": "pytest",
						"description": "Pytest temporary directory fixture",
						"include": ["fixture_tests/test_tmp_path.py"],
						"timeout_seconds": 30,
						"max_log_bytes": 4096,
					}],
				}
			),
			encoding="utf-8",
		)
		output = self.root / "results"
		script = Path(__file__).resolve().parents[1] / "run-python-suites.ps1"
		result = subprocess.run(
			[
				powershell,
				"-NoProfile",
				"-File",
				str(script),
				"-ManifestPath",
				str(manifest),
				"-RepositoryRoot",
				str(self.root),
				"-OutputRoot",
				str(output),
			],
			check=False,
			capture_output=True,
			text=True,
		)
		self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
		summary = json.loads((output / "summary.json").read_text(encoding="utf-8-sig"))
		self.assertEqual([entry["status"] for entry in summary["results"]], ["passed"])
		pytest_roots = list(output.glob(".pytest-pytest_fixture-*"))
		self.assertEqual(len(pytest_roots), 1)
		self.assertTrue(pytest_roots[0].is_relative_to(output.resolve()))


if __name__ == "__main__":
	unittest.main()

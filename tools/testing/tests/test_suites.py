from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.testing.suites import SuiteManifestError, load_suite_manifest


class SuiteManifestTests(unittest.TestCase):
	def test_supports_pytest_and_rejects_unknown_runners(self) -> None:
		entry = {"id": "all", "description": "All", "include": ["**/test_*.py"],
			"timeout_seconds": 30, "max_log_bytes": 4096, "runner": "pytest"}
		manifest = load_suite_manifest(self.write_manifest([entry]), self.root)
		self.assertEqual(manifest.suites[0].runner, "pytest")
		entry["runner"] = "shell"
		with self.assertRaisesRegex(SuiteManifestError, "runner"):
			load_suite_manifest(self.write_manifest([entry]), self.root)

	def setUp(self) -> None:
		self.temporary_directory = tempfile.TemporaryDirectory()
		self.root = Path(self.temporary_directory.name)
		(self.root / "alpha" / "tests").mkdir(parents=True)
		(self.root / "beta" / "tests").mkdir(parents=True)
		(self.root / "alpha" / "tests" / "test_one.py").write_text("", encoding="utf-8")
		(self.root / "beta" / "tests" / "test_two.py").write_text("", encoding="utf-8")

	def tearDown(self) -> None:
		self.temporary_directory.cleanup()

	def write_manifest(self, suites: list[dict[str, object]]) -> Path:
		path = self.root / "python-suites.json"
		path.write_text(json.dumps({"schema_version": 1, "suites": suites}), encoding="utf-8")
		return path

	def test_assigns_each_discovered_test_to_exactly_one_suite(self) -> None:
		manifest_path = self.write_manifest(
			[
				{
					"id": "alpha",
					"description": "Alpha tests",
					"include": ["alpha/tests/test_*.py"],
					"timeout_seconds": 30,
					"max_log_bytes": 4096,
				},
				{
					"id": "beta",
					"description": "Beta tests",
					"include": ["beta/tests/test_*.py"],
					"timeout_seconds": 60,
					"max_log_bytes": 8192,
				},
			]
		)

		manifest = load_suite_manifest(manifest_path, self.root)

		self.assertEqual([suite.id for suite in manifest.suites], ["alpha", "beta"])
		self.assertEqual(manifest.suites[0].modules, ("alpha.tests.test_one",))
		self.assertEqual(manifest.suites[1].modules, ("beta.tests.test_two",))

	def test_rejects_a_test_assigned_to_multiple_suites(self) -> None:
		manifest_path = self.write_manifest(
			[
				{
					"id": "first",
					"description": "First",
					"include": ["alpha/tests/test_*.py"],
					"timeout_seconds": 30,
					"max_log_bytes": 4096,
				},
				{
					"id": "second",
					"description": "Second",
					"include": ["alpha/tests/test_one.py", "beta/tests/test_*.py"],
					"timeout_seconds": 30,
					"max_log_bytes": 4096,
				},
			]
		)

		with self.assertRaisesRegex(SuiteManifestError, "assigned to multiple suites.*alpha/tests/test_one.py"):
			load_suite_manifest(manifest_path, self.root)

	def test_rejects_an_unassigned_test(self) -> None:
		manifest_path = self.write_manifest(
			[
				{
					"id": "alpha",
					"description": "Alpha tests",
					"include": ["alpha/tests/test_*.py"],
					"timeout_seconds": 30,
					"max_log_bytes": 4096,
				}
			]
		)

		with self.assertRaisesRegex(SuiteManifestError, "unassigned tests.*beta/tests/test_two.py"):
			load_suite_manifest(manifest_path, self.root)

	def test_rejects_paths_that_escape_the_repository(self) -> None:
		manifest_path = self.write_manifest(
			[
				{
					"id": "unsafe",
					"description": "Unsafe",
					"include": ["../test_*.py"],
					"timeout_seconds": 30,
					"max_log_bytes": 4096,
				}
			]
		)

		with self.assertRaisesRegex(SuiteManifestError, "repository-relative"):
			load_suite_manifest(manifest_path, self.root)

	def test_cli_emits_resolved_suite_modules(self) -> None:
		manifest_path = self.write_manifest(
			[
				{
					"id": "all",
					"description": "All tests",
					"include": ["alpha/tests/test_*.py", "beta/tests/test_*.py"],
					"timeout_seconds": 30,
					"max_log_bytes": 4096,
				}
			]
		)

		completed = subprocess.run(
			[
				sys.executable,
				"-m",
				"tools.testing.suites",
				"--manifest",
				str(manifest_path),
				"--repository-root",
				str(self.root),
			],
			check=False,
			capture_output=True,
			text=True,
		)

		self.assertEqual(completed.returncode, 0, completed.stderr)
		payload = json.loads(completed.stdout)
		self.assertEqual(payload["suites"][0]["modules"], ["alpha.tests.test_one", "beta.tests.test_two"])

	def test_repository_manifest_assigns_every_test_to_a_bounded_group(self) -> None:
		repository_root = Path(__file__).resolve().parents[3]
		manifest = load_suite_manifest(
			repository_root / "tools" / "testing" / "python-suites.json",
			repository_root,
		)

		self.assertEqual(
			{suite.id for suite in manifest.suites},
			{
				"docs_and_testing",
				"content_graph",
				"lore_editor",
				"parsec_assets",
				"webapp_core",
				"webapp_store",
				"webapp_embeddings",
				"webapp_worker_process",
			},
		)


if __name__ == "__main__":
	unittest.main()

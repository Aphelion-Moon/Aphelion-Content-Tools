from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from tools.lore_editor.records import atomic_write_record, record_path
from webapp.store.cli import main


class StoreCliTests(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp_dir.cleanup)
		self.repo_root = Path(self.temp_dir.name)
		atomic_write_record(record_path(self.repo_root, "group", "items"), {
			"id": "items",
			"label": "Items",
			"color": "#fff",
			"keywords": [],
			"type_path_prefixes": [],
		})

	def _run(self, *arguments: str) -> tuple[int, str]:
		output = StringIO()
		with redirect_stdout(output):
			result = main([*arguments, "--repo-root", str(self.repo_root)])
		return result, output.getvalue()

	def test_status_reconcile_and_rebuild_report_projection_state(self) -> None:
		status_code, status_output = self._run("status")
		self.assertEqual(status_code, 0)
		self.assertFalse(json.loads(status_output)["current"])

		reconcile_code, _reconcile_output = self._run("reconcile")
		self.assertEqual(reconcile_code, 0)
		status_code, status_output = self._run("status")
		self.assertEqual(status_code, 0)
		self.assertTrue(json.loads(status_output)["current"])

		rebuild_code, rebuild_output = self._run("rebuild")
		self.assertEqual(rebuild_code, 0)
		self.assertEqual(json.loads(rebuild_output)["counts"]["groups"], 1)

	def test_backup_and_restore_commands_use_explicit_labeled_paths(self) -> None:
		self._run("reconcile")
		backup_path = self.repo_root / "backup-one"
		backup_output = StringIO()
		with redirect_stdout(backup_output):
			backup_code = main([
				"backup",
				"--repo-root", str(self.repo_root),
				"--output", str(backup_path),
				"--label", "before-edit",
			])
		self.assertEqual(backup_code, 0)
		self.assertTrue((backup_path / "backup.json").is_file())

		restore_output = StringIO()
		with redirect_stdout(restore_output):
			restore_code = main([
				"restore",
				"--repo-root", str(self.repo_root),
				"--backup", str(backup_path),
			])
		self.assertEqual(restore_code, 0)
		self.assertEqual(json.loads(restore_output.getvalue())["state"], "stale")


if __name__ == "__main__":
	unittest.main()

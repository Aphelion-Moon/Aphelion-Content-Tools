from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.content_graph.graph import scan_and_cache_content_graph
from tools.lore_editor.catalog import activate_catalog_targets
from tools.lore_editor.reconcile import reconcile_projection
from webapp.store.health import store_health
from webapp.store.metadata import active_projection_metadata

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "workspace_snapshots"


def _run_git(repo_root: Path, *arguments: str) -> str:
	result = subprocess.run(
		["git", "-C", str(repo_root), *arguments],
		check=True,
		capture_output=True,
		text=True,
	)
	return result.stdout.strip()


class WorkspaceStatusTests(unittest.TestCase):
	def setUp(self) -> None:
		model = patch("webapp.store.embeddings._load_model", return_value=None)
		model.start()
		self.addCleanup(model.stop)
		self.temp_dir = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp_dir.cleanup)
		root = Path(self.temp_dir.name)
		self.tool_root = root / "tool"
		self.game_root = root / "game"
		shutil.copytree(FIXTURE_ROOT / "content_tools", self.tool_root)
		shutil.copytree(FIXTURE_ROOT / "game", self.game_root)
		_run_git(self.game_root, "init", "--initial-branch=main")
		_run_git(self.game_root, "config", "user.name", "Fixture Author")
		_run_git(self.game_root, "config", "user.email", "fixture@example.invalid")
		_run_git(self.game_root, "add", "--all")
		_run_git(self.game_root, "commit", "-m", "Fixture baseline")

	def _build_matching_projection(self) -> str:
		reconcile_projection(self.tool_root)
		manifest = scan_and_cache_content_graph(self.tool_root, self.game_root)
		activate_catalog_targets(self.tool_root, [], source_game_revision=manifest.game_repo_revision, source_provenance="release-seed")
		return manifest.game_repo_revision

	def test_matching_fixture_reports_projection_current(self) -> None:
		self._build_matching_projection()

		health = store_health(self.tool_root, self.game_root)
		self.assertTrue(health["projection"]["current"])
		self.assertTrue(health["workspace"]["current"])

	def test_game_revision_change_must_make_aggregate_workspace_stale(self) -> None:
		built_revision = self._build_matching_projection()
		(self.game_root / "revision-change.dm").write_text("/datum/revision_change\n", encoding="utf-8")
		_run_git(self.game_root, "add", "revision-change.dm")
		_run_git(self.game_root, "commit", "-m", "Advance fixture game revision")
		self.assertNotEqual(_run_git(self.game_root, "rev-parse", "HEAD"), built_revision)

		self.assertFalse(store_health(self.tool_root, self.game_root)["workspace"]["current"])

	def test_uncommitted_game_source_changes_make_the_workspace_stale(self) -> None:
		built_revision = self._build_matching_projection()
		(self.game_root / "revision-change.dm").write_text("/datum/new_catalog_type\n", encoding="utf-8")
		self.assertEqual(_run_git(self.game_root, "rev-parse", "HEAD"), built_revision)
		health = store_health(self.tool_root, self.game_root)
		self.assertFalse(health["workspace"]["current"])
		self.assertTrue(health["projection"]["current"])

	def test_ignored_graph_inputs_cannot_leave_the_workspace_current(self) -> None:
		(self.game_root / ".gitignore").write_text("code/ignored.dm\n", encoding="utf-8")
		_run_git(self.game_root, "add", ".gitignore")
		_run_git(self.game_root, "commit", "-m", "Ignore fixture graph source")
		self._build_matching_projection()
		(self.game_root / "code").mkdir(exist_ok=True)
		(self.game_root / "code/ignored.dm").write_text("// APHELION EDIT - ignored\n/datum/ignored\n", encoding="utf-8")
		self.assertEqual(_run_git(self.game_root, "status", "--porcelain"), "")
		self.assertFalse(store_health(self.tool_root, self.game_root)["workspace"]["current"])

	def test_failed_inactive_build_preserves_active_generation(self) -> None:
		self._build_matching_projection()
		active_before = active_projection_metadata(self.tool_root)

		with (
			patch("tools.lore_editor.catalog.db.sync_snapshot", side_effect=RuntimeError("fixture build failed")),
			self.assertRaisesRegex(RuntimeError, "fixture build failed"),
		):
			activate_catalog_targets(self.tool_root, [], source_game_revision=_run_git(self.game_root, "rev-parse", "HEAD"))

		self.assertEqual(active_projection_metadata(self.tool_root), active_before)

	def test_audit_baseline_is_machine_readable_and_contains_no_absolute_paths(self) -> None:
		payload = json.loads((FIXTURE_ROOT / "audit-baseline.json").read_text(encoding="utf-8"))

		self.assertEqual(payload["schema_version"], 1)
		self.assertFalse(payload["repository_paths_included"])
		self.assertEqual(payload["row_counts"]["catalog_targets"], 20881)
		self.assertNotIn(":\\", json.dumps(payload))


if __name__ == "__main__":
	unittest.main()

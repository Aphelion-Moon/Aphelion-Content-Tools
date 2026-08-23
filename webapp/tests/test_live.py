from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from webapp.api.live import Broadcaster
from webapp.git_adapter import WorkspaceRevision
from webapp.store.metadata import ProjectionRevision


class BroadcasterTests(unittest.TestCase):
	def test_collect_includes_branch_aware_workspace_revision(self) -> None:
		with tempfile.TemporaryDirectory() as temporary_directory:
			revision = WorkspaceRevision(
				worktree_id="worktree-one",
				branch="writer/zoe",
				head="abc123",
				content_revision="content123",
				projection_revision=ProjectionRevision(1, "content123", "model", "current"),
			)
			broadcaster = Broadcaster(Path(temporary_directory))
			with (
				patch("webapp.api.live.workspace_revision", return_value=revision),
				patch("webapp.api.live.store_health", return_value={"ok": True}),
				patch("webapp.api.live.list_tools", return_value=[]),
				patch("webapp.api.live.list_active_runs", return_value=[]),
			):
				snapshot = broadcaster._collect()

		self.assertEqual(snapshot["workspace_revision"]["branch"], "writer/zoe")
		self.assertEqual(
			snapshot["workspace_revision"]["projection_revision"]["content_revision"],
			"content123",
		)


if __name__ == "__main__":
	unittest.main()

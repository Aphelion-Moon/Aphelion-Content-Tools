from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from webapp.api.live import Broadcaster
from webapp.api.models import LiveMessage
from webapp.git_adapter import WorkspaceRevision
from webapp.store.metadata import ProjectionRevision


class BroadcasterTests(unittest.TestCase):
	def test_unavailable_revision_is_part_of_the_live_protocol(self) -> None:
		with tempfile.TemporaryDirectory() as temporary_directory:
			broadcaster = Broadcaster(Path(temporary_directory))
			with (
				patch("webapp.api.live.workspace_revision", side_effect=ValueError("unavailable")),
				patch("webapp.api.live.store_health", return_value={}),
				patch("webapp.api.live.list_tools", return_value=[]),
				patch("webapp.api.live.list_active_runs", return_value=[]),
			):
				snapshot = broadcaster._collect()
			message = LiveMessage(type="workspace_revision", data=snapshot["workspace_revision"])
			self.assertIsNone(message.model_dump()["data"])

	def test_collect_includes_branch_aware_workspace_revision(self) -> None:
		with tempfile.TemporaryDirectory() as temporary_directory:
			revision = WorkspaceRevision(
				worktree_id="worktree-one",
				branch="writer/zoe",
				head="abc123",
				content_revision="content123",
				projection_revision=ProjectionRevision(1, "content123", "model", "current"),
			)
			game_root = Path(temporary_directory) / "game"
			broadcaster = Broadcaster(Path(temporary_directory), game_root)
			with (
				patch("webapp.api.live.workspace_revision", return_value=revision) as revision_read,
				patch("webapp.api.live.store_health", return_value={"ok": True}),
				patch("webapp.api.live.list_tools", return_value=[]),
				patch("webapp.api.live.list_active_runs", return_value=[]),
			):
				snapshot = broadcaster._collect()
				revision_read.assert_called_once_with(Path(temporary_directory), game_root)

		self.assertEqual(snapshot["workspace_revision"]["branch"], "writer/zoe")
		self.assertEqual(
			snapshot["workspace_revision"]["projection_revision"]["content_revision"],
			"content123",
		)


if __name__ == "__main__":
	unittest.main()

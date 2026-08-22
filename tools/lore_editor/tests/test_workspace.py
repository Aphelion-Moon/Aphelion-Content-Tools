from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.lore_editor.workspace import GENERATED_DM_PATH, WorkspaceLayout


class WorkspaceLayoutTests(unittest.TestCase):

	def test_generated_dm_path_is_the_local_stage_artifact(self) -> None:
		with TemporaryDirectory() as temporary_directory:
			layout = WorkspaceLayout.from_root(Path(temporary_directory))

			self.assertEqual(GENERATED_DM_PATH, layout.generated_dm_path)
			self.assertEqual(
				Path("tools/lore_editor/stages/current/generated_lore_overrides.dm"),
				layout.generated_dm_path,
			)


if __name__ == "__main__":
	unittest.main()

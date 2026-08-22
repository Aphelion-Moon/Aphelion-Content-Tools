from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


GENERATED_DM_PATH = Path("tools/lore_editor/stages/current/generated_lore_overrides.dm")


@dataclass(frozen=True)
class WorkspaceLayout:
	"""The one on-disk path this tool still owns directly: the local staging copy of the generated DM
	artifact used by the `generate`/`validate --check-generated` CLI commands. Everything else (catalog
	targets, overrides, groups, reviews, assignments) lives in the shared store (`webapp/store`), not on
	disk, so there is no longer a standalone/non-standalone mode to choose between."""

	generated_dm_path: Path = GENERATED_DM_PATH

	@classmethod
	def from_root(cls, repo_root: Path) -> "WorkspaceLayout":
		return cls()

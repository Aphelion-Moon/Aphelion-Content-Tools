from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import Request

from .errors import BadRequest
from .models import RepositoryName


@dataclass(frozen=True)
class AppContext:
	"""Roots the app was started against.

	Held on `app.state` rather than in a module-level global so a test can build an app per temporary
	directory -- the existing test suite relies on exactly that.
	"""

	repo_root: Path
	game_repo_root: Path

	def repository(self, name: RepositoryName) -> Path:
		if name == "tool":
			return self.repo_root
		if name == "game":
			return self.game_repo_root
		raise BadRequest("Repository must be 'tool' or 'game'.")

	@property
	def export_stage_root(self) -> Path:
		return (self.repo_root / "tools/lore_editor/stages").resolve()


def context(request: Request) -> AppContext:
	return request.app.state.context  # type: ignore[no-any-return]

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import Request

from tools.lore_editor.reconcile import scan_canonical_records
from tools.lore_editor.write_coordinator import repository_write_lock
from webapp.game_changes import GameChangeSetService
from webapp.store.metadata import projection_status

from .errors import BadRequest, Conflict
from .models import RepositoryName


@dataclass(frozen=True)
class AppContext:
	"""Roots the app was started against.

	Held on `app.state` rather than in a module-level global so a test can build an app per temporary
	directory -- the existing test suite relies on exactly that.
	"""

	repo_root: Path
	game_repo_root: Path
	game_changes: GameChangeSetService = field(init=False, repr=False, compare=False)

	def __post_init__(self) -> None:
		object.__setattr__(self, 'game_changes', GameChangeSetService(self.game_repo_root))

	@contextmanager
	def authoring(self) -> Iterator[None]:
		"""Check currentness and perform the domain write in the same synchronous lease.

		Do not hold a thread-owned lock across a yielding FastAPI dependency: its
		enter, route, and exit can execute on different worker threads.
		"""
		with repository_write_lock(self.repo_root):
			snapshot = scan_canonical_records(self.repo_root)
			status = projection_status(self.repo_root, snapshot.content_revision)
			if not status.current:
				raise Conflict('Canonical content changed outside this backend. Reconcile the projection before authoring.')
			yield

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


def mutation_context(request: Request) -> AppContext:
	return context(request)

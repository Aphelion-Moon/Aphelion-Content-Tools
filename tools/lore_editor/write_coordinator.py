from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Lock, RLock

_repository_locks: dict[str, RLock] = {}
_repository_locks_guard = Lock()


@contextmanager
def repository_write_lock(repo_root: Path) -> Iterator[None]:
	key = str(repo_root.resolve())
	with _repository_locks_guard:
		lock = _repository_locks.setdefault(key, RLock())
	with lock:
		yield


class RecordConflict(ValueError):
	def __init__(
		self,
		*,
		record_id: str,
		expected_hash: str | None,
		current_hash: str | None,
		base: dict[str, object] | None,
		current: dict[str, object] | None,
		proposed: dict[str, object] | None,
	) -> None:
		super().__init__(f"Record '{record_id}' changed after it was loaded.")
		self.record_id = record_id
		self.expected_hash = expected_hash
		self.current_hash = current_hash
		self.base = base
		self.current = current
		self.proposed = proposed

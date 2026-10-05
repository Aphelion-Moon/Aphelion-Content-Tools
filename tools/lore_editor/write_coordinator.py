from __future__ import annotations

import hashlib
import os
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Lock, RLock, local

_repository_locks: dict[str, RLock] = {}
_repository_locks_guard = Lock()
_held = local()


@contextmanager
def repository_write_lock(repo_root: Path) -> Iterator[None]:
	key = os.path.normcase(str(repo_root.resolve()))
	with _repository_locks_guard:
		lock = _repository_locks.setdefault(key, RLock())
	with lock:
		depths = getattr(_held, 'depths', None)
		if depths is None:
			depths = _held.depths = {}
		if key in depths:
			yield
			return
		# Keep the coordination file outside authored trees. Never unlink it: another
		# process may already be waiting on that inode/handle when we release it.
		name = hashlib.sha256(os.path.normcase(key).encode()).hexdigest()
		lock_root = Path(tempfile.gettempdir()) / 'aphelion-content-tools-write-locks'
		lock_root.mkdir(exist_ok=True)
		with (lock_root / f'{name}.lock').open('a+b') as handle:
			handle.seek(0, 2)
			if handle.tell() == 0:
				handle.write(b'\0')
				handle.flush()
			handle.seek(0)
			if os.name == 'nt':
				import msvcrt
				deadline = time.monotonic() + 120
				while True:
					try:
						msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
						break
					except OSError:
						if time.monotonic() >= deadline:
							raise TimeoutError('Another process is still writing this repository.') from None
						time.sleep(0.05)
			else:
				import fcntl
				fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
			depths[key] = True
			try:
				yield
			finally:
				del depths[key]
				handle.seek(0)
				if os.name == 'nt':
					msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
				else:
					fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


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

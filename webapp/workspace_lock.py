from __future__ import annotations

import ctypes
import json
import os
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from ctypes import wintypes
from pathlib import Path
from typing import TypeVar

LEASE_RELATIVE_PATH = Path("webapp/store/workspace-lease.json")
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 2.0
_T = TypeVar('_T')


def _sharing_retry(operation: Callable[[], _T]) -> _T:
	"""Allow a brief Windows reader/atomic-replace overlap without losing the lease."""
	for attempt in range(4):
		try:
			return operation()
		except PermissionError:
			if attempt == 3:
				raise
			time.sleep(0.01)
	raise AssertionError('unreachable')


class WorkspaceLeaseConflict(RuntimeError):
	def __init__(self, workspace: Path, owner: dict[str, object]) -> None:
		self.workspace = workspace
		self.owner = owner
		session_id = owner.get("session_id", "unknown")
		pid = owner.get("pid", "unknown")
		super().__init__(f"Workspace is already owned by backend session {session_id} (PID {pid}).")


def _windows_process_start_identity(pid: int) -> str | None:
	process_query_limited_information = 0x1000
	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
	if not handle:
		return None
	creation = wintypes.FILETIME()
	exit_time = wintypes.FILETIME()
	kernel_time = wintypes.FILETIME()
	user_time = wintypes.FILETIME()
	try:
		if not kernel32.GetProcessTimes(
			handle,
			ctypes.byref(creation),
			ctypes.byref(exit_time),
			ctypes.byref(kernel_time),
			ctypes.byref(user_time),
		):
			return None
		return str((creation.dwHighDateTime << 32) | creation.dwLowDateTime)
	finally:
		kernel32.CloseHandle(handle)


def _posix_process_start_identity(pid: int) -> str | None:
	try:
		fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()
	except OSError:
		return None
	return fields[21] if len(fields) > 21 else None


def process_start_identity(pid: int) -> str | None:
	if os.name == "nt":
		return _windows_process_start_identity(pid)
	return _posix_process_start_identity(pid)


def _pid_exists(pid: int) -> bool:
	if pid <= 0:
		return False
	try:
		os.kill(pid, 0)
	except ProcessLookupError:
		return False
	except PermissionError:
		return True
	except OSError:
		return False
	return True


def _read_owner(path: Path) -> dict[str, object]:
	payload = json.loads(_sharing_retry(lambda: path.read_text(encoding="utf-8")))
	if not isinstance(payload, dict):
		raise ValueError("Workspace lease must contain a JSON object.")
	return payload


def _atomic_write_owner(path: Path, owner: dict[str, object]) -> None:
	data = json.dumps(owner, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
	file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
	temporary_path = Path(temporary_name)
	try:
		with os.fdopen(file_descriptor, "wb") as handle:
			handle.write(data)
			handle.flush()
			os.fsync(handle.fileno())
		_sharing_retry(lambda: os.replace(temporary_path, path))
	finally:
		temporary_path.unlink(missing_ok=True)


class WorkspaceLease:
	def __init__(
		self,
		workspace: Path,
		*,
		heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
	) -> None:
		if heartbeat_interval_seconds <= 0:
			raise ValueError("Heartbeat interval must be positive.")
		self.workspace = workspace.resolve()
		self.lock_path = self.workspace / LEASE_RELATIVE_PATH
		self.heartbeat_interval_seconds = heartbeat_interval_seconds
		self.session_id = uuid.uuid4().hex
		self._acquired = False
		self._stop = threading.Event()
		self._heartbeat_thread: threading.Thread | None = None

	@property
	def acquired(self) -> bool:
		return self._acquired

	@property
	def owner(self) -> dict[str, object]:
		return _read_owner(self.lock_path)

	def _new_owner(self) -> dict[str, object]:
		now = time.time()
		return {
			"pid": os.getpid(),
			"process_start_identity": process_start_identity(os.getpid()),
			"workspace": str(self.workspace),
			"session_id": self.session_id,
			"acquired_at": now,
			"heartbeat_at": now,
		}

	def _owner_is_demonstrably_stale(self, owner: dict[str, object]) -> bool:
		pid = owner.get("pid")
		if not isinstance(pid, int):
			return False
		if not _pid_exists(pid):
			return True
		recorded_identity = owner.get("process_start_identity")
		current_identity = process_start_identity(pid)
		return (
			isinstance(recorded_identity, str)
			and current_identity is not None
			and recorded_identity != current_identity
		)

	def _write_new_owner_exclusive(self, owner: dict[str, object]) -> None:
		self.lock_path.parent.mkdir(parents=True, exist_ok=True)
		data = json.dumps(owner, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
		file_descriptor = os.open(self.lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
		with os.fdopen(file_descriptor, "wb") as handle:
			handle.write(data)
			handle.flush()
			os.fsync(handle.fileno())

	def acquire(self) -> WorkspaceLease:
		if self._acquired:
			return self
		owner = self._new_owner()
		for _attempt in range(2):
			try:
				self._write_new_owner_exclusive(owner)
			except FileExistsError:
				try:
					existing_owner = _read_owner(self.lock_path)
				except (OSError, ValueError, json.JSONDecodeError):
					raise WorkspaceLeaseConflict(self.workspace, {"session_id": "unreadable", "pid": "unknown"}) from None
				if not self._owner_is_demonstrably_stale(existing_owner):
					raise WorkspaceLeaseConflict(self.workspace, existing_owner) from None
				self.lock_path.unlink(missing_ok=True)
				continue
			self._acquired = True
			self._stop.clear()
			self._heartbeat_thread = threading.Thread(target=self._heartbeat, daemon=True)
			self._heartbeat_thread.start()
			return self
		raise WorkspaceLeaseConflict(self.workspace, _read_owner(self.lock_path))

	def _heartbeat(self) -> None:
		while not self._stop.wait(self.heartbeat_interval_seconds):
			try:
				owner = _read_owner(self.lock_path)
				if owner.get("session_id") != self.session_id:
					self._acquired = False
					return
				owner["heartbeat_at"] = time.time()
				_atomic_write_owner(self.lock_path, owner)
			except (OSError, ValueError, json.JSONDecodeError):
				self._acquired = False
				return

	def release(self) -> None:
		self._stop.set()
		if self._heartbeat_thread is not None:
			self._heartbeat_thread.join(timeout=max(1.0, self.heartbeat_interval_seconds * 2))
			self._heartbeat_thread = None
		try:
			owner = _read_owner(self.lock_path)
		except (OSError, ValueError, json.JSONDecodeError):
			self._acquired = False
			return
		if owner.get("session_id") == self.session_id:
			self.lock_path.unlink(missing_ok=True)
		self._acquired = False

	def __enter__(self) -> WorkspaceLease:
		return self.acquire()

	def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
		self.release()

from __future__ import annotations

import contextlib
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from multiprocessing.connection import Client
from pathlib import Path


@dataclass(frozen=True)
class ToolDefinition:
	id: str
	label: str
	description: str
	tool_root: str
	commands: tuple[tuple[str, ...], ...]
	game_repo_commands: frozenset[str] = frozenset()


def list_tools(definitions: tuple[ToolDefinition, ...]) -> list[dict[str, str]]:
	return [
		{"id": definition.id, "label": definition.label, "description": definition.description}
		for definition in definitions
	]


# Every tool run happens inside one persistent, warm worker process per repo root (see
# `webapp/store_worker.py`) instead of a fresh `python cli.py` subprocess per click -- spawning a whole
# interpreter and re-loading the ~130MB embedding model from scratch on every button click was the real
# cost behind "the python app is pulling a significant cpu and memory load", independent of how little
# data actually changed. This module is the client half: it starts/reconnects to that worker over a
# local named pipe and forwards requests to it, translating its responses back into the same shape
# (and exceptions) callers already expect.
WORKER_START_TIMEOUT_SECONDS = 20.0
WORKER_POLL_INTERVAL_SECONDS = 0.05
WORKER_SHUTDOWN_TIMEOUT_SECONDS = 5.0


class _WorkerHandle:
	def __init__(self, repo_root: Path) -> None:
		self.repo_root = repo_root.resolve()
		self.process: subprocess.Popen | None = None
		self.lock = threading.Lock()

	@property
	def address(self) -> str:
		from .store_worker import pipe_address
		return pipe_address(self.repo_root)

	@property
	def startup_log_path(self) -> Path:
		return self.repo_root / "tools/logs/store-worker-startup.log"

	def _startup_diagnostics(self) -> str:
		try:
			text = self.startup_log_path.read_text(encoding="utf-8", errors="replace")
		except OSError:
			return "No worker startup log was available."
		return text[-8_000:] or "The worker startup log was empty."

	def ensure_started(self) -> None:
		with self.lock:
			if self.process is not None and self.process.poll() is None:
				return
			# Run store_worker.py by path, not "-m webapp.store_worker": the worker's job is to operate
			# on `self.repo_root` (which may be an arbitrary --repo-root, including a temp directory in
			# tests) -- it must not be confused with *this* installation's own directory, which is what
			# the child process actually needs on its import path to find the `webapp`/`tools` packages.
			worker_script = Path(__file__).resolve().with_name("store_worker.py")
			self.startup_log_path.parent.mkdir(parents=True, exist_ok=True)
			with self.startup_log_path.open("a", encoding="utf-8", newline="") as startup_log:
				startup_log.write(f"\nStarting store worker for {self.repo_root}.\n")
				startup_log.flush()
				self.process = subprocess.Popen(
					[sys.executable, str(worker_script), "--repo-root", str(self.repo_root)],
					stdin=subprocess.DEVNULL,
					stdout=startup_log,
					stderr=subprocess.STDOUT,
				)
			self._wait_until_reachable()

	def _wait_until_reachable(self) -> None:
		from .store_worker import AUTH_KEY

		deadline = _now() + WORKER_START_TIMEOUT_SECONDS
		last_error: Exception | None = None
		while _now() < deadline:
			if self.process.poll() is not None:
				raise RuntimeError(
					"The store worker process exited immediately on startup.\n"
					f"Startup diagnostics:\n{self._startup_diagnostics()}"
				)
			try:
				with Client(self.address, family="AF_PIPE", authkey=AUTH_KEY):
					return
			except OSError as exc:
				last_error = exc
				_sleep(WORKER_POLL_INTERVAL_SECONDS)
		raise RuntimeError(
			f"Store worker did not become reachable in time: {last_error}\n"
			f"Startup diagnostics:\n{self._startup_diagnostics()}"
		)

	def shut_down(self) -> None:
		with self.lock:
			if self.process is None:
				return
			with contextlib.suppress(OSError):
				_send(self.address, {"action": "shutdown", "repo_root": str(self.repo_root)})
			try:
				self.process.wait(timeout=WORKER_SHUTDOWN_TIMEOUT_SECONDS)
			except subprocess.TimeoutExpired:
				self.process.kill()
				self.process.wait(timeout=WORKER_SHUTDOWN_TIMEOUT_SECONDS)
			self.process = None


def _now() -> float:
	return time.monotonic()


def _sleep(seconds: float) -> None:
	time.sleep(seconds)


def _send(address: str, message: dict[str, object]) -> dict[str, object]:
	from .store_worker import AUTH_KEY
	with Client(address, family="AF_PIPE", authkey=AUTH_KEY) as conn:
		conn.send(message)
		return conn.recv()


_workers: dict[str, _WorkerHandle] = {}
_workers_lock = threading.Lock()


def _get_worker(repo_root: Path) -> _WorkerHandle:
	resolved = repo_root.resolve()
	key = str(resolved)
	with _workers_lock:
		handle = _workers.get(key)
		if handle is None:
			handle = _WorkerHandle(resolved)
			_workers[key] = handle
	return handle


def _request(handle: _WorkerHandle, message: dict[str, object]) -> dict[str, object]:
	message = {**message, "repo_root": str(handle.repo_root)}
	handle.ensure_started()
	try:
		response = _send(handle.address, message)
	except (OSError, EOFError):
		# The worker died between calls (crashed, was killed) -- respawn once and retry. This is the
		# actual payoff of moving execution into its own process: a bug in job code can only take down
		# the worker, never the always-on HTTP server, and the server can recover instead of every
		# subsequent click just failing forever.
		handle.ensure_started()
		response = _send(handle.address, message)
	if not response.get("ok"):
		error_type = response.get("error_type")
		error_message = str(response.get("error") or "Unknown store worker error.")
		if error_type == "ValueError":
			raise ValueError(error_message)
		raise RuntimeError(error_message)
	return response["result"]  # type: ignore[return-value]


def start_tool(
	repo_root: Path,
	definitions: tuple[ToolDefinition, ...],
	tool_id: str,
	*,
	game_repo_root: Path | None = None,
) -> dict[str, object]:
	if not any(definition.id == tool_id for definition in definitions):
		raise ValueError(f"Unknown tool '{tool_id}'.")
	handle = _get_worker(repo_root)
	message = {"action": "start", "tool_id": tool_id}
	if game_repo_root is not None:
		message["game_repo_root"] = str(game_repo_root.resolve())
	return _request(handle, message)


def list_active_runs(repo_root: Path) -> list[dict[str, object]]:
	"""Currently queued/running jobs for `repo_root`, for a sidebar "what's happening right now" widget
	shown on every page -- unlike `start_tool`, this must never spawn a worker as a side effect of merely
	checking: most pages never start a job, and a status widget polling every few seconds would otherwise
	spin up (and keep alive) a store worker just by existing. Returns `[]` whenever there's nothing to
	ask -- no worker ever started for this repo root, or its process has already exited -- without any
	IPC or subprocess spawn."""
	key = str(repo_root.resolve())
	with _workers_lock:
		handle = _workers.get(key)
	if handle is None or handle.process is None or handle.process.poll() is not None:
		return []
	try:
		response = _send(handle.address, {"action": "list_active", "repo_root": str(handle.repo_root)})
	except (OSError, EOFError):
		return []
	if not response.get("ok"):
		return []
	return response["result"]  # type: ignore[return-value]


def get_tool_run(repo_root: Path, run_id: str) -> dict[str, object]:
	return _request(_get_worker(repo_root), {"action": "status", "run_id": run_id})


def stop_tool(repo_root: Path, run_id: str) -> dict[str, object]:
	return _request(_get_worker(repo_root), {"action": "stop", "run_id": run_id})


def shut_down_worker(repo_root: Path) -> None:
	"""Cleanly stop the worker for `repo_root`, if one was ever started.

	Must be called when the main server shuts down: an unmanaged leftover worker process is exactly the
	orphaned-process failure mode this project has already hit once with a hung `catalog-refresh` -- the
	fix here must not reintroduce a new variant of the same bug."""
	key = str(repo_root.resolve())
	with _workers_lock:
		handle = _workers.get(key)
	if handle is not None:
		handle.shut_down()

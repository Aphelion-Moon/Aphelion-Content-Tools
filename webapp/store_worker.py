from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import sys
import tempfile
import threading
import time
import uuid
from contextlib import redirect_stderr, redirect_stdout, suppress
from multiprocessing.connection import Listener
from pathlib import Path

if __package__ in (None, ""):
	sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
	from webapp.tool_registry import load_tool_registry
	from webapp.tooling import ToolDefinition
else:
	from .tool_registry import load_tool_registry
	from .tooling import ToolDefinition

MAX_OUTPUT_CHARACTERS = 64_000
MAX_LOG_CHARACTERS = 1_000_000
MAX_RETAINED_RUNS = 200
LOG_ROOT = Path("tools/logs")
RUN_STATE_ROOT = LOG_ROOT / "runs"


def pipe_address(repo_root: Path, launch_nonce: str | None = None) -> str:
	"""Return the per-launch Windows pipe address for one checkout."""
	digest = hashlib.sha256(str(repo_root.resolve()).encode("utf-8")).hexdigest()[:16]
	if launch_nonce is not None and (
		len(launch_nonce) != 32 or any(character not in "0123456789abcdef" for character in launch_nonce.casefold())
	):
		raise ValueError("Store worker launch nonce is invalid.")
	suffix = f"-{launch_nonce}" if launch_nonce else ""
	return rf"\\.\pipe\aphelion-store-worker-{digest}{suffix}"


class JobCancelled(Exception):
	"""Raised from inside a running job when a stop has been requested."""


class _RunOutputStream(io.TextIOBase):
	"""Redirect target for a job's stdout/stderr while it runs.

	Every `print(...)` a tool's `cli.main()` makes becomes a `write()` call here, which appends the text
	to the run's in-memory output and log file. Output remains a cancellation point, while the worker's
	per-line trace handles silent Python work independently of whether the tool prints progress.
	"""

	def __init__(self, worker: Worker, run_id: str) -> None:
		super().__init__()
		self._worker = worker
		self._run_id = run_id

	def write(self, text: str) -> int:
		if text:
			self._worker.append_output(self._run_id, text)
		if self._worker.is_stop_requested(self._run_id):
			raise JobCancelled()
		return len(text)

	def flush(self) -> None:
		return None


def _load_cli_main(tool_root: str):
	if tool_root == "tools/lore_editor":
		from tools.lore_editor.cli import main as cli_main
	elif tool_root == "tools/content_graph":
		from tools.content_graph.cli import main as cli_main
	elif tool_root == "webapp/store":
		from webapp.store.cli import main as cli_main
	else:
		raise ValueError(f"Unknown tool root '{tool_root}'.")
	return cli_main


def _build_argv(
	repo_root: Path,
	definition: ToolDefinition,
	command_index: int,
	*,
	game_repo_root: Path | None,
) -> list[str]:
	if command_index < 0 or command_index >= len(definition.commands):
		raise ValueError(f"Tool '{definition.id}' has no command at index {command_index}.")
	argv = [*definition.commands[command_index], "--repo-root", str(repo_root)]
	if game_repo_root is not None and any(
		command_name in definition.game_repo_commands for command_name in definition.commands[command_index]
	):
		argv.extend(("--game-repo", str(game_repo_root)))
	return argv


class Worker:
	"""Owns every tool run for one repo root: run bookkeeping, one-job-at-a-time execution, and the
	named-pipe RPC loop client requests come in through."""

	def __init__(self, repo_root: Path) -> None:
		self.repo_root = repo_root.resolve()
		self._runs: dict[str, dict[str, object]] = {}
		# The cancellation trace checks the stop flag while traced tool code calls back into output and
		# bookkeeping helpers. A re-entrant lock prevents that same worker thread deadlocking itself.
		self._runs_lock = threading.RLock()
		self._run_lock = threading.Lock()  # held for the duration of a job -- one job at a time, ever
		self._load_run_state()

	def _state_path(self, run_id: str) -> Path:
		return self.repo_root / RUN_STATE_ROOT / f"{run_id}.json"

	def _persist_run_locked(self, run_id: str) -> None:
		run = self._runs[run_id]
		payload = {key: value for key, value in run.items() if key != "output"}
		payload["repo_root"] = str(self.repo_root)
		path = self._state_path(run_id)
		path.parent.mkdir(parents=True, exist_ok=True)
		data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
		file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{run_id}.", suffix=".tmp", dir=path.parent)
		temporary_path = Path(temporary_name)
		try:
			with os.fdopen(file_descriptor, "wb") as handle:
				handle.write(data)
				handle.flush()
				os.fsync(handle.fileno())
			os.replace(temporary_path, path)
		finally:
			temporary_path.unlink(missing_ok=True)

	def _read_log_tail(self, run_id: str) -> str:
		try:
			return (self.repo_root / LOG_ROOT / f"{run_id}.log").read_text(
				encoding="utf-8",
				errors="replace",
			)[-MAX_OUTPUT_CHARACTERS:]
		except OSError:
			return ""

	def _load_run_state(self) -> None:
		state_root = self.repo_root / RUN_STATE_ROOT
		try:
			paths = sorted(state_root.glob("*.json"), key=lambda path: path.stat().st_mtime)[-MAX_RETAINED_RUNS:]
		except OSError:
			return
		for path in paths:
			try:
				payload = json.loads(path.read_text(encoding="utf-8"))
				run_id = str(payload["run_id"])
				if run_id != path.stem or Path(str(payload["repo_root"])).resolve() != self.repo_root:
					continue
				status = str(payload["status"])
				if status not in ("queued", "running", "succeeded", "failed", "stopped"):
					continue
			except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
				continue
			payload.pop("repo_root", None)
			payload["output"] = self._read_log_tail(run_id)
			self._runs[run_id] = payload
			if status in ("queued", "running"):
				payload["status"] = "failed"
				payload["exit_code"] = None
				payload["stop_requested"] = False
				message = "Worker exited before job completed; rerun the operation.\n"
				payload["output"] = (str(payload["output"]) + message)[-MAX_OUTPUT_CHARACTERS:]
				self._append_log(run_id, message)
				self._persist_run_locked(run_id)

	def _update_run(self, run_id: str, **values: object) -> None:
		with self._runs_lock:
			self._runs[run_id].update(values)
			self._persist_run_locked(run_id)

	def append_output(self, run_id: str, text: str) -> None:
		with self._runs_lock:
			run = self._runs.get(run_id)
			if run is None:
				return
			run["output"] = (str(run.get("output", "")) + text)[-MAX_OUTPUT_CHARACTERS:]
		self._append_log(run_id, text)

	def _append_log(self, run_id: str, text: str) -> None:
		log_path = self.repo_root / LOG_ROOT / f"{run_id}.log"
		try:
			log_path.parent.mkdir(parents=True, exist_ok=True)
			if log_path.exists() and log_path.stat().st_size >= MAX_LOG_CHARACTERS:
				return
			with log_path.open("a", encoding="utf-8", newline="") as log_file:
				log_file.write(text)
		except OSError:
			return

	def is_stop_requested(self, run_id: str) -> bool:
		with self._runs_lock:
			run = self._runs.get(run_id)
			return bool(run and run.get("stop_requested"))

	def _raise_if_cancelled(self, run_id: str) -> None:
		if self.is_stop_requested(run_id):
			raise JobCancelled()

	def _cancellation_trace(self, run_id: str):
		def check_cancelled(frame, event, arg):
			self._raise_if_cancelled(run_id)
			return check_cancelled

		return check_cancelled

	def start(self, definition: ToolDefinition, game_repo_root: Path | None) -> dict[str, object]:
		run_id = uuid.uuid4().hex
		log_path = LOG_ROOT / f"{run_id}.log"
		with self._runs_lock:
			self._runs[run_id] = {
				"run_id": run_id,
				"tool_id": definition.id,
				"status": "queued",
				"output": "",
				"exit_code": None,
				"log_path": log_path.as_posix(),
				"stop_requested": False,
				"queued_at": time.time(),
			}
			self._persist_run_locked(run_id)
			self._evict_old_runs_locked()
		self._append_log(run_id, f"Queued {definition.id}.\n")
		thread = threading.Thread(target=self._execute, args=(run_id, definition, game_repo_root), daemon=True)
		thread.start()
		return self.status(run_id)

	def list_active(self) -> list[dict[str, object]]:
		"""Runs that are currently queued or running -- for a "what's happening right now" summary (see
		the sidebar status widget), not the full run history `status()` already covers per-run. Deliberately
		trimmed to just the fields a summary needs (not `output`, which can be up to `MAX_OUTPUT_CHARACTERS`
		and would otherwise be re-sent whole on every few-second poll from every open page)."""
		with self._runs_lock:
			return [
				{"run_id": run["run_id"], "tool_id": run["tool_id"], "status": run["status"], "queued_at": run["queued_at"]}
				for run in self._runs.values()
				if run["status"] in ("queued", "running")
			]

	def _evict_old_runs_locked(self) -> None:
		if len(self._runs) <= MAX_RETAINED_RUNS:
			return
		finished_ids = [run_id for run_id, run in self._runs.items() if run["status"] in ("succeeded", "failed", "stopped")]
		excess = len(self._runs) - MAX_RETAINED_RUNS
		for run_id in finished_ids[:excess]:
			del self._runs[run_id]
			with suppress(OSError):
				self._state_path(run_id).unlink()

	def _execute(self, run_id: str, definition: ToolDefinition, game_repo_root: Path | None) -> None:
		with self._run_lock:  # serializes every job against every other -- never two writers at once
			self._update_run(run_id, status="running")
			self.append_output(run_id, f"Starting {definition.id}.\n")
			try:
				self._raise_if_cancelled(run_id)
				for command_index in range(len(definition.commands)):
					cli_main = _load_cli_main(definition.tool_root)
					argv = _build_argv(self.repo_root, definition, command_index, game_repo_root=game_repo_root)
					self.append_output(run_id, f"Command {command_index + 1}: {' '.join(argv)}\n")
					stream = _RunOutputStream(self, run_id)
					previous_trace = sys.gettrace()
					sys.settrace(self._cancellation_trace(run_id))
					try:
						with redirect_stdout(stream), redirect_stderr(stream):
							return_code = cli_main(argv)
					finally:
						sys.settrace(previous_trace)
					self._raise_if_cancelled(run_id)
					if return_code != 0:
						self.append_output(run_id, f"Command exited with code {return_code}.\n")
						self._update_run(run_id, status="failed", exit_code=return_code)
						return
				self._update_run(run_id, status="succeeded", exit_code=0)
				self.append_output(run_id, "Completed successfully.\n")
			except JobCancelled:
				self.append_output(run_id, "Stopped by user request.\n")
				self._update_run(run_id, status="stopped", exit_code=None)
			except Exception as exc:
				self.append_output(run_id, f"error: {exc}\n")
				self._update_run(run_id, status="failed", exit_code=None)

	def status(self, run_id: str) -> dict[str, object]:
		with self._runs_lock:
			if run_id not in self._runs:
				raise ValueError(f"Unknown tool run '{run_id}'.")
			return dict(self._runs[run_id])

	def stop(self, run_id: str) -> dict[str, object]:
		with self._runs_lock:
			if run_id not in self._runs:
				raise ValueError(f"Unknown tool run '{run_id}'.")
			self._runs[run_id]["stop_requested"] = True
			self._persist_run_locked(run_id)
		return self.status(run_id)


def _validate_request_repo(worker: Worker, request: dict[str, object]) -> None:
	claimed_root = request.get("repo_root")
	if not isinstance(claimed_root, str) or Path(claimed_root).resolve() != worker.repo_root:
		raise ValueError("Tool request repository does not match the worker repository.")


def _handle_connection(worker: Worker, definitions: tuple[ToolDefinition, ...], conn) -> bool:
	"""Handle one request on `conn`. Returns True if the worker should keep serving, False on shutdown."""
	try:
		request = conn.recv()
		_validate_request_repo(worker, request)
		action = request.get("action")
		if action == "shutdown":
			conn.send({"ok": True, "result": None})
			return False
		if action == "start":
			tool_id = request["tool_id"]
			definition = next((item for item in definitions if item.id == tool_id), None)
			if definition is None:
				raise ValueError(f"Unknown tool '{tool_id}'.")
			game_repo_root = request.get("game_repo_root")
			result = worker.start(definition, Path(game_repo_root) if game_repo_root else None)
		elif action == "status":
			result = worker.status(request["run_id"])
		elif action == "stop":
			result = worker.stop(request["run_id"])
		elif action == "list_active":
			result = worker.list_active()
		else:
			raise ValueError(f"Unknown action '{action}'.")
		conn.send({"ok": True, "result": result})
	except Exception as exc:
		with suppress(OSError):
			conn.send({"ok": False, "error_type": type(exc).__name__, "error": str(exc)})
	return True


def _launch_credentials() -> tuple[str, bytes]:
	launch_nonce = os.environ.get("APHELION_STORE_WORKER_NONCE", "")
	encoded_authkey = os.environ.get("APHELION_STORE_WORKER_AUTHKEY", "")
	if not launch_nonce or not encoded_authkey:
		raise RuntimeError("Store worker launch credentials are missing.")
	try:
		authkey = base64.urlsafe_b64decode(encoded_authkey.encode("ascii"))
	except (ValueError, UnicodeError) as exc:
		raise RuntimeError("Store worker launch credentials are invalid.") from exc
	if len(authkey) < 32:
		raise RuntimeError("Store worker launch credentials are invalid.")
	return launch_nonce, authkey


def serve(repo_root: Path, *, launch_nonce: str | None = None, authkey: bytes | None = None) -> None:
	worker = Worker(repo_root)
	definitions = load_tool_registry()
	if launch_nonce is None or authkey is None:
		environment_nonce, environment_authkey = _launch_credentials()
		launch_nonce = launch_nonce or environment_nonce
		authkey = authkey or environment_authkey
	address = pipe_address(repo_root, launch_nonce)
	listener = Listener(address=address, family="AF_PIPE", authkey=authkey)
	try:
		while True:
			conn = listener.accept()
			try:
				if not _handle_connection(worker, definitions, conn):
					return
			finally:
				conn.close()
	finally:
		listener.close()


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Persistent worker process for store-backed tool runs.")
	parser.add_argument("--repo-root", type=Path, required=True)
	return parser


def main(argv: list[str] | None = None) -> int:
	args = build_parser().parse_args(argv)
	serve(args.repo_root.resolve())
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

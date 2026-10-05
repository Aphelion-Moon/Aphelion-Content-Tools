from __future__ import annotations

import argparse
import json
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import BinaryIO

from webapp.process_tree import KillOnCloseJob

_TRUNCATION_MARKER = b"\n[log truncated: output exceeded configured byte limit]\n"
_RESOURCE_WARNING = b"ResourceWarning"


@dataclass(frozen=True)
class SuiteResult:
	"""Summarize one bounded command execution."""

	name: str
	status: str
	exit_code: int | None
	duration_seconds: float
	log_path: str
	log_truncated: bool
	resource_warning_detected: bool
	peak_memory_bytes: int | None


def _drain_output(
	stream: BinaryIO,
	captured: bytearray,
	max_log_bytes: int,
	truncated: list[bool],
	resource_warning: list[bool],
) -> None:
	tail = b""
	while chunk := stream.read(65536):
		candidate = tail + chunk
		if _RESOURCE_WARNING in candidate:
			resource_warning[0] = True
		tail = candidate[-(len(_RESOURCE_WARNING) - 1) :]
		remaining = max_log_bytes - len(captured)
		if remaining > 0:
			captured.extend(chunk[:remaining])
		if len(chunk) > remaining:
			truncated[0] = True


def run_command(
	*,
	name: str,
	command: tuple[str, ...],
	working_directory: Path,
	log_path: Path,
	timeout_seconds: float,
	max_log_bytes: int,
) -> SuiteResult:
	"""Run one command with an owned process tree, timeout, and bounded captured log."""

	if not command:
		raise ValueError("command must not be empty")
	if timeout_seconds <= 0:
		raise ValueError("timeout_seconds must be positive")
	if max_log_bytes <= 0:
		raise ValueError("max_log_bytes must be positive")
	working_directory = working_directory.resolve()
	log_path = log_path.resolve()
	log_path.parent.mkdir(parents=True, exist_ok=True)
	owner = KillOnCloseJob()
	captured = bytearray()
	truncated = [False]
	resource_warning = [False]
	peak_memory_bytes: int | None = None
	started = time.monotonic()
	process = subprocess.Popen(
		command,
		cwd=working_directory,
		stdout=subprocess.PIPE,
		stderr=subprocess.STDOUT,
	)
	try:
		owner.assign(process.pid)
		assert process.stdout is not None
		reader = threading.Thread(
			target=_drain_output,
			args=(process.stdout, captured, max_log_bytes, truncated, resource_warning),
			name=f"{name}-output",
			daemon=True,
		)
		reader.start()
		timed_out = False
		try:
			process.wait(timeout=timeout_seconds)
		except subprocess.TimeoutExpired:
			timed_out = True
			peak_memory_bytes = owner.peak_memory_bytes()
			owner.close()
			process.wait(timeout=5)
		if peak_memory_bytes is None:
			peak_memory_bytes = owner.peak_memory_bytes()
		reader.join(timeout=5)
		if reader.is_alive():
			raise RuntimeError(f"suite {name!r} output reader did not stop")
	finally:
		if process.stdout is not None:
			process.stdout.close()
		owner.close()
		if process.poll() is None:
			process.kill()
			process.wait(timeout=5)

	log = bytes(captured)
	if truncated[0]:
		log += _TRUNCATION_MARKER
	log_path.write_bytes(log)
	duration_seconds = time.monotonic() - started
	if timed_out:
		status = "timed_out"
		exit_code = None
	else:
		exit_code = process.returncode
		if exit_code != 0:
			status = "failed"
		elif resource_warning[0]:
			status = "resource_warning"
		else:
			status = "passed"
	return SuiteResult(
		name=name,
		status=status,
		exit_code=exit_code,
		duration_seconds=duration_seconds,
		log_path=str(log_path),
		log_truncated=truncated[0],
		resource_warning_detected=resource_warning[0],
		peak_memory_bytes=peak_memory_bytes,
	)


def main() -> int:
	parser = argparse.ArgumentParser(description="Run one owned process tree with bounded output.")
	parser.add_argument("--name", required=True)
	parser.add_argument("--working-directory", type=Path, required=True)
	parser.add_argument("--log-path", type=Path, required=True)
	parser.add_argument("--timeout-seconds", type=float, required=True)
	parser.add_argument("--max-log-bytes", type=int, required=True)
	parser.add_argument("command", nargs=argparse.REMAINDER)
	args = parser.parse_args()
	command = tuple(args.command[1:] if args.command[:1] == ["--"] else args.command)
	result = run_command(
		name=args.name,
		command=command,
		working_directory=args.working_directory,
		log_path=args.log_path,
		timeout_seconds=args.timeout_seconds,
		max_log_bytes=args.max_log_bytes,
	)
	print(json.dumps(asdict(result)))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

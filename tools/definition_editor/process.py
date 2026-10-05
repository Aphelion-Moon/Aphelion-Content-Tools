from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from contextlib import suppress
from pathlib import Path

from webapp.process_tree import KillOnCloseJob


class Cancelled(Exception):
	pass


class RunContext:
	"""One cancellable native operation, with a bounded log and owned descendants."""
	def __init__(self, directory: Path, cancel: threading.Event, *, max_log_bytes: int = 2_000_000) -> None:
		self.directory = directory
		self.cancel = cancel
		self.max_log_bytes = max_log_bytes
		self.output = bytearray()

	def check(self) -> None:
		if self.cancel.is_set():
			raise Cancelled('Operation cancelled.')

	def command(self, command: list[str], cwd: Path, *, timeout: float, ready: threading.Event | None = None, env: dict[str, str] | None = None) -> None:
		self.check()
		owner = KillOnCloseJob()
		gate = [sys.executable, '-I', '-S', str(Path(__file__).with_name('_child.py')), json.dumps(command)]
		process = subprocess.Popen(gate, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
			creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0, start_new_session=os.name != 'nt')
		reader: threading.Thread | None = None
		try:
			owner.assign(process.pid)
			assert process.stdin is not None
			process.stdin.write(b'1')
			process.stdin.close()
			assert process.stdout is not None
			def drain() -> None:
				assert process.stdout is not None
				while chunk := os.read(process.stdout.fileno(), 65536):
					remaining = self.max_log_bytes - len(self.output)
					if remaining > 0:
						self.output.extend(chunk[:remaining])
			reader = threading.Thread(target=drain, daemon=True, name='definition-preview-log')
			reader.start()
			if ready:
				ready.set()
			deadline = time.monotonic() + timeout
			while process.poll() is None:
				self.check()
				if time.monotonic() >= deadline:
					raise TimeoutError('Native authoring operation exceeded its time limit.')
				self.cancel.wait(0.1)
			if process.returncode:
				raise ValueError(f'Native authoring command failed with exit {process.returncode}. See the run log.')
		finally:
			if process.stdin and not process.stdin.closed:
				process.stdin.close()
			owner.close()
			if os.name != 'nt':
				with suppress(ProcessLookupError):
					os.killpg(process.pid, signal.SIGKILL)
			if process.poll() is None:
				process.kill()
			process.wait(timeout=10)
			if reader:
				reader.join(timeout=5)
			if process.stdout:
				process.stdout.close()
			self.directory.mkdir(parents=True, exist_ok=True)
			(self.directory / 'run.log').write_bytes(bytes(self.output))

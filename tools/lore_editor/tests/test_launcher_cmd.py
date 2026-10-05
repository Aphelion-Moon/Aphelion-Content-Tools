from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

LAUNCHER_CMD_PATH = Path(__file__).resolve().parents[3] / "Launch Aphelion Content Tools.cmd"
LAUNCHER_PS1_PATH = Path(__file__).resolve().parents[3] / "tools" / "launcher" / "launch.ps1"


class LauncherCmdArgumentQuotingTests(unittest.TestCase):
	"""Regression coverage for the launcher batch file's own argument quoting.

	`%~dp0` always expands with a trailing backslash. Quoting it bare as `"%~dp0"` hits a classic
	Windows argument-parsing hazard: a backslash immediately before a closing quote escapes the quote
	into a literal character instead of ending the string, so PowerShell receives a path with a
	stray trailing `"` and Resolve-Path fails with "Illegal characters in path". This is exercised
	against real cmd.exe, with a stub launch.ps1 standing in for the real one so the test does not
	need to start an actual server.
	"""

	def test_launcher_does_not_quote_a_bare_trailing_backslash(self) -> None:
		launcher_text = LAUNCHER_CMD_PATH.read_text(encoding="utf-8")

		self.assertNotIn('-RepositoryRoot "%~dp0"', launcher_text)

	def test_repository_root_argument_survives_cmd_exe_quoting(self) -> None:
		launcher_text = LAUNCHER_CMD_PATH.read_text(encoding="utf-8")

		with tempfile.TemporaryDirectory() as temp_dir:
			temp_root = Path(temp_dir)
			(temp_root / "tools" / "launcher").mkdir(parents=True)
			(temp_root / "tools" / "launcher" / "launch.ps1").write_text(
				"param([Parameter(Mandatory=$true)][string]$RepositoryRoot)\n"
				"$resolved = (Resolve-Path -LiteralPath $RepositoryRoot).Path\n"
				"Write-Output \"RESOLVED=$resolved\"\n",
				encoding="utf-8",
			)
			batch_path = temp_root / "Launch Lore Tools.cmd"
			batch_path.write_text(launcher_text, encoding="utf-8")

			result = subprocess.run(
				["cmd.exe", "/c", "call", str(batch_path)],
				cwd=temp_root,
				capture_output=True,
				text=True,
				timeout=20,
			)

		combined_output = result.stdout + result.stderr
		self.assertNotIn("Illegal characters in path", combined_output)
		self.assertIn(f"RESOLVED={temp_root}", combined_output)


@unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"), "requires Windows PowerShell")
class LauncherProcessLifecycleTests(unittest.TestCase):
	@staticmethod
	def _write_fixture(server_source: str) -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
		temporary_directory = tempfile.TemporaryDirectory()
		root = Path(temporary_directory.name)
		(root / "tools" / "launcher").mkdir(parents=True)
		(root / "tools" / "lore_editor").mkdir(parents=True)
		(root / "webapp" / "frontend" / "dist").mkdir(parents=True)
		(root / "localappdata" / "AphelionContentTools").mkdir(parents=True)
		(root / "localappdata" / "AphelionContentTools" / "settings.json").write_text(
			'{"gameRepository":"' + str(root).replace('\\', '\\\\') + '"}', encoding="utf-8"
		)
		shutil.copy2(LAUNCHER_PS1_PATH, root / "tools" / "launcher" / "launch.ps1")
		(root / "tools" / "launcher" / "runtime_manifest.json").write_text(
			'{"version":"3.11.0","architecture":"amd64","installer_url":"","signature_subject_contains":""}',
			encoding="utf-8",
		)
		(root / "tools" / "lore_editor" / "requirements.txt").write_text("", encoding="utf-8")
		(root / "tools" / "lore_editor" / "cli.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
		(root / "webapp" / "frontend" / "dist" / "index.html").write_text("<html></html>\n", encoding="utf-8")
		(root / "webapp" / "serve_api.py").write_text(server_source, encoding="utf-8")
		return temporary_directory, root, root / "server.pid"

	@staticmethod
	def _launch(root: Path, marker: Path) -> subprocess.Popen[str]:
		environment = os.environ.copy()
		environment["LOCALAPPDATA"] = str(root / "localappdata")
		environment["APHELION_TEST_SERVER_MARKER"] = str(marker)
		return subprocess.Popen(
			[
				"powershell.exe",
				"-NoProfile",
				"-ExecutionPolicy",
				"Bypass",
				"-File",
				str(root / "tools" / "launcher" / "launch.ps1"),
				"-RepositoryRoot",
				str(root),
			],
			stdin=subprocess.PIPE,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			text=True,
			env=environment,
		)

	@staticmethod
	def _wait_for_file(path: Path, process: subprocess.Popen[str]) -> None:
		# The launcher's dependency probe imports fastembed and can take several seconds on a cold
		# interpreter before it starts the fixture server.
		deadline = time.monotonic() + 45
		while time.monotonic() < deadline and not path.exists():
			if process.poll() is not None:
				break
			time.sleep(0.05)
		if not path.exists():
			if process.poll() is None:
				process.kill()
			stdout, stderr = process.communicate(timeout=10)
			raise AssertionError(f"fixture did not start; stdout={stdout!r}, stderr={stderr!r}")

	@staticmethod
	def _process_exists(pid: int) -> bool:
		result = subprocess.run(
			["tasklist.exe", "/FI", f"PID eq {pid}"],
			capture_output=True,
			text=True,
			check=False,
		)
		return str(pid) in result.stdout

	def test_server_stderr_cannot_block_launcher(self) -> None:
		server_source = """
import os
import pathlib
import sys
import time

pathlib.Path(os.environ['APHELION_TEST_SERVER_MARKER']).write_text(str(os.getpid()), encoding='ascii')
sys.stderr.write('x' * (2 * 1024 * 1024))
sys.stderr.flush()
time.sleep(0.2)
"""
		temporary_directory, root, marker = self._write_fixture(server_source)
		self.addCleanup(temporary_directory.cleanup)
		process = self._launch(root, marker)
		stdout, stderr = process.communicate("\n", timeout=60)

		self.assertNotEqual(process.returncode, 0)  # no URL is intentional: this avoids opening a browser.
		self.assertGreaterEqual(len(stderr), 2 * 1024 * 1024)
		self.assertIn("could not start its local server", stdout + stderr)

	def test_owned_server_dies_when_launcher_process_is_killed(self) -> None:
		server_source = """
import os
import pathlib
import time

pathlib.Path(os.environ['APHELION_TEST_SERVER_MARKER']).write_text(str(os.getpid()), encoding='ascii')
time.sleep(120)
"""
		temporary_directory, root, marker = self._write_fixture(server_source)
		self.addCleanup(temporary_directory.cleanup)
		process = self._launch(root, marker)
		try:
			self._wait_for_file(marker, process)
			server_pid = int(marker.read_text(encoding="ascii"))
			process.kill()
			process.wait(timeout=10)
			deadline = time.monotonic() + 10
			while time.monotonic() < deadline and self._process_exists(server_pid):
				time.sleep(0.1)
			self.assertFalse(self._process_exists(server_pid), f"owned server {server_pid} survived launcher death")
		finally:
			if process.poll() is None:
				process.kill()
				process.wait(timeout=10)
			process.communicate(timeout=10)


if __name__ == "__main__":
	unittest.main()

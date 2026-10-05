from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterable
from contextlib import suppress
from pathlib import Path

from webapp.json_storage import canonical_json_bytes
from webapp.path_safety import resolve_repo_path
from webapp.store.metadata import store_root

from .models import EditorRun, PreviewRequest, SourceInput
from .process import Cancelled, RunContext
from .source import decode_source


def byond_binary(name: str) -> Path:
	# Windows BYOND ships DreamDaemon.exe; dd.exe on PATH may be coreutils.
	if name.casefold() == 'dd.exe':
		name = 'DreamDaemon.exe'
	for executable in (shutil.which(name), *(str(Path(os.environ.get(variable, '')) / 'BYOND' / 'bin' / name) for variable in ('ProgramFiles(x86)', 'ProgramFiles'))):
		if executable and Path(executable).is_file():
			return Path(executable)
	return _missing(name)


def _missing(name: str) -> Path:
	raise ValueError(f'{name} is unavailable. Install BYOND to compile or run native previews.')


def create_source_directory(root: Path) -> Path:
	# BYOND still uses MAX_PATH for includes. Keep source outside the deeper run/log
	# hierarchy; a unique directory retains isolation between validated candidates.
	parent = store_root(root) / 'dm'
	parent.mkdir(parents=True, exist_ok=True)
	return Path(tempfile.mkdtemp(prefix='', dir=parent))


_RESOURCE_SUFFIXES = frozenset(('.dmi', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.ogg', '.wav', '.mp3', '.mid', '.midi', '.mod', '.xm', '.it', '.s3m', '.html', '.htm', '.css', '.js', '.svg', '.ttf', '.woff', '.woff2', '.otf', '.webp', '.webm', '.mp4'))


def _excluded_source(name: str) -> bool:
	parts = tuple(part.casefold() for part in Path(name).parts)
	return not parts or parts[0] in ('.git', 'data', 'config', 'logs', '.github') or any(part in ('node_modules', '__pycache__') for part in parts)


def _source_paths(root: Path, required_inputs: list[SourceInput], additional_sources: Iterable[bytes]) -> list[str]:
	result = subprocess.run(['git', '-C', str(root), 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], capture_output=True, check=True, timeout=60)
	names = {name for name in result.stdout.decode('utf-8').split('\0') if name and not _excluded_source(name)}
	for item in required_inputs:
		path = resolve_repo_path(root, Path(item.path))
		if '.git' in (part.casefold() for part in path.relative_to(root.resolve()).parts):
			raise ValueError('Git administration cannot be a private analysis input.')
		if item.path not in names:
			if Path(item.path).suffix not in ('.dm', '.dme', '.dmf', '.toml'):
				raise ValueError(f'Unsupported private analysis input: {item.path}')
			data = path.read_bytes()
			if hashlib.sha256(data).hexdigest() != item.sha256:
				raise ValueError('Generated analysis input changed during snapshot creation.')
			names.add(item.path)
	# Git ignore rules can hide compiled resources (for example an Icon directory).
	# Include only literal resource files named by source, never the ignored tree.
	def resources(data: bytes) -> None:
		text, _ = decode_source(data)
		for literal in re.findall(r"'([^'\r\n]+)'", text):
			name = literal.replace('\\', '/')
			if Path(name).suffix.casefold() not in _RESOURCE_SUFFIXES or _excluded_source(name):
				continue
			path = resolve_repo_path(root, Path(name))
			resolved_name = path.relative_to(root.resolve()).as_posix()
			if path.is_file() and not _excluded_source(resolved_name):
				names.add(resolved_name)
	for name in tuple(names):
		if Path(name).suffix in ('.dm', '.dme'):
			path = resolve_repo_path(root, Path(name))
			if path.is_file():
				resources(path.read_bytes())
	for data in additional_sources:
		resources(data)
	return sorted(names)


def source_fingerprint(root: Path, required_inputs: list[SourceInput], additional_sources: Iterable[bytes] = ()) -> str:
	digest = hashlib.sha256()
	for name in _source_paths(root, required_inputs, additional_sources):
		path = resolve_repo_path(root, Path(name))
		if '.git' in (part.casefold() for part in path.relative_to(root.resolve()).parts):
			raise ValueError('Git administration cannot be a private build input.')
		if path.is_file():
			digest.update(name.encode() + b'\0' + hashlib.sha256(path.read_bytes()).digest())
	return digest.hexdigest()


def copy_source(root: Path, destination: Path, run: RunContext, required_inputs: list[SourceInput] | None = None, additional_sources: Iterable[bytes] = ()) -> str:
	"""Copy build inputs, never runtime data, local secrets, or Git administration."""
	digest = hashlib.sha256()
	for name in _source_paths(root, required_inputs or [], additional_sources):
		run.check()
		path = resolve_repo_path(root, Path(name))
		if '.git' in (part.casefold() for part in path.relative_to(root.resolve()).parts):
			raise ValueError('Git administration cannot be a private build input.')
		if not path.is_file():
			continue
		data = path.read_bytes()
		digest.update(name.encode() + b'\0' + hashlib.sha256(data).digest())
		target = resolve_repo_path(destination, Path(name))
		target.parent.mkdir(parents=True, exist_ok=True)
		target.write_bytes(data)
	return digest.hexdigest()


def build_candidate(source: Path, run: RunContext, *, preview: bool = False) -> dict[str, str]:
	if os.name == 'nt':
		for path in source.rglob('*'):
			if path.is_file() and len(str(path.resolve()).encode('utf-16-le')) // 2 >= 260:
				raise ValueError(f'BYOND cannot read Windows paths of 260 characters or more. Move Content Tools to a shorter path before validating: {path.relative_to(source).as_posix()}')
	compiler = byond_binary('dm.exe')
	entry = source / 'tools/build/build.bat'
	if not entry.is_file():
		raise ValueError('The maintained Meridian build entry point is missing.')
	# Build tools inherit their normal toolchain lookup; record the actual compiler bytes separately.
	run.command([sys.executable, 'tools/build_bt.py', '--repo-root', str(source)], source, timeout=120)
	command = [str(entry), 'build']
	if preview:
		command.append('--define=CONTENT_TOOLS_PREVIEW')
	for suffix in ('dmb', 'rsc'):
		(source / f'tgstation.{suffix}').unlink(missing_ok=True)
	if os.name == 'nt':
		command = [os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c', *command]
	started = time.time_ns()
	run.command(command, source, timeout=1800, env={**os.environ, 'DM_EXE': str(compiler)})
	artifact = source / 'tgstation.dmb'
	if not artifact.is_file() or artifact.stat().st_mtime_ns < started - 2_000_000_000:
		raise ValueError('The build did not produce a fresh compiled game.')
	return {'compiler_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(), 'dmb_sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(), 'configuration': 'CONTENT_TOOLS_PREVIEW' if preview else 'production'}


def run_preview(source: Path, request: PreviewRequest, run: RunContext, state: EditorRun, publish: Callable[[], None], *, target_kind: str | None = None) -> None:
	build_candidate(source, run, preview=True)
	output = source / 'data/content_tools'
	output.mkdir(parents=True, exist_ok=True)
	result_path = output / 'result.json'
	result_path.unlink(missing_ok=True)
	daemon_log = output / 'daemon.log'
	daemon_log.unlink(missing_ok=True)
	def check_log_limit() -> None:
		if daemon_log.is_file() and daemon_log.stat().st_size > run.max_log_bytes:
			raise ValueError('Native preview log exceeded its size limit.')
	(output / 'request.json').write_bytes(canonical_json_bytes({'schema_version': 1, 'kind': target_kind or request.kind, 'type_path': request.type_path, 'species': request.species, 'body_gender': request.body_gender, 'body_type': request.body_type, 'mode': request.mode}))
	with socket.socket() as reservation:
		reservation.bind(('127.0.0.1', 0))
		port = reservation.getsockname()[1]
	command = [str(byond_binary('dd.exe')), str(source / 'tgstation.dmb'), str(port), '-invisible', '-trusted', '-log', 'data/content_tools/daemon.log']
	# DreamDaemon cannot bind an interface on all supported releases. The preview-only
	# harness rejects non-loopback clients and all Topic requests before normal startup.
	errors: list[BaseException] = []
	finished = threading.Event()
	def server() -> None:
		try:
			run.command(command, source, timeout=3600 if request.mode == 'interactive' else 180)
		except BaseException as exc:
			errors.append(exc)
		finally:
			finished.set()
	thread = threading.Thread(target=server, daemon=True, name='definition-preview-server')
	client_thread: threading.Thread | None = None
	thread.start()
	try:
		deadline = time.monotonic() + 120
		payload = None
		while payload is None:
			run.check()
			check_log_limit()
			with suppress(FileNotFoundError, json.JSONDecodeError):
				payload = json.loads(result_path.read_bytes())
			if payload is not None:
				break
			if finished.is_set():
				raise ValueError(f'Preview ended before readiness: {errors[0] if errors else "no result"}')
			if time.monotonic() >= deadline:
				raise TimeoutError('Preview did not become ready within two minutes.')
			run.cancel.wait(0.1)
		check_log_limit()
		if payload.get('schema_version') != 1 or payload.get('status') != 'ready':
			raise ValueError('Native preview failed: ' + '; '.join(payload.get('diagnostics', [])))
		for image in payload.get('images', []):
			path = resolve_repo_path(source, Path(image['file']))
			if not path.is_relative_to(output) or path.suffix != '.png' or path.stat().st_size > 10_000_000:
				raise ValueError('Native preview returned an invalid image artifact.')
			artifact = run.directory / 'images' / path.name
			artifact.parent.mkdir(parents=True, exist_ok=True)
			shutil.copyfile(path, artifact)
			state.images.append(artifact.relative_to(run.directory).as_posix())
		state.diagnostics.extend(payload.get('diagnostics', []))
		state.equipment = payload.get('equipment', [])
		state.preview_settings = {'type_path': request.type_path, 'species': request.species, 'body_gender': request.body_gender, 'body_type': request.body_type, 'mode': request.mode}
		state.status, state.message = 'ready', 'Native preview ready.'
		if request.mode == 'interactive':
			state.connection_url = f'byond://127.0.0.1:{port}'
		publish()
		if request.mode == 'interactive':
			client_context = RunContext(run.directory / 'client', run.cancel)
			def client() -> None:
				try:
					client_context.command([str(byond_binary('DreamSeeker.exe')), state.connection_url or ''], source, timeout=3600)
				except Cancelled:
					pass
				except Exception as exc:
					state.diagnostics.append(f'Client launch ended: {exc}. The private session remains available until stopped.')
					publish()
			client_thread = threading.Thread(target=client, daemon=True, name='definition-preview-client')
			client_thread.start()
			while not finished.wait(0.25):
				run.check()
				check_log_limit()
				try:
					current = json.loads(result_path.read_bytes())
				except (FileNotFoundError, json.JSONDecodeError):
					continue
				if current.get('status') == 'failed':
					state.images, state.equipment, state.connection_url = [], [], None
					raise ValueError('Native preview runtime failed: ' + '; '.join(current.get('diagnostics', [])))
			# The owned daemon may finish between the wait and the next check.
			# An explicit stop remains cancellation regardless of that ordering.
			run.check()
			if errors:
				raise ValueError(f'Native preview stopped: {errors[0]}')
	finally:
		# Explicitly stop the owned server for one-shot renders and all failed sessions.
		run.cancel.set()
		thread.join(timeout=15)
		if client_thread:
			client_thread.join(timeout=15)
		# DreamDaemon world.log is separate from stdout on Windows. Preserve its
		# diagnostics in the same bounded run log after the owned process stops.
		if daemon_log.is_file():
			remaining = max(0, run.max_log_bytes - len(run.output))
			with daemon_log.open('rb') as stream:
				run.output.extend(stream.read(remaining))
			run.directory.mkdir(parents=True, exist_ok=True)
			(run.directory / 'run.log').write_bytes(bytes(run.output))

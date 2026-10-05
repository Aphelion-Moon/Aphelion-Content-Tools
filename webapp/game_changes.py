from __future__ import annotations

import difflib
import hashlib
import json
import re
import secrets
import subprocess
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from tools.lore_editor.write_coordinator import repository_write_lock
from webapp.game_repository import validate_game_repository
from webapp.git_adapter import repository_revision, repository_status
from webapp.json_storage import atomic_write, canonical_json_bytes, rollback_files
from webapp.path_safety import resolve_repo_path


@dataclass(frozen=True)
class PreparedGameChange:
	stage_id: str
	base_revision: str
	preview: str
	paths: tuple[str, ...]


@dataclass(frozen=True)
class _Stage:
	public: PreparedGameChange
	expires: float
	files: tuple[tuple[str, str | None, bytes], ...]


class GameChangeSetService:
	"""Bounded, per-launch prepare/apply authority shared by tools that edit game files.

	Tools supply explicit path allowlists and proposed bytes. Browser input can only
	apply a server-held stage, never replace its revision, paths, hashes, or contents.
	Stages expire after 15 minutes and disappear when the backend restarts.
	"""

	def __init__(self, root: Path) -> None:
		self.root = root.resolve()
		self._stages: dict[str, _Stage] = {}
		self._lock = threading.RLock()

	def _clean_revision(self) -> str:
		validate_game_repository(self.root)
		status = repository_status(self.root)
		if status.conflicted:
			raise ValueError('The game checkout has unresolved Git conflicts.')
		if status.dirty or status.truncated_change_count:
			raise ValueError('The game checkout must be clean before preparing or applying changes.')
		return repository_revision(self.root)

	def _journal_root(self) -> Path:
		result = subprocess.run(['git', '-C', str(self.root), 'rev-parse', '--absolute-git-dir'], capture_output=True, text=True, check=True, timeout=15)
		return Path(result.stdout.strip()) / 'aphelion-content-tools'

	def _path(self, relative: str) -> Path:
		path = resolve_repo_path(self.root, Path(relative))
		if path.relative_to(self.root).as_posix() != relative or '.git' in Path(relative).parts:
			raise ValueError('Change paths must identify canonical repository files.')
		if path.exists() and not path.is_file():
			raise ValueError('Change path is not a file.')
		return path

	def recover(self) -> None:
		"""Recover only our interrupted writes, never overwrite a later independent edit."""
		with self._lock, repository_write_lock(self.root):
			journal = self._journal_root() / 'pending.json'
			if not journal.exists():
				return
			payload = json.loads(journal.read_bytes())
			if payload.get('schema_version') != 1 or payload.get('base_revision') != repository_revision(self.root):
				raise ValueError('Interrupted change recovery requires the original game revision.')
			stage_id = payload.get('stage_id', '')
			if stage_id and not re.fullmatch(r'[A-Za-z0-9_-]{16,64}', stage_id):
				raise ValueError('Invalid interrupted change journal identity.')
			receipt_path = self._journal_root() / 'receipts' / f'{stage_id}.json'
			committed = json.loads(receipt_path.read_bytes()) if stage_id and receipt_path.is_file() else None
			if committed and (committed.get('stage_id') != stage_id or committed.get('base_revision') != payload['base_revision'] or committed.get('sha256') != {item['path']: item['after_sha256'] for item in payload['files']}):
				raise ValueError('Interrupted change receipt does not match its journal.')
			restores: list[tuple[Path, bytes | None]] = []
			for item in payload['files']:
				path = self._path(item['path'])
				before = bytes.fromhex(item['before']) if item['before'] is not None else None
				current = path.read_bytes() if path.exists() else None
				current_hash = hashlib.sha256(current).hexdigest() if current is not None else None
				before_hash = hashlib.sha256(before).hexdigest() if before is not None else None
				if current_hash not in (before_hash, item['after_sha256']):
					raise ValueError('Interrupted change recovery found an independent edit; review the recovery journal.')
				restores.append((path, before))
			if committed:
				# The durable receipt is the transaction commit point. A crash while
				# removing the journal must not undo an already committed application.
				if any(hashlib.sha256(self._path(item['path']).read_bytes()).hexdigest() != item['after_sha256'] for item in payload['files']):
					raise ValueError('Committed change files no longer match their receipt.')
				journal.unlink()
				return
			# Separate journal writes from the game-write injection point used by callers/tests.
			from webapp.json_storage import atomic_write as restore_write
			for path, before in restores:
				if before is None:
					path.unlink(missing_ok=True)
				else:
					restore_write(path, before)
			journal.unlink()

	def prepare(self, changes: Mapping[str, tuple[bytes | None, bytes]], *, allowed_paths: frozenset[str]) -> PreparedGameChange:
		if not changes or not set(changes).issubset(allowed_paths):
			raise ValueError('The change set contains a path outside this tool\'s allowlist.')
		with self._lock, repository_write_lock(self.root):
			self.recover()
			revision = self._clean_revision()
			files: list[tuple[str, str | None, bytes]] = []
			preview: list[str] = []
			for relative, (expected, proposed) in changes.items():
				path = self._path(relative)
				if (path.read_bytes() if path.exists() else None) != expected:
					raise ValueError('A source file changed while preparing the change set; refresh and retry.')
				files.append((relative, hashlib.sha256(expected).hexdigest() if expected is not None else None, proposed))
				def text(data: bytes) -> str:
					try:
						return data.decode('utf-8-sig')
					except UnicodeDecodeError:
						return data.decode('latin-1')
				preview.extend(difflib.unified_diff(text(expected or b'').splitlines(keepends=True), text(proposed).splitlines(keepends=True), fromfile=f'a/{relative}' if expected is not None else '/dev/null', tofile=f'b/{relative}'))
			self._stages = {key: stage for key, stage in self._stages.items() if stage.expires > time.monotonic()}
			if len(self._stages) >= 128:
				raise ValueError('Too many pending change previews. Apply a preview or wait for it to expire.')
			public = PreparedGameChange(secrets.token_urlsafe(24), revision, ''.join(preview), tuple(changes))
			self._stages[public.stage_id] = _Stage(public, time.monotonic() + 900, tuple(files))
			return public

	def apply(self, stage_id: str) -> dict[str, object]:
		with self._lock, repository_write_lock(self.root):
			self.recover()
			stage = self._stages.get(stage_id)
			if stage is None or stage.expires <= time.monotonic():
				self._stages.pop(stage_id, None)
				raise ValueError('This change preview expired or was already applied. Prepare a new preview.')
			if self._clean_revision() != stage.public.base_revision:
				raise ValueError('The game revision changed after preparation. Prepare a new preview.')
			resolved: list[tuple[Path, bytes]] = []
			for relative, expected_hash, proposed in stage.files:
				path = self._path(relative)
				current_hash = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
				if current_hash != expected_hash:
					raise ValueError('A staged source file changed. Prepare a new preview.')
				resolved.append((path, proposed))
			from webapp.json_storage import atomic_write as journal_write
			journal = self._journal_root() / 'pending.json'
			journal_write(journal, canonical_json_bytes({'schema_version': 1, 'stage_id': stage_id, 'base_revision': stage.public.base_revision, 'files': [
				{'path': path.relative_to(self.root).as_posix(), 'before': path.read_bytes().hex() if path.exists() else None, 'after_sha256': hashlib.sha256(proposed).hexdigest()}
				for path, proposed in resolved
			]}))
			receipt = {'stage_id': stage_id, 'base_revision': stage.public.base_revision, 'paths': list(stage.public.paths),
				'sha256': {relative: hashlib.sha256(proposed).hexdigest() for relative, _, proposed in stage.files}}
			try:
				with rollback_files(path for path, _ in resolved):
					for path, proposed in resolved:
						atomic_write(path, proposed)
					for path, proposed in resolved:
						if path.read_bytes() != proposed:
							raise OSError('The applied game file failed verification.')
					journal_write(self._journal_root() / 'receipts' / f'{stage_id}.json', canonical_json_bytes(receipt))
			except Exception:
				self.recover()
				raise
			del self._stages[stage_id]
			journal.unlink()
			return receipt

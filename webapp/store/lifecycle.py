from __future__ import annotations

import errno
import hashlib
import json
import logging
import os
import shutil
import tempfile
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import BinaryIO, Concatenate, ParamSpec, TypeVar

from .metadata import (
	ACTIVE_PROJECTION_FILE,
	PREVIOUS_PROJECTION_FILE,
	PROJECTION_MARKER_FILE,
	PROJECTIONS_DIRECTORY,
	ActiveProjection,
	_atomic_write_json,
	_read_metadata_file,
	active_projection,
	projection_path,
	store_root,
)

_reads: ContextVar[dict[Path, ActiveProjection] | None] = ContextVar("projection_reads", default=None)
_logger = logging.getLogger(__name__)
_P = ParamSpec("_P")
_R = TypeVar("_R")
MAX_RETIREMENTS_PER_WRITE = 4


def lifecycle_lock(repo_root: Path):
	from tools.lore_editor.write_coordinator import repository_write_lock

	# A distinct lock identity reuses the cross-process coordinator without making
	# readers wait for the repository writer's potentially long copy/embedding work.
	return repository_write_lock(repo_root.resolve() / "webapp/store/projection-lifecycle")


def selected_projection(repo_root: Path) -> ActiveProjection:
	return (_reads.get() or {}).get(repo_root.resolve()) or active_projection(repo_root)


def _lease_directory(repo_root: Path) -> Path:
	key = os.path.normcase(str(repo_root.resolve()))
	name = hashlib.sha256(key.encode()).hexdigest()
	return Path(tempfile.gettempdir()) / "aphelion-content-tools-projection-leases" / name


def _try_lock(handle: BinaryIO) -> bool:
	handle.seek(0)
	try:
		if os.name == "nt":
			import msvcrt
			msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
		else:
			import fcntl
			fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
	except OSError as exc:
		if exc.errno in (errno.EACCES, errno.EAGAIN):
			return False
		raise
	return True


@dataclass
class ProjectionLease:
	projection: ActiveProjection
	handle: BinaryIO | None = None
	lease_path: Path | None = None

	def close(self) -> None:
		if self.handle is not None:
			self.handle.close()  # The OS also releases this lock on process death.
			self.handle = None
		if self.lease_path is not None:
			# A collector may have it open; it can remove the unlocked file later.
			with suppress(OSError):
				self.lease_path.unlink(missing_ok=True)
			self.lease_path = None


def _generation_at(repo_root: Path, path: Path) -> str | None:
	root = store_root(repo_root) / PROJECTIONS_DIRECTORY
	requested = path.absolute()
	resolved = path.resolve()
	if not requested.is_relative_to(root) and resolved.parent != root.resolve():
		return None
	# Do not lease or retire a directory alias, including Windows junctions.
	if root.resolve() != root or requested.parent != root or resolved != requested:
		raise ValueError("Projection path must not be a filesystem alias.")
	projection_path(repo_root, path.name)  # Validate the generation identifier.
	return path.name


def acquire_projection(repo_root: Path, *, store_dir: Path | None = None, include_owners: bool = True) -> ProjectionLease:
	with lifecycle_lock(repo_root):
		if store_dir is None:
			projection = selected_projection(repo_root)
		else:
			projection = ActiveProjection(None, store_dir.absolute())
		generation = _generation_at(repo_root, projection.path)
		if generation is None:
			return ProjectionLease(projection)
		if not projection.path.is_dir():
			raise FileNotFoundError(f"Projection generation is no longer available: {generation}")
		if store_dir is not None:
			try:
				metadata = _read_metadata_file(projection.path / PROJECTION_MARKER_FILE)
			except (KeyError, OSError, TypeError, ValueError):
				metadata = None
			if metadata is not None and metadata.generation_id == generation:
				projection = ActiveProjection(metadata, projection.path)
		directory = _lease_directory(repo_root)
		directory.mkdir(parents=True, exist_ok=True)
		path = directory / f"{generation}_{uuid.uuid4().hex}.lease"
		handle = path.open("x+b")
		try:
			owners = projection.metadata.table_owners if include_owners and projection.metadata is not None else None
			generations = sorted({generation, *(owners or {}).values()})
			handle.write(b"\0" + json.dumps(generations).encode("utf-8"))
			handle.flush()
			if not _try_lock(handle):
				raise OSError("Cannot lock a new projection reader lease.")
		except BaseException:
			handle.close()
			path.unlink(missing_ok=True)
			raise
		return ProjectionLease(projection, handle, path)


@contextmanager
def read_projection(repo_root: Path, *, store_dir: Path | None = None) -> Iterator[ActiveProjection]:
	root = repo_root.resolve()
	current = (_reads.get() or {}).get(root)
	if current is not None and (store_dir is None or store_dir.resolve() == current.path):
		yield current
		return
	lease = acquire_projection(root, store_dir=store_dir)
	token = _reads.set({**(_reads.get() or {}), root: lease.projection})
	try:
		yield lease.projection
	finally:
		_reads.reset(token)
		lease.close()


def with_projection_read(function: Callable[Concatenate[Path, _P], _R]) -> Callable[Concatenate[Path, _P], _R]:
	"""Keep synchronous composite reads and their nested loaders on one generation."""
	@wraps(function)
	def pinned(repo_root: Path, *args: _P.args, **kwargs: _P.kwargs) -> _R:
		with read_projection(repo_root):
			return function(repo_root, *args, **kwargs)
	return pinned


def _live_generations(repo_root: Path) -> set[str]:
	live: set[str] = set()
	for path in _lease_directory(repo_root).glob("*.lease"):
		generation, separator, _nonce = path.stem.partition("_")
		if not separator:
			raise ValueError("Unrecognized projection reader lease.")
		projection_path(repo_root, generation)
		try:
			with path.open("r+b") as handle:
				if not _try_lock(handle):
					live.add(generation)
					handle.seek(1)
					payload = handle.read(16385)
					if payload:
						owners = json.loads(payload)
						if len(payload) > 16384 or not isinstance(owners, list) or any(not isinstance(owner, str) for owner in owners):
							raise ValueError("Invalid projection reader owner list.")
						for owner in owners:
							projection_path(repo_root, owner)
						live.update(owners)
					continue
			path.unlink(missing_ok=True)
		except FileNotFoundError:
			pass
	return live


def _retire_projections(repo_root: Path) -> tuple[str, ...]:
	from tools.lore_editor.write_coordinator import repository_write_lock

	from . import db

	retired: list[str] = []
	root = store_root(repo_root) / PROJECTIONS_DIRECTORY
	quarantine = root / ".retired"
	with repository_write_lock(repo_root):
		with lifecycle_lock(repo_root):
			if not root.is_dir():
				return ()
			if root.resolve() != root or quarantine.resolve() != quarantine:
				raise ValueError("Projection retirement path must not be a filesystem alias.")
			if active_projection(repo_root).metadata is None:
				return ()  # Leave recovery material intact if both pointers are unusable.
			keep: set[str] = set()
			for filename in (ACTIVE_PROJECTION_FILE, PREVIOUS_PROJECTION_FILE):
				try:
					metadata = _read_metadata_file(store_root(repo_root) / filename)
					projection_path(repo_root, metadata.generation_id)
					keep.add(metadata.generation_id)
					keep.update((metadata.table_owners or {}).values())
				except (KeyError, OSError, TypeError, ValueError):
					continue
			candidates = []
			for path in root.iterdir():
				if path.name.startswith(".") or path.name in keep:
					continue
				try:
					if _generation_at(repo_root, path) is None or not path.is_dir():
						continue
					metadata = _read_metadata_file(path / PROJECTION_MARKER_FILE)
				except (KeyError, OSError, TypeError, ValueError):
					continue  # Incomplete builds and unknown files are not garbage.
				if metadata.generation_id == path.name:
					db.discard_connection(path)
					candidates.append(path)
			keep.update(_live_generations(repo_root))
			for path in candidates:
				if path.name in keep:
					continue
				quarantine.mkdir(exist_ok=True)
				try:
					path.rename(quarantine / path.name)
				except OSError:
					continue  # Windows may still have a handle from another cache.
				retired.append(path.name)
				if len(retired) >= MAX_RETIREMENTS_PER_WRITE:
					break
		# Readers may select the active projection while potentially slow deletion runs.
		if quarantine.is_dir():
			cursor_path = quarantine / "retirement-cursor.json"
			try:
				last_attempted = json.loads(cursor_path.read_text(encoding="utf-8"))["last_attempted"]
				if not isinstance(last_attempted, str):
					last_attempted = ""
			except (KeyError, OSError, TypeError, ValueError):
				last_attempted = ""
			pending = sorted((path for path in quarantine.iterdir() if path.is_dir()), key=lambda path: path.name)
			# Resume after the last attempt, not the last success. Busy handles cannot
			# keep every later generation behind the same failed deletion forever.
			pending = [path for path in pending if path.name > last_attempted] + [path for path in pending if path.name <= last_attempted]
			for path in pending[:MAX_RETIREMENTS_PER_WRITE]:
				last_attempted = path.name
				if path.resolve() != path or path.parent != quarantine:
					continue
				try:
					metadata = _read_metadata_file(path / PROJECTION_MARKER_FILE)
					if metadata.generation_id != path.name:
						continue
					projection_path(repo_root, metadata.generation_id)
				except (KeyError, OSError, TypeError, ValueError):
					continue
				try:
					shutil.rmtree(path)
				except OSError:
					_logger.warning("Deferred removal of retired projection %s", path.name)
			_atomic_write_json(cursor_path, {"last_attempted": last_attempted})
	return tuple(retired)


def retire_projections(repo_root: Path) -> tuple[str, ...]:
	"""Best-effort maintenance; failure cannot roll back an already published write."""
	try:
		return _retire_projections(repo_root)
	except (OSError, ValueError):
		_logger.warning("Projection retirement deferred", exc_info=True)
		return ()

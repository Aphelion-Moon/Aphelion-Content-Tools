from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Literal

from .embeddings import EMBEDDING_MODEL_NAME

PROJECTION_SCHEMA_VERSION = 2
STORE_ROOT_RELATIVE_PATH = Path("webapp/store")
LEGACY_DATA_DIRECTORY = "data"
PROJECTIONS_DIRECTORY = "projections"
ACTIVE_PROJECTION_FILE = "active-projection.json"
PREVIOUS_PROJECTION_FILE = "previous-projection.json"
PROJECTION_MARKER_FILE = "projection.json"
BACKUP_MARKER_FILE = "backup.json"

ProjectionState = Literal["current", "stale"]


@dataclass(frozen=True)
class ProjectionRevision:
	schema_version: int
	content_revision: str
	embedding_model_id: str
	state: ProjectionState


@dataclass(frozen=True)
class ProjectionMetadata:
	generation_id: str
	revision: ProjectionRevision
	table_owners: dict[str, str] | None = None


@dataclass(frozen=True)
class ProjectionStatus:
	active: ProjectionMetadata | None
	current: bool
	reason: str | None
	path: Path


@dataclass(frozen=True)
class ActiveProjection:
	metadata: ProjectionMetadata | None
	path: Path


def store_root(repo_root: Path) -> Path:
	return repo_root.resolve() / STORE_ROOT_RELATIVE_PATH


def projection_path(repo_root: Path, generation_id: str) -> Path:
	if not generation_id or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in generation_id):
		raise ValueError("Invalid projection generation id.")
	path = store_root(repo_root) / PROJECTIONS_DIRECTORY / generation_id
	if path.resolve() != path:
		raise ValueError("Projection path must not be a filesystem alias.")
	return path


def new_projection_metadata(content_revision: str, *, state: ProjectionState = "current") -> ProjectionMetadata:
	return ProjectionMetadata(
		generation_id=f"{content_revision[:12]}-{uuid.uuid4().hex[:12]}",
		revision=ProjectionRevision(
			schema_version=PROJECTION_SCHEMA_VERSION,
			content_revision=content_revision,
			embedding_model_id=EMBEDDING_MODEL_NAME,
			state=state,
		),
	)


def _payload(metadata: ProjectionMetadata) -> dict[str, object]:
	return asdict(metadata)


def _parse_metadata(payload: object) -> ProjectionMetadata:
	if not isinstance(payload, dict) or not isinstance(payload.get("generation_id"), str):
		raise ValueError("Projection metadata requires a generation_id.")
	revision = payload.get("revision")
	if not isinstance(revision, dict):
		raise ValueError("Projection metadata requires a revision object.")
	state = revision.get("state")
	if state not in ("current", "stale"):
		raise ValueError("Projection metadata has an invalid state.")
	owners = payload.get("table_owners")
	if owners is not None and (
		not isinstance(owners, dict) or len(owners) > 128
		or any(not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", name)
			or not isinstance(owner, str) or not re.fullmatch(r"[a-z0-9-]+", owner)
			for name, owner in owners.items())
	):
		raise ValueError("Projection metadata has invalid table owners.")
	return ProjectionMetadata(
		generation_id=payload["generation_id"],
		table_owners=owners,
		revision=ProjectionRevision(
			schema_version=int(revision["schema_version"]),
			content_revision=str(revision["content_revision"]),
			embedding_model_id=str(revision["embedding_model_id"]),
			state=state,
		),
	)


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
	file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
	temporary_path = Path(temporary_name)
	try:
		with os.fdopen(file_descriptor, "wb") as handle:
			handle.write(data)
			handle.flush()
			os.fsync(handle.fileno())
		os.replace(temporary_path, path)
	finally:
		temporary_path.unlink(missing_ok=True)


def _read_metadata_file(path: Path) -> ProjectionMetadata:
	payload = json.loads(path.read_text(encoding="utf-8"))
	return _parse_metadata(payload)


def write_projection_marker(repo_root: Path, metadata: ProjectionMetadata) -> Path:
	path = projection_path(repo_root, metadata.generation_id)
	_atomic_write_json(path / PROJECTION_MARKER_FILE, _payload(metadata))
	return path


def _is_valid_projection(repo_root: Path, metadata: ProjectionMetadata) -> bool:
	path = projection_path(repo_root, metadata.generation_id)
	try:
		if _read_metadata_file(path / PROJECTION_MARKER_FILE) != metadata:
			return False
		projection_table_paths(repo_root, ActiveProjection(metadata, path))
		return True
	except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
		return False


def table_directory(repo_root: Path, name: str, projection: ActiveProjection) -> Path | None:
	if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
		raise ValueError("Invalid projection table name.")
	metadata = projection.metadata
	owners = metadata.table_owners if metadata is not None else None
	if metadata is not None and owners is not None:
		owner = owners.get(name)
		if owner is None:
			return None
		owner_path = projection_path(repo_root, owner)
		if owner != metadata.generation_id:
			owner_metadata = _read_metadata_file(owner_path / PROJECTION_MARKER_FILE)
			if owner_metadata.generation_id != owner or owner_metadata.table_owners is None or owner_metadata.table_owners.get(name) != owner:
				raise ValueError("Projection tables must reference their direct physical owner.")
		path = owner_path / f"{name}.lance"
	else:
		path = projection.path / f"{name}.lance"
	if path.resolve() != path:
		raise ValueError("Projection table must not be a filesystem alias.")
	if not path.is_dir():
		if owners is not None:
			raise ValueError(f"Projection table '{name}' is missing from its declared owner.")
		return None
	return path


def projection_table_paths(repo_root: Path, projection: ActiveProjection) -> dict[str, Path]:
	metadata = projection.metadata
	names = metadata.table_owners if metadata is not None and metadata.table_owners is not None else {
		path.stem: "" for path in projection.path.glob("*.lance")
	}
	paths = {name: table_directory(repo_root, name, projection) for name in names}
	return {name: path for name, path in paths.items() if path is not None}


def active_projection(repo_root: Path) -> ActiveProjection:
	root = store_root(repo_root)
	for filename in (ACTIVE_PROJECTION_FILE, PREVIOUS_PROJECTION_FILE):
		try:
			metadata = _read_metadata_file(root / filename)
			valid = _is_valid_projection(repo_root, metadata)
		except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
			continue
		if valid:
			return ActiveProjection(metadata, projection_path(repo_root, metadata.generation_id))
	return ActiveProjection(None, root / LEGACY_DATA_DIRECTORY)


def active_projection_metadata(repo_root: Path) -> ProjectionMetadata | None:
	return active_projection(repo_root).metadata


def active_projection_path(repo_root: Path) -> Path:
	return active_projection(repo_root).path


def activate_projection(repo_root: Path, metadata: ProjectionMetadata) -> None:
	from .lifecycle import lifecycle_lock

	with lifecycle_lock(repo_root):
		if not _is_valid_projection(repo_root, metadata):
			raise ValueError("Cannot activate a projection without matching generation metadata.")
		root = store_root(repo_root)
		current = active_projection(repo_root).metadata
		if current is not None and current.generation_id != metadata.generation_id:
			_atomic_write_json(root / PREVIOUS_PROJECTION_FILE, _payload(current))
		_atomic_write_json(root / ACTIVE_PROJECTION_FILE, _payload(metadata))


def projection_status(
	repo_root: Path,
	content_revision: str,
	*,
	active: ActiveProjection | None = None,
) -> ProjectionStatus:
	pinned = active if active is not None else active_projection(repo_root)
	metadata = pinned.metadata
	if metadata is None:
		return ProjectionStatus(active=None, current=False, reason="No versioned projection is active.", path=pinned.path)
	revision = metadata.revision
	if revision.schema_version != PROJECTION_SCHEMA_VERSION:
		return ProjectionStatus(active=metadata, current=False, reason="Projection schema version is stale.", path=pinned.path)
	if revision.embedding_model_id != EMBEDDING_MODEL_NAME:
		return ProjectionStatus(active=metadata, current=False, reason="Projection embedding model is stale.", path=pinned.path)
	if revision.state != "current":
		return ProjectionStatus(active=metadata, current=False, reason="Projection was restored from a recovery snapshot.", path=pinned.path)
	if revision.content_revision != content_revision:
		return ProjectionStatus(active=metadata, current=False, reason="Canonical content changed after projection.", path=pinned.path)
	return ProjectionStatus(active=metadata, current=True, reason=None, path=pinned.path)


def backup_projection(repo_root: Path, destination: Path, *, label: str) -> Path:
	from tools.lore_editor.write_coordinator import repository_write_lock

	with repository_write_lock(repo_root):
		active = active_projection(repo_root)
		if active.metadata is None:
			raise ValueError("No versioned projection is available to back up.")
		destination = destination.resolve()
		if destination.exists():
			raise ValueError(f"Backup destination already exists: {destination}")
		if destination.is_relative_to(store_root(repo_root) / PROJECTIONS_DIRECTORY):
			raise ValueError("Backup destination must be outside projection generations.")
		tables = projection_table_paths(repo_root, active)
		materialized = replace(active.metadata, table_owners={name: active.metadata.generation_id for name in tables})
		destination.mkdir(parents=True)
		try:
			for name, source in tables.items():
				shutil.copytree(source, destination / f"{name}.lance")
			_atomic_write_json(destination / PROJECTION_MARKER_FILE, _payload(materialized))
			_atomic_write_json(destination / BACKUP_MARKER_FILE, {"label": label, "projection": _payload(materialized)})
		except BaseException:
			if destination.resolve() == destination:
				shutil.rmtree(destination, ignore_errors=True)
			raise
		return destination


def restore_projection(repo_root: Path, backup_path: Path) -> ProjectionMetadata:
	from tools.lore_editor.write_coordinator import repository_write_lock

	from .lifecycle import retire_projections

	with repository_write_lock(repo_root):
		restored = _restore_projection_locked(repo_root, backup_path)
		retire_projections(repo_root)
		return restored


def _restore_projection_locked(repo_root: Path, backup_path: Path) -> ProjectionMetadata:
	backup_path = backup_path.resolve()
	try:
		backup_payload = json.loads((backup_path / BACKUP_MARKER_FILE).read_text(encoding="utf-8"))
		original = _parse_metadata(backup_payload["projection"])
	except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
		raise ValueError(f"Invalid projection backup: {backup_path}") from exc
	marker = _read_metadata_file(backup_path / PROJECTION_MARKER_FILE)
	if marker != original:
		raise ValueError("Projection backup marker does not match its label metadata.")
	if original.table_owners is not None and any(owner != original.generation_id for owner in original.table_owners.values()):
		raise ValueError("Projection backup must contain all of its tables.")
	names = original.table_owners if original.table_owners is not None else {path.stem: "" for path in backup_path.glob("*.lance")}
	for name in names:
		if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
			raise ValueError("Projection backup has an invalid table name.")
		path = backup_path / f"{name}.lance"
		if path.resolve() != path or not path.is_dir():
			raise ValueError(f"Projection backup table '{name}' is missing or aliased.")
	restored = replace(
		new_projection_metadata(original.revision.content_revision, state="stale"),
		revision=replace(original.revision, state="stale"),
	)
	restored = replace(restored, table_owners={name: restored.generation_id for name in names})
	destination = projection_path(repo_root, restored.generation_id)
	destination.mkdir(parents=True)
	try:
		for name in names:
			shutil.copytree(backup_path / f"{name}.lance", destination / f"{name}.lance")
		write_projection_marker(repo_root, restored)
		activate_projection(repo_root, restored)
	except BaseException:
		if active_projection(repo_root).metadata != restored and destination.resolve() == destination:
			shutil.rmtree(destination, ignore_errors=True)
		raise
	return restored

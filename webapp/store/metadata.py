from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Literal

from .embeddings import EMBEDDING_MODEL_NAME

PROJECTION_SCHEMA_VERSION = 1
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


@dataclass(frozen=True)
class ProjectionStatus:
	active: ProjectionMetadata | None
	current: bool
	reason: str | None
	path: Path


def store_root(repo_root: Path) -> Path:
	return repo_root.resolve() / STORE_ROOT_RELATIVE_PATH


def projection_path(repo_root: Path, generation_id: str) -> Path:
	if not generation_id or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in generation_id):
		raise ValueError("Invalid projection generation id.")
	return store_root(repo_root) / PROJECTIONS_DIRECTORY / generation_id


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
	return ProjectionMetadata(
		generation_id=payload["generation_id"],
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
		return _read_metadata_file(path / PROJECTION_MARKER_FILE) == metadata
	except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
		return False


def active_projection_metadata(repo_root: Path) -> ProjectionMetadata | None:
	root = store_root(repo_root)
	for filename in (ACTIVE_PROJECTION_FILE, PREVIOUS_PROJECTION_FILE):
		try:
			metadata = _read_metadata_file(root / filename)
		except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
			continue
		if _is_valid_projection(repo_root, metadata):
			return metadata
	return None


def active_projection_path(repo_root: Path) -> Path:
	metadata = active_projection_metadata(repo_root)
	if metadata is None:
		return store_root(repo_root) / LEGACY_DATA_DIRECTORY
	return projection_path(repo_root, metadata.generation_id)


def activate_projection(repo_root: Path, metadata: ProjectionMetadata) -> None:
	if not _is_valid_projection(repo_root, metadata):
		raise ValueError("Cannot activate a projection without matching generation metadata.")
	root = store_root(repo_root)
	current = active_projection_metadata(repo_root)
	if current is not None and current.generation_id != metadata.generation_id:
		_atomic_write_json(root / PREVIOUS_PROJECTION_FILE, _payload(current))
	_atomic_write_json(root / ACTIVE_PROJECTION_FILE, _payload(metadata))


def projection_status(repo_root: Path, content_revision: str) -> ProjectionStatus:
	active = active_projection_metadata(repo_root)
	path = active_projection_path(repo_root)
	if active is None:
		return ProjectionStatus(active=None, current=False, reason="No versioned projection is active.", path=path)
	revision = active.revision
	if revision.schema_version != PROJECTION_SCHEMA_VERSION:
		return ProjectionStatus(active=active, current=False, reason="Projection schema version is stale.", path=path)
	if revision.embedding_model_id != EMBEDDING_MODEL_NAME:
		return ProjectionStatus(active=active, current=False, reason="Projection embedding model is stale.", path=path)
	if revision.state != "current":
		return ProjectionStatus(active=active, current=False, reason="Projection was restored from a recovery snapshot.", path=path)
	if revision.content_revision != content_revision:
		return ProjectionStatus(active=active, current=False, reason="Canonical content changed after projection.", path=path)
	return ProjectionStatus(active=active, current=True, reason=None, path=path)


def backup_projection(repo_root: Path, destination: Path, *, label: str) -> Path:
	metadata = active_projection_metadata(repo_root)
	if metadata is None:
		raise ValueError("No versioned projection is available to back up.")
	destination = destination.resolve()
	if destination.exists():
		raise ValueError(f"Backup destination already exists: {destination}")
	shutil.copytree(active_projection_path(repo_root), destination)
	_atomic_write_json(destination / BACKUP_MARKER_FILE, {"label": label, "projection": _payload(metadata)})
	return destination


def restore_projection(repo_root: Path, backup_path: Path) -> ProjectionMetadata:
	backup_path = backup_path.resolve()
	try:
		backup_payload = json.loads((backup_path / BACKUP_MARKER_FILE).read_text(encoding="utf-8"))
		original = _parse_metadata(backup_payload["projection"])
	except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
		raise ValueError(f"Invalid projection backup: {backup_path}") from exc
	marker = _read_metadata_file(backup_path / PROJECTION_MARKER_FILE)
	if marker != original:
		raise ValueError("Projection backup marker does not match its label metadata.")
	restored = replace(
		new_projection_metadata(original.revision.content_revision, state="stale"),
		revision=replace(original.revision, state="stale"),
	)
	destination = projection_path(repo_root, restored.generation_id)
	shutil.copytree(backup_path, destination, ignore=shutil.ignore_patterns(BACKUP_MARKER_FILE, PROJECTION_MARKER_FILE))
	write_projection_marker(repo_root, restored)
	activate_projection(repo_root, restored)
	return restored

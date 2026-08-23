from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from webapp.store import db
from webapp.store.metadata import (
	ProjectionRevision,
	activate_projection,
	new_projection_metadata,
	projection_path,
	projection_status,
	write_projection_marker,
)
from webapp.store.schema import decode, encode, table

from .records import CONTENT_ROOT, RECORD_DIRECTORIES, RecordKind, atomic_write_record, record_path
from .source import make_lore_entry
from .taxonomy import _group_from_raw, _review_from_raw
from .validation import TYPE_PATH_PATTERN, validate_entry_id, validate_entry_shape
from .write_coordinator import repository_write_lock

RECORD_KIND_DIRECTORIES: tuple[tuple[RecordKind, str], ...] = (
	("override", "overrides"),
	("group", "groups"),
	("review", "reviews"),
	("assignment", "assignments"),
)


@dataclass(frozen=True)
class CanonicalSnapshot:
	overrides: tuple[dict[str, object], ...]
	groups: tuple[dict[str, object], ...]
	reviews: tuple[dict[str, object], ...]
	assignments: tuple[dict[str, object], ...]
	content_revision: str
	active_kinds: frozenset[RecordKind]


@dataclass(frozen=True)
class ReconcileResult:
	counts: dict[str, int]
	content_revision: str
	projection_revision: ProjectionRevision


def _read_json_object(path: Path) -> dict[str, object]:
	try:
		payload = json.loads(path.read_text(encoding="utf-8"))
	except (OSError, json.JSONDecodeError) as exc:
		raise ValueError(f"Could not read canonical record {path}: {exc}") from exc
	if not isinstance(payload, dict):
		raise ValueError(f"Canonical record {path} must contain a JSON object.")
	return payload


def _record_id(kind: RecordKind, payload: dict[str, object]) -> str:
	field = "id" if kind in ("override", "group") else "type_path"
	value = payload.get(field)
	if not isinstance(value, str):
		raise ValueError(f"Canonical {kind} record requires a string {field}.")
	return value


def _validate_record(repo_root: Path, kind: RecordKind, path: Path, payload: dict[str, object]) -> None:
	record_id = _record_id(kind, payload)
	if path.resolve() != record_path(repo_root, kind, record_id):
		raise ValueError(f"Canonical {kind} record path does not match its id: {path}")
	if kind == "override":
		validate_entry_id(record_id)
		issues = []
		validate_entry_shape(make_lore_entry(path.relative_to(repo_root), payload), issues)
		if issues:
			raise ValueError("\n".join(issue.message for issue in issues))
	elif kind == "group":
		_group_from_raw(payload)
	elif kind == "review":
		_review_from_raw(record_id, payload)
	else:
		if not TYPE_PATH_PATTERN.fullmatch(record_id):
			raise ValueError(f"Invalid assignment type path '{record_id}'.")
		group_ids = payload.get("group_ids")
		if not isinstance(group_ids, list) or any(not isinstance(group_id, str) for group_id in group_ids):
			raise ValueError("Canonical assignment group_ids must be an array of strings.")


def scan_canonical_records(repo_root: Path) -> CanonicalSnapshot:
	resolved_root = repo_root.resolve()
	root = resolved_root / CONTENT_ROOT
	records: dict[RecordKind, list[dict[str, object]]] = {
		kind: [] for kind, _directory in RECORD_KIND_DIRECTORIES
	}
	active_kinds: set[RecordKind] = set()
	revision = hashlib.sha256()
	for kind, directory in RECORD_KIND_DIRECTORIES:
		directory_path = root / directory
		if not directory_path.is_dir():
			continue
		active_kinds.add(kind)
		for path in sorted(directory_path.rglob("*.json")):
			payload = _read_json_object(path)
			_validate_record(resolved_root, kind, path, payload)
			records[kind].append(payload)
			revision.update(path.relative_to(resolved_root).as_posix().encode())
			revision.update(b"\0")
			revision.update(path.read_bytes())
			revision.update(b"\0")

	group_ids = {str(group["id"]) for group in records["group"]}
	for assignment in records["assignment"]:
		assigned_group_ids = assignment["group_ids"]
		if not isinstance(assigned_group_ids, list):
			raise ValueError("Canonical assignment group_ids must be an array of strings.")
		unknown = {str(group_id) for group_id in assigned_group_ids} - group_ids
		if unknown:
			raise ValueError(f"Canonical assignment references unknown groups: {', '.join(sorted(unknown))}.")

	return CanonicalSnapshot(
		overrides=tuple(records["override"]),
		groups=tuple(records["group"]),
		reviews=tuple(records["review"]),
		assignments=tuple(records["assignment"]),
		content_revision=revision.hexdigest(),
		active_kinds=frozenset(active_kinds),
	)


def materialize_legacy_records(repo_root: Path, kind: RecordKind) -> tuple[Path, ...]:
	resolved_root = repo_root.resolve()
	directory = resolved_root / CONTENT_ROOT / RECORD_DIRECTORIES[kind]
	if directory.is_dir():
		return ()
	table_name = {
		"override": "overrides",
		"group": "groups",
		"review": "reviews",
		"assignment": "assignments",
	}[kind]
	written: list[Path] = []
	for row in db.all_rows(table(resolved_root, table_name)):
		payload = decode(row)
		record_id = _record_id(kind, payload)
		path = record_path(resolved_root, kind, record_id)
		atomic_write_record(path, payload)
		written.append(path)
	return tuple(written)


def _override_row(payload: dict[str, object]) -> dict[str, object]:
	entry_id = str(payload["id"])
	return {
		"id": entry_id,
		"type_path": str(payload["type_path"]),
		"group": entry_id.partition(".")[0],
		"raw_json": encode(payload),
		"text": " ".join(
			str(payload.get(field) or "")
			for field in ("id", "type_path", "name", "description")
		).strip(),
	}


def _group_row(payload: dict[str, object]) -> dict[str, object]:
	keywords = payload.get("keywords", [])
	if not isinstance(keywords, list):
		raise ValueError("Canonical group keywords must be an array of strings.")
	return {
		"id": str(payload["id"]),
		"raw_json": encode(payload),
		"text": f"{payload['label']} {' '.join(str(keyword) for keyword in keywords)}".strip(),
	}


def _review_row(payload: dict[str, object]) -> dict[str, object]:
	type_path = str(payload["type_path"])
	return {
		"id": type_path,
		"type_path": type_path,
		"raw_json": encode(payload),
		"text": f"{type_path} {payload.get('notes', '')}".strip(),
	}


def _assignment_row(payload: dict[str, object]) -> dict[str, object]:
	type_path = str(payload["type_path"])
	return {
		"id": type_path,
		"type_path": type_path,
		"raw_json": encode(payload),
		"text": type_path,
	}


def reconcile_projection(repo_root: Path, *, rebuild: bool = False, on_progress=None) -> ReconcileResult:
	resolved_root = repo_root.resolve()
	with repository_write_lock(resolved_root):
		snapshot = scan_canonical_records(resolved_root)
		projected_rows = {
			"overrides": [_override_row(payload) for payload in snapshot.overrides],
			"groups": [_group_row(payload) for payload in snapshot.groups],
			"reviews": [_review_row(payload) for payload in snapshot.reviews],
			"assignments": [_assignment_row(payload) for payload in snapshot.assignments],
		}
		table_kinds: dict[str, RecordKind] = {
			"overrides": "override",
			"groups": "group",
			"reviews": "review",
			"assignments": "assignment",
		}
		active_rows = {
			name: rows
			for name, rows in projected_rows.items()
			if table_kinds[name] in snapshot.active_kinds
		}
		status = projection_status(resolved_root, snapshot.content_revision)
		if status.current and not rebuild and status.active is not None:
			return ReconcileResult(
				counts={name: len(rows) for name, rows in active_rows.items()},
				content_revision=snapshot.content_revision,
				projection_revision=status.active.revision,
			)

		metadata = new_projection_metadata(snapshot.content_revision)
		destination = projection_path(resolved_root, metadata.generation_id)
		source = db.store_path(resolved_root)
		if source.is_dir():
			shutil.copytree(source, destination)
		else:
			destination.mkdir(parents=True, exist_ok=False)
		try:
			for index, (name, rows) in enumerate(active_rows.items(), start=1):
				db.sync_snapshot(table(resolved_root, name, store_dir=destination), "id", rows)
				if on_progress is not None:
					on_progress(name, index, len(active_rows))
			write_projection_marker(resolved_root, metadata)
			activate_projection(resolved_root, metadata)
		except Exception:
			db.discard_connection(destination)
			shutil.rmtree(destination, ignore_errors=True)
			raise
		return ReconcileResult(
			counts={name: len(rows) for name, rows in active_rows.items()},
			content_revision=snapshot.content_revision,
			projection_revision=metadata.revision,
		)

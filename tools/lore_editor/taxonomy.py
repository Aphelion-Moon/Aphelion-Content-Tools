from __future__ import annotations

import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from webapp.store import db
from webapp.store.lifecycle import read_projection
from webapp.store.schema import decode, table

from .model import (
	DEFAULT_KEYWORD_SCOPE,
	KEYWORD_SCOPE_FIELDS,
	CatalogTarget,
	GroupConfig,
	GroupRecord,
	ReviewRecord,
	thaw_json,
)
from .records import CONTENT_ROOT, atomic_write_record, canonical_record_hash, read_record, record_path
from .write_coordinator import RecordConflict, repository_write_lock

GROUP_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REVIEW_STATUSES = frozenset(("reviewed", "needs-attention"))


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
	if value is None:
		return ()
	if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
		raise ValueError(f"{field_name} must be an array of non-empty strings.")
	return tuple(item.strip() for item in value)


def _validate_group_id(group_id: str) -> None:
	if not GROUP_ID_PATTERN.fullmatch(group_id):
		raise ValueError(f"Invalid group id '{group_id}'. Use lowercase letters, numbers, and hyphens.")


def _group_from_raw(raw_group: object) -> GroupRecord:
	if not isinstance(raw_group, dict):
		raise ValueError("Each group must be a JSON object.")
	group_id = raw_group.get("id")
	label = raw_group.get("label")
	color = raw_group.get("color")
	if not isinstance(group_id, str):
		raise ValueError("Each group must contain a string id.")
	_validate_group_id(group_id)
	if not isinstance(label, str) or not label.strip():
		raise ValueError(f"Group '{group_id}' must contain a non-empty label.")
	if not isinstance(color, str) or not color.strip():
		raise ValueError(f"Group '{group_id}' must contain a non-empty color.")
	type_path_prefixes = _string_tuple(raw_group.get("type_path_prefixes"), f"Group '{group_id}' type_path_prefixes")
	if any(not prefix.startswith("/") for prefix in type_path_prefixes):
		raise ValueError(f"Group '{group_id}' type_path_prefixes must be absolute type paths.")
	raw_keyword_scope = raw_group.get("keyword_scope")
	if raw_keyword_scope is None:
		keyword_scope = DEFAULT_KEYWORD_SCOPE
	else:
		keyword_scope = _string_tuple(raw_keyword_scope, f"Group '{group_id}' keyword_scope")
		unknown_fields = set(keyword_scope) - set(KEYWORD_SCOPE_FIELDS)
		if unknown_fields:
			raise ValueError(f"Group '{group_id}' keyword_scope has unknown field(s): {', '.join(sorted(unknown_fields))}.")
	return GroupRecord(
		id=group_id,
		label=label.strip(),
		color=color.strip(),
		keywords=_string_tuple(raw_group.get("keywords"), f"Group '{group_id}' keywords"),
		type_path_prefixes=type_path_prefixes,
		keyword_scope=keyword_scope,
	)


def _group_payload(group: GroupRecord) -> dict[str, object]:
	return {
		"id": group.id,
		"label": group.label,
		"color": group.color,
		"keywords": list(group.keywords),
		"type_path_prefixes": list(group.type_path_prefixes),
		"keyword_scope": list(group.keyword_scope),
	}


def load_groups(repo_root: Path, *, store_dir: Path | None = None) -> GroupConfig:
	with read_projection(repo_root, store_dir=store_dir) as pinned:
		return _load_groups(repo_root, pinned.path)


def _load_groups(repo_root: Path, pinned_store: Path) -> GroupConfig:
	resolved_root = repo_root.resolve()
	group_directory = resolved_root / CONTENT_ROOT / "groups"
	if group_directory.is_dir():
		group_payloads = [read_record(path) for path in sorted(group_directory.rglob("*.json"))]
	else:
		group_payloads = [decode(row) for row in db.all_rows(table(resolved_root, "groups", store_dir=pinned_store))]
	groups = tuple(sorted((_group_from_raw(payload) for payload in group_payloads), key=lambda group: group.id))
	assignment_directory = resolved_root / CONTENT_ROOT / "assignments"
	if assignment_directory.is_dir():
		assignment_payloads = [read_record(path) for path in sorted(assignment_directory.rglob("*.json"))]
	else:
		assignment_payloads = [decode(row) for row in db.all_rows(table(resolved_root, "assignments", store_dir=pinned_store))]
	assignments: dict[str, tuple[str, ...]] = {}
	group_ids = {group.id for group in groups}
	for record in assignment_payloads:
		type_path = record.get("type_path")
		if not isinstance(type_path, str):
			raise ValueError("Assignment record must contain a type_path.")
		assigned_group_ids = _string_tuple(record.get("group_ids"), f"Assignment for '{type_path}'")
		if any(group_id not in group_ids for group_id in assigned_group_ids):
			raise ValueError(f"Assignment for '{type_path}' references an unknown group.")
		assignments[type_path] = assigned_group_ids
	return GroupConfig(groups=groups, assignments=assignments)


def _review_from_raw(type_path: str, raw_record: object) -> ReviewRecord:
	if not isinstance(raw_record, dict):
		raise ValueError(f"Review for '{type_path}' must be a JSON object.")
	status = raw_record.get("status")
	reviewed_by = raw_record.get("reviewed_by")
	reviewed_at = raw_record.get("reviewed_at")
	notes = raw_record.get("notes", "")
	if status not in REVIEW_STATUSES:
		raise ValueError(f"Review for '{type_path}' must have status 'reviewed' or 'needs-attention'.")
	if not isinstance(reviewed_by, str) or not reviewed_by.strip():
		raise ValueError(f"Review for '{type_path}' requires reviewed_by.")
	if not isinstance(reviewed_at, str):
		raise ValueError(f"Review for '{type_path}' requires reviewed_at.")
	try:
		datetime.fromisoformat(reviewed_at)
	except ValueError as exc:
		raise ValueError(f"Review for '{type_path}' has an invalid reviewed_at timestamp.") from exc
	if not isinstance(notes, str):
		raise ValueError(f"Review for '{type_path}' notes must be a string.")
	return ReviewRecord(status=status, reviewed_by=reviewed_by.strip(), reviewed_at=reviewed_at, notes=notes)


def load_reviews(repo_root: Path) -> dict[str, ReviewRecord]:
	resolved_root = repo_root.resolve()
	review_directory = resolved_root / CONTENT_ROOT / "reviews"
	if review_directory.is_dir():
		payloads = [read_record(path) for path in sorted(review_directory.rglob("*.json"))]
	else:
		payloads = [decode(row) for row in db.all_rows(table(resolved_root, "reviews"))]
	reviews: dict[str, ReviewRecord] = {}
	for record in payloads:
		type_path = record.get("type_path")
		if not isinstance(type_path, str):
			raise ValueError("Review record must contain a type_path.")
		reviews[type_path] = _review_from_raw(type_path, record)
	return reviews


def save_group(
	repo_root: Path,
	group: GroupRecord,
	*,
	expected_record_hash: str | None = None,
	enforce_record_hash: bool = False,
	require_new: bool = False,
) -> GroupRecord:
	_validate_group_id(group.id)
	payload = _group_payload(group)
	_group_from_raw(payload)
	resolved_root = repo_root.resolve()
	with repository_write_lock(resolved_root):
		from .reconcile import materialize_legacy_records

		materialize_legacy_records(resolved_root, "group")
		path = record_path(resolved_root, "group", group.id)
		previous_payload = read_record(path) if path.exists() else None
		current_hash = canonical_record_hash(previous_payload) if previous_payload is not None else None
		if require_new and previous_payload is not None:
			raise RecordConflict(
				record_id=group.id,
				expected_hash=None,
				current_hash=current_hash,
				base=None,
				current=previous_payload,
				proposed=payload,
			)
		if (enforce_record_hash or expected_record_hash is not None) and expected_record_hash != current_hash:
			raise RecordConflict(
				record_id=group.id,
				expected_hash=expected_record_hash,
				current_hash=current_hash,
				base=None,
				current=previous_payload,
				proposed=payload,
			)
		atomic_write_record(path, payload)
	return group


def delete_group(repo_root: Path, group_id: str, *, expected_record_hash: str) -> int:
	"""Delete one group and remove its ID from every manual assignment atomically."""
	_validate_group_id(group_id)
	resolved_root = repo_root.resolve()
	with repository_write_lock(resolved_root):
		from .reconcile import materialize_legacy_records

		materialize_legacy_records(resolved_root, "group")
		materialize_legacy_records(resolved_root, "assignment")
		group_path = record_path(resolved_root, "group", group_id)
		if not group_path.exists():
			raise ValueError(f"Group '{group_id}' was not found.")
		group_payload = read_record(group_path)
		current_hash = canonical_record_hash(group_payload)
		if expected_record_hash != current_hash:
			raise RecordConflict(
				record_id=group_id,
				expected_hash=expected_record_hash,
				current_hash=current_hash,
				base=None,
				current=group_payload,
				proposed=None,
			)

		assignment_root = resolved_root / CONTENT_ROOT / "assignments"
		updates: list[tuple[Path, dict[str, object], dict[str, object] | None]] = []
		if assignment_root.is_dir():
			for path in sorted(assignment_root.rglob("*.json")):
				payload = read_record(path)
				group_ids = payload.get("group_ids")
				if not isinstance(group_ids, list) or group_id not in group_ids:
					continue
				remaining = [value for value in group_ids if value != group_id]
				updated = {**payload, "group_ids": remaining} if remaining else None
				updates.append((path, payload, updated))

		try:
			for path, _previous, updated in updates:
				if updated is None:
					path.unlink()
				else:
					atomic_write_record(path, updated)
			group_path.unlink()
		except Exception:
			atomic_write_record(group_path, group_payload)
			for path, previous, _updated in updates:
				atomic_write_record(path, previous)
			raise
		return len(updates)


def save_group_assignments(
	repo_root: Path,
	type_path: str,
	group_ids: tuple[str, ...],
	*,
	expected_record_hash: str | None = None,
	enforce_record_hash: bool = False,
) -> None:
	if not type_path.startswith("/"):
		raise ValueError("Group assignments must use absolute type paths.")
	config = load_groups(repo_root)
	if any(group_id not in {group.id for group in config.groups} for group_id in group_ids):
		raise ValueError("Group assignments reference an unknown group.")
	resolved_root = repo_root.resolve()
	with repository_write_lock(resolved_root):
		from .reconcile import materialize_legacy_records

		materialize_legacy_records(resolved_root, "assignment")
		path = record_path(resolved_root, "assignment", type_path)
		previous_payload = read_record(path) if path.exists() else None
		current_hash = canonical_record_hash(previous_payload) if previous_payload is not None else None
		payload = {"type_path": type_path, "group_ids": list(group_ids)}
		if (enforce_record_hash or expected_record_hash is not None) and expected_record_hash != current_hash:
			raise RecordConflict(
				record_id=type_path,
				expected_hash=expected_record_hash,
				current_hash=current_hash,
				base=None,
				current=previous_payload,
				proposed=payload if group_ids else None,
			)
		if group_ids:
			atomic_write_record(path, payload)
		else:
			path.unlink(missing_ok=True)


def save_review(
	repo_root: Path,
	type_path: str,
	record: ReviewRecord | None,
	*,
	expected_record_hash: str | None = None,
	enforce_record_hash: bool = False,
) -> None:
	if not type_path.startswith("/"):
		raise ValueError("Review keys must be absolute type paths.")
	resolved_root = repo_root.resolve()
	with repository_write_lock(resolved_root):
		from .reconcile import materialize_legacy_records

		materialize_legacy_records(resolved_root, "review")
		path = record_path(resolved_root, "review", type_path)
		previous_payload = read_record(path) if path.exists() else None
		current_hash = canonical_record_hash(previous_payload) if previous_payload is not None else None
		if record is None:
			if (enforce_record_hash or expected_record_hash is not None) and expected_record_hash != current_hash:
				raise RecordConflict(
					record_id=type_path,
					expected_hash=expected_record_hash,
					current_hash=current_hash,
					base=None,
					current=previous_payload,
					proposed=None,
				)
			path.unlink(missing_ok=True)
			return
		validated = _review_from_raw(type_path, {
			"status": record.status,
			"reviewed_by": record.reviewed_by,
			"reviewed_at": record.reviewed_at,
			"notes": record.notes,
		})
		payload = {
			"type_path": type_path,
			"status": validated.status,
			"reviewed_by": validated.reviewed_by,
			"reviewed_at": validated.reviewed_at,
			"notes": validated.notes,
		}
		if (enforce_record_hash or expected_record_hash is not None) and expected_record_hash != current_hash:
			raise RecordConflict(
				record_id=type_path,
				expected_hash=expected_record_hash,
				current_hash=current_hash,
				base=None,
				current=previous_payload,
				proposed=payload,
			)
		atomic_write_record(path, payload)


def _flatten_text(value: object) -> str:
	if isinstance(value, dict):
		return " ".join(_flatten_text(item) for item in value.values())
	if isinstance(value, list):
		return " ".join(_flatten_text(item) for item in value)
	return str(value or "")


@lru_cache(maxsize=256)
def _keyword_pattern(keyword: str) -> re.Pattern[str]:
	return re.compile(rf"(?<![a-z0-9]){re.escape(keyword.casefold())}(?![a-z0-9])")


def _keyword_matches(keyword: str, search_text: str) -> bool:
	return _keyword_pattern(keyword).search(search_text) is not None


_FIELD_DISPLAY_NAMES = {
	"type_path": "type path",
	"parent_type": "parent type",
	"label": "label",
	"name": "name",
	"description": "description",
}


def _target_search_fields(target: CatalogTarget) -> dict[str, str]:
	"""Return this target's searchable text, keyed by the field ids in `KEYWORD_SCOPE_FIELDS`."""
	raw_target = thaw_json(target.raw_data)
	if not isinstance(raw_target, dict):
		return {}
	base_values = raw_target.get("base_values")
	search_values = {
		"type_path": raw_target.get("type_path"),
		"parent_type": raw_target.get("parent_type"),
		"label": raw_target.get("label"),
		"name": base_values.get("name") if isinstance(base_values, dict) else None,
		"description": base_values.get("description") if isinstance(base_values, dict) else None,
	}
	search_fields: dict[str, str] = {}
	for field_name, value in search_values.items():
		if value is None:
			continue
		field_text = _flatten_text(value)
		if field_text:
			search_fields[field_name] = field_text
	return search_fields


def classify_target_details(target: CatalogTarget, groups: GroupConfig) -> dict[str, tuple[str, ...]]:
	search_fields = _target_search_fields(target)
	type_path = target.type_path or ""
	assigned_ids = groups.assignments.get(type_path, ())
	classified: dict[str, tuple[str, ...]] = {}
	for group in groups.groups:
		reasons: list[str] = []
		if group.id in assigned_ids:
			reasons.append("manual assignment")
		for prefix in group.type_path_prefixes:
			if type_path == prefix or type_path.startswith(prefix + "/"):
				reasons.append(f"type path prefix '{prefix}'")
		for keyword in group.keywords:
			keyword_pattern = _keyword_pattern(keyword)
			for field_name, field_value in search_fields.items():
				if field_name not in group.keyword_scope:
					continue
				if keyword_pattern.search(field_value.casefold()):
					reasons.append(f"keyword '{keyword}' in {_FIELD_DISPLAY_NAMES.get(field_name, field_name)}")
		if reasons:
			classified[group.id] = tuple(reasons)
	return classified


def classify_target(target: CatalogTarget, groups: GroupConfig) -> tuple[str, ...]:
	return tuple(classify_target_details(target, groups))

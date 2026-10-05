"""Shared test helpers for seeding the store directly, replacing the old write-JSON-files-to-disk test
fixtures now that `tools/lore_editor` reads and writes `webapp/store` tables instead of per-record JSON."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from webapp.store import db
from webapp.store.generations import staged_projection
from webapp.store.metadata import active_projection
from webapp.store.schema import TABLE_SCHEMAS, encode, writable_table


def legacy_table(repo_root: Path, name: str):
	"""Explicit writable setup for tests of the low-level table primitives."""
	return db.get_or_create_table(repo_root, name, TABLE_SCHEMAS[name])


@contextmanager
def fixture_table(repo_root: Path, name: str):
	"""Seed a table without silently changing the fixture's provenance manifests."""
	active = active_projection(repo_root)
	if active.metadata is None:
		yield legacy_table(repo_root, name)
	else:
		with staged_projection(repo_root, content_revision=active.metadata.revision.content_revision, changed_tables={name}) as staged:
			yield writable_table(repo_root, name, store_dir=staged.path)


def seed_targets(repo_root: Path, targets: list[dict[str, object]]) -> None:
	rows = []
	for target in targets:
		base_values = target.get("base_values")
		name = base_values.get("name") if isinstance(base_values, dict) else None
		description = base_values.get("description") if isinstance(base_values, dict) else None
		rows.append({
			"id": target["type_path"],
			"type_path": target["type_path"],
			"raw_json": encode(target),
			"text": " ".join(str(value) for value in (target.get("type_path"), target.get("label"), name, description) if value),
		})
	with fixture_table(repo_root, "catalog_targets") as targets_table:
		db.replace_all_rows(targets_table, rows)


def seed_override(repo_root: Path, group: str, entry: dict[str, object]) -> None:
	with fixture_table(repo_root, "overrides") as overrides_table:
		db.upsert_rows(overrides_table, "id", [{
			"id": entry["id"],
			"type_path": str(entry.get("type_path") or ""),
			"group": group,
			"raw_json": encode(entry),
			"text": " ".join(str(value) for value in (entry.get("id"), entry.get("type_path"), entry.get("name"), entry.get("description")) if value),
		}])


def seed_group(repo_root: Path, group: dict[str, object]) -> None:
	with fixture_table(repo_root, "groups") as groups_table:
		db.upsert_rows(groups_table, "id", [{
			"id": group["id"],
			"raw_json": encode(group),
			"text": str(group.get("label", "")),
		}])


def seed_review(repo_root: Path, type_path: str, review: dict[str, object]) -> None:
	with fixture_table(repo_root, "reviews") as reviews_table:
		db.upsert_rows(reviews_table, "id", [{
			"id": type_path,
			"type_path": type_path,
			"raw_json": encode({"type_path": type_path, **review}),
			"text": type_path,
		}])


def seed_assignment(repo_root: Path, type_path: str, group_ids: list[str]) -> None:
	with fixture_table(repo_root, "assignments") as assignments_table:
		db.upsert_rows(assignments_table, "id", [{
			"id": type_path,
			"type_path": type_path,
			"raw_json": encode({"type_path": type_path, "group_ids": group_ids}),
			"text": type_path,
		}])

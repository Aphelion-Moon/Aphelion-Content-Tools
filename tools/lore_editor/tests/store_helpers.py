"""Shared test helpers for seeding the store directly, replacing the old write-JSON-files-to-disk test
fixtures now that `tools/lore_editor` reads and writes `webapp/store` tables instead of per-record JSON."""

from __future__ import annotations

from pathlib import Path

from webapp.store import db
from webapp.store.schema import encode, table


def seed_targets(repo_root: Path, targets: list[dict[str, object]]) -> None:
	targets_table = table(repo_root, "catalog_targets")
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
	db.replace_all_rows(targets_table, rows)


def seed_override(repo_root: Path, group: str, entry: dict[str, object]) -> None:
	overrides_table = table(repo_root, "overrides")
	db.upsert_rows(overrides_table, "id", [{
		"id": entry["id"],
		"type_path": str(entry.get("type_path") or ""),
		"group": group,
		"raw_json": encode(entry),
		"text": " ".join(str(value) for value in (entry.get("id"), entry.get("type_path"), entry.get("name"), entry.get("description")) if value),
	}])


def seed_group(repo_root: Path, group: dict[str, object]) -> None:
	groups_table = table(repo_root, "groups")
	db.upsert_rows(groups_table, "id", [{
		"id": group["id"],
		"raw_json": encode(group),
		"text": str(group.get("label", "")),
	}])


def seed_review(repo_root: Path, type_path: str, review: dict[str, object]) -> None:
	reviews_table = table(repo_root, "reviews")
	slug = type_path.strip("/").replace("/", "-").casefold() or "root"
	db.upsert_rows(reviews_table, "id", [{
		"id": slug,
		"type_path": type_path,
		"raw_json": encode({"type_path": type_path, **review}),
		"text": type_path,
	}])


def seed_assignment(repo_root: Path, type_path: str, group_ids: list[str]) -> None:
	assignments_table = table(repo_root, "assignments")
	slug = type_path.strip("/").replace("/", "-").casefold() or "root"
	db.upsert_rows(assignments_table, "id", [{
		"id": slug,
		"type_path": type_path,
		"raw_json": encode({"type_path": type_path, "group_ids": group_ids}),
		"text": type_path,
	}])

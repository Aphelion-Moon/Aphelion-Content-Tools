from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from tools.lore_editor.write_coordinator import repository_write_lock
from webapp.store import db
from webapp.store.generations import staged_projection
from webapp.store.schema import decode, encode, table, writable_table

VALID_KINDS = frozenset(("catalog_target", "graph_node", "file", "definition"))
VALID_TOOLS = frozenset(("lore-editor", "graph", "file-management", "job-editor", "outfit-editor"))


@contextmanager
def _reference_write(repo_root: Path):
	from tools.lore_editor.reconcile import reconcile_projection

	with repository_write_lock(repo_root):
		reconciled = reconcile_projection(repo_root)
		with staged_projection(repo_root, content_revision=reconciled.content_revision, changed_tables={"references"}) as staged:
			yield writable_table(repo_root, "references", store_dir=staged.path)


def _reference_search_text(payload: dict[str, object]) -> str:
	return " ".join(str(value) for value in (payload.get("label"), payload.get("key"), payload.get("path")) if value)


def list_references(repo_root: Path) -> list[dict[str, object]]:
	rows = db.all_rows(table(repo_root, "references"))
	references = [decode(row) for row in rows]
	references.sort(key=lambda reference: reference.get("created_at", ""))
	return references


def add_reference(repo_root: Path, payload: object) -> dict[str, object]:
	if not isinstance(payload, dict):
		raise ValueError("Reference payload must be a JSON object.")
	tool = payload.get("tool")
	kind = payload.get("kind")
	key = payload.get("key")
	label = payload.get("label")
	if tool not in VALID_TOOLS:
		raise ValueError(f"Reference tool must be one of {sorted(VALID_TOOLS)}.")
	if kind not in VALID_KINDS:
		raise ValueError(f"Reference kind must be one of {sorted(VALID_KINDS)}.")
	if not isinstance(key, str) or not key:
		raise ValueError("Reference key must be a non-empty string.")
	if not isinstance(label, str) or not label:
		raise ValueError("Reference label must be a non-empty string.")
	catalog_id = payload.get('catalog_id')
	if kind == 'definition' and (not isinstance(catalog_id, str) or not catalog_id):
		raise ValueError('Definition references require source snapshot provenance.')
	path = payload.get("path")
	if path is not None and not isinstance(path, str):
		raise ValueError("Reference path must be a string when provided.")
	note = payload.get("note")
	if note is not None and not isinstance(note, str):
		raise ValueError("Reference note must be a string when provided.")

	record = {
		"id": str(uuid.uuid4()),
		"tool": tool,
		"kind": kind,
		"key": key,
		"label": label,
		"path": path,
		"note": note or "",
		"created_at": datetime.now(UTC).isoformat(),
		**({'catalog_id': catalog_id} if kind == 'definition' else {}),
	}
	with _reference_write(repo_root) as references_table:
		db.upsert_rows(references_table, "id", [{
			"id": record["id"],
			"tool": tool,
			"kind": kind,
			"key": key,
			"raw_json": encode(record),
			"text": _reference_search_text(record),
		}])
	return record


def remove_reference(repo_root: Path, reference_id: str) -> None:
	with _reference_write(repo_root) as references_table:
		if db.get_row_by_key(references_table, "id", reference_id) is None:
			raise ValueError(f"Reference '{reference_id}' was not found.")
		db.delete_row_by_key(references_table, "id", reference_id)

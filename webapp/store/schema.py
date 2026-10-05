from __future__ import annotations

import json
from collections.abc import Mapping

import pyarrow as pa

from .db import (
	CONTENT_HASH_FIELD,
	EMBEDDING_HASH_FIELD,
	RECORD_HASH_FIELD,
	TEXT_FIELD,
	VECTOR_FIELD,
	WritableTable,
	get_or_create_table,
	read_table,
)

# Every table shares the same shape: a handful of small "promoted" columns used for keys and predicate
# filtering (`.where(...)`), one `raw_json` column holding the complete record as JSON (the single source
# of truth -- callers decode it back into the exact same dict shape the old per-record JSON file used to
# hold, so `model.py`'s existing `make_lore_entry`/`make_catalog_target` and everything downstream of them
# is unaffected by this storage change), and the shared `text`/`vector` search columns every table gets for
# free via `webapp/store/search.py`.

CATALOG_TARGETS_SCHEMA = pa.schema([
	pa.field("id", pa.string()),
	pa.field("type_path", pa.string()),
	pa.field("raw_json", pa.string()),
	TEXT_FIELD,
	CONTENT_HASH_FIELD,
	RECORD_HASH_FIELD,
	EMBEDDING_HASH_FIELD,
	VECTOR_FIELD,
])

OVERRIDES_SCHEMA = pa.schema([
	pa.field("id", pa.string()),
	pa.field("type_path", pa.string()),
	pa.field("group", pa.string()),
	pa.field("raw_json", pa.string()),
	TEXT_FIELD,
	CONTENT_HASH_FIELD,
	RECORD_HASH_FIELD,
	EMBEDDING_HASH_FIELD,
	VECTOR_FIELD,
])

GROUPS_SCHEMA = pa.schema([
	pa.field("id", pa.string()),
	pa.field("raw_json", pa.string()),
	TEXT_FIELD,
	CONTENT_HASH_FIELD,
	RECORD_HASH_FIELD,
	EMBEDDING_HASH_FIELD,
	VECTOR_FIELD,
])

REVIEWS_SCHEMA = pa.schema([
	pa.field("id", pa.string()),
	pa.field("type_path", pa.string()),
	pa.field("raw_json", pa.string()),
	TEXT_FIELD,
	CONTENT_HASH_FIELD,
	RECORD_HASH_FIELD,
	EMBEDDING_HASH_FIELD,
	VECTOR_FIELD,
])

ASSIGNMENTS_SCHEMA = pa.schema([
	pa.field("id", pa.string()),
	pa.field("type_path", pa.string()),
	pa.field("raw_json", pa.string()),
	TEXT_FIELD,
	CONTENT_HASH_FIELD,
	RECORD_HASH_FIELD,
	EMBEDDING_HASH_FIELD,
	VECTOR_FIELD,
])

GRAPH_NODES_SCHEMA = pa.schema([
	pa.field("id", pa.string()),
	pa.field("kind", pa.string()),
	pa.field("path", pa.string()),
	pa.field("raw_json", pa.string()),
	TEXT_FIELD,
	CONTENT_HASH_FIELD,
	RECORD_HASH_FIELD,
	EMBEDDING_HASH_FIELD,
	VECTOR_FIELD,
])

GRAPH_EDGES_SCHEMA = pa.schema([
	pa.field("id", pa.string()),
	pa.field("source", pa.string()),
	pa.field("target", pa.string()),
	pa.field("relation", pa.string()),
	pa.field("raw_json", pa.string()),
	TEXT_FIELD,
	CONTENT_HASH_FIELD,
	RECORD_HASH_FIELD,
	EMBEDDING_HASH_FIELD,
	VECTOR_FIELD,
])

UNRESOLVED_MARKERS_SCHEMA = pa.schema([
	pa.field("id", pa.string()),
	pa.field("core_file", pa.string()),
	pa.field("raw_json", pa.string()),
	TEXT_FIELD,
	CONTENT_HASH_FIELD,
	RECORD_HASH_FIELD,
	EMBEDDING_HASH_FIELD,
	VECTOR_FIELD,
])

MANIFESTS_SCHEMA = pa.schema([
	pa.field("id", pa.string()),
	pa.field("raw_json", pa.string()),
	TEXT_FIELD,
	CONTENT_HASH_FIELD,
	RECORD_HASH_FIELD,
	EMBEDDING_HASH_FIELD,
	VECTOR_FIELD,
])

REFERENCES_SCHEMA = pa.schema([
	pa.field("id", pa.string()),
	pa.field("tool", pa.string()),
	pa.field("kind", pa.string()),
	pa.field("key", pa.string()),
	pa.field("raw_json", pa.string()),
	TEXT_FIELD,
	CONTENT_HASH_FIELD,
	RECORD_HASH_FIELD,
	EMBEDDING_HASH_FIELD,
	VECTOR_FIELD,
])

TABLE_SCHEMAS: dict[str, pa.Schema] = {
	"catalog_targets": CATALOG_TARGETS_SCHEMA,
	"overrides": OVERRIDES_SCHEMA,
	"groups": GROUPS_SCHEMA,
	"reviews": REVIEWS_SCHEMA,
	"assignments": ASSIGNMENTS_SCHEMA,
	"graph_nodes": GRAPH_NODES_SCHEMA,
	"graph_edges": GRAPH_EDGES_SCHEMA,
	"unresolved_markers": UNRESOLVED_MARKERS_SCHEMA,
	"manifests": MANIFESTS_SCHEMA,
	"references": REFERENCES_SCHEMA,
}

# These records contain paths, identifiers, and structural relations rather than natural-language
# prose. Full-text search is both more accurate and dramatically cheaper than embedding tens of
# thousands of them during every fresh graph projection.
KEYWORD_ONLY_TABLES = frozenset(("graph_nodes", "graph_edges", "unresolved_markers"))


def table(repo_root, name: str, *, store_dir=None):
	if name not in TABLE_SCHEMAS:
		raise ValueError(f"Unknown store table '{name}'.")
	return read_table(repo_root, name, store_dir=store_dir)


def writable_table(repo_root, name: str, *, store_dir):
	from .generations import require_staged_table

	if name not in TABLE_SCHEMAS:
		raise ValueError(f"Unknown store table '{name}'.")
	stage = require_staged_table(store_dir, name)
	opened = get_or_create_table(repo_root, name, TABLE_SCHEMAS[name], store_dir=store_dir)
	return WritableTable(opened, stage.require_active)


def decode(row: dict[str, object]) -> dict[str, object]:
	return json.loads(row["raw_json"])


def encode(payload: Mapping[str, object]) -> str:
	return json.dumps(payload, ensure_ascii=False, sort_keys=True)

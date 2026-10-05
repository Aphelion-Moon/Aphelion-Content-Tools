from __future__ import annotations

import hashlib
import json
import re
import weakref
from collections import OrderedDict
from collections.abc import Callable, Mapping
from datetime import timedelta
from pathlib import Path
from threading import Lock

import lancedb
import pyarrow as pa
from lancedb.index import FTS

from .embeddings import EMBEDDING_DIM, EMBEDDING_MODEL_NAME, embed_texts
from .lifecycle import acquire_projection, read_projection, selected_projection
from .metadata import PROJECTION_MARKER_FILE, table_directory

STORE_RELATIVE_PATH = Path("webapp/store/data")

# Rows are re-embedded only when their `text` actually changed since the last write -- see
# `sync_snapshot` below. Embedding the full ~20,000-row real catalog measured at ~42 texts/sec during
# investigation (2026-08-22): re-embedding everything on every refresh, unconditionally, is what made
# "Refresh and Validate" hang for 15+ minutes with no progress output and no way to cancel.
SYNC_CHUNK_SIZE = 500
KEYWORD_ONLY_EMBEDDING_MODEL_ID = "keyword-only-v1"

MAX_CACHED_CONNECTIONS = 8
_connections: OrderedDict[str, object] = OrderedDict()
_connections_lock = Lock()

_generation = 0
_generation_lock = Lock()


def current_generation() -> int:
	"""A process-wide counter bumped by every store write.

	Callers combine this cheap same-process signal with the active projection generation stored on disk.
	The durable generation catches atomic projection activation, including the separate job worker's
	writes. This counter also invalidates legacy fixture caches during direct table setup."""
	with _generation_lock:
		return _generation


def _bump_generation() -> None:
	global _generation
	with _generation_lock:
		_generation += 1

VECTOR_FIELD = pa.field("vector", pa.list_(pa.float32(), EMBEDDING_DIM))
TEXT_FIELD = pa.field("text", pa.string())
CONTENT_HASH_FIELD = pa.field("content_hash", pa.string())
RECORD_HASH_FIELD = pa.field("record_hash", pa.string())
EMBEDDING_HASH_FIELD = pa.field("embedding_hash", pa.string())
KEY_FIELD_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ReadTable:
	"""Expose only reads; native version checkout alone still allows merge writes."""

	def __init__(self, table):
		self._table = table

	@property
	def schema(self):
		return self._table.schema

	def search(self, *args, **kwargs):
		return self._table.search(*args, **kwargs)

	def count_rows(self, *args, **kwargs):
		return self._table.count_rows(*args, **kwargs)

	def __getattr__(self, name: str):
		raise AttributeError(f"Read-only projection table does not expose '{name}'.")


class _StagedMerge:
	def __init__(self, builder, require_active: Callable[[], None]):
		self._builder = builder
		self._require_active = require_active

	def when_matched_update_all(self, *args, **kwargs):
		self._require_active()
		self._builder.when_matched_update_all(*args, **kwargs)
		return self

	def when_not_matched_insert_all(self, *args, **kwargs):
		self._require_active()
		self._builder.when_not_matched_insert_all(*args, **kwargs)
		return self

	def execute(self, *args, **kwargs):
		self._require_active()
		return self._builder.execute(*args, **kwargs)


class WritableTable(ReadTable):
	def __init__(self, table, require_active: Callable[[], None]):
		super().__init__(table)
		self._require_active = require_active

	def merge_insert(self, *args, **kwargs):
		self._require_active()
		return _StagedMerge(self._table.merge_insert(*args, **kwargs), self._require_active)

	def add(self, *args, **kwargs):
		self._require_active()
		return self._table.add(*args, **kwargs)

	def delete(self, *args, **kwargs):
		self._require_active()
		return self._table.delete(*args, **kwargs)

	def optimize(self, *args, **kwargs):
		self._require_active()
		return self._table.optimize(*args, **kwargs)


def store_path(repo_root: Path) -> Path:
	return selected_projection(repo_root).path


def connect(repo_root: Path, *, store_dir: Path | None = None):
	lease = acquire_projection(repo_root, store_dir=store_dir, include_owners=False)
	path = lease.projection.path.resolve()
	key = str(path)
	try:
		with _connections_lock:
			connection = _connections.get(key)
			if connection is None:
				path.mkdir(parents=True, exist_ok=True)
				connection = lancedb.connect(str(path), read_consistency_interval=timedelta(0))
				if lease.handle is not None:
					# LanceTable retains its connection and queries retain their table.
					# Evict cache ownership only: a live query must keep its lease.
					weakref.finalize(connection, lease.close)
					lease = None
				_connections[key] = connection
			_connections.move_to_end(key)
			while len(_connections) > MAX_CACHED_CONNECTIONS:
				_connections.popitem(last=False)
			return connection
	finally:
		if lease is not None:
			lease.close()


def discard_connection(store_dir: Path) -> None:
	with _connections_lock:
		_connections.pop(str(store_dir.resolve()), None)


def get_or_create_table(repo_root: Path, name: str, schema: pa.Schema, *, store_dir: Path | None = None):
	"""Open a table, creating it (with an FTS index on its `text` column) if it doesn't exist yet."""
	path = store_dir if store_dir is not None else store_path(repo_root)
	if (path / PROJECTION_MARKER_FILE).exists():
		raise ValueError("Published projection tables require a new write stage.")
	connection = connect(repo_root, store_dir=store_dir)
	if name in connection.list_tables().tables:
		table = connection.open_table(name)
		missing_fields = [field for field in schema if field.name not in table.schema.names]
		if missing_fields:
			table.add_columns(missing_fields)
		return table
	table = connection.create_table(name, schema=schema)
	table.create_index("text", config=FTS())
	return table


def read_table(repo_root: Path, name: str, *, store_dir: Path | None = None):
	with read_projection(repo_root, store_dir=store_dir) as projection:
		path = table_directory(repo_root, name, projection)
		if path is None:
			return None
		opened = connect(repo_root, store_dir=path.parent).open_table(name)
		opened.checkout(opened.version)
		return ReadTable(opened)


def with_embedding(row: dict[str, object]) -> dict[str, object]:
	"""Return `row` with its `vector` column filled in from its `text` column.

	Every table write goes through this so no caller has to remember to embed -- callers just build the
	structured + `text` fields and this fills in the rest.
	"""
	row = dict(row)
	row["vector"] = embed_texts([row.get("text") or ""])[0]
	return row


def with_embeddings(rows: list[dict[str, object]]) -> list[dict[str, object]]:
	texts = [row.get("text") or "" for row in rows]
	vectors = embed_texts(texts)
	# strict=True: a short vector list would otherwise silently truncate the write, dropping rows with no
	# error -- data loss that only shows up later as a missing search result.
	return [{**row, "vector": vector} for row, vector in zip(rows, vectors, strict=True)]


def upsert_rows(table, key_field: str, rows: list[dict[str, object]]) -> None:
	"""Insert-or-update `rows` by `key_field`, embedding each row's `text` column first."""
	if not rows:
		return
	table.merge_insert(key_field).when_matched_update_all().when_not_matched_insert_all().execute(
		with_embeddings(rows)
	)
	_bump_generation()


def replace_all_rows(table, rows: list[dict[str, object]]) -> None:
	"""Atomically replace a table's entire contents. Only used directly by tests and by callers that
	genuinely want an unconditional full rewrite (e.g. seeding a fresh table); real whole-corpus refreshes
	(catalog refresh, content-graph scan) should use `sync_snapshot` instead, which skips re-embedding
	rows whose content hasn't changed."""
	table.delete("true")
	if rows:
		table.add(with_embeddings(rows))
	_bump_generation()


def content_hash_for(text: str) -> str:
	return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def record_hash_for(row: Mapping[str, object]) -> str:
	payload = {
		key: value
		for key, value in row.items()
		if key not in {"vector", "content_hash", "record_hash", "embedding_hash"}
	}
	encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
	return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def embedding_hash_for(text: str, model_id: str = EMBEDDING_MODEL_NAME) -> str:
	return hashlib.sha256(f"{model_id}\0{text or ''}".encode()).hexdigest()


def _sql_string_literal(value: str) -> str:
	escaped_value = value.replace("'", "''")
	return f"'{escaped_value}'"


def sync_snapshot(
	table,
	key_field: str,
	rows: list[dict[str, object]],
	*,
	chunk_size: int = SYNC_CHUNK_SIZE,
	embedding_model_id: str = EMBEDDING_MODEL_NAME,
	embed: bool = True,
	on_progress=None,
) -> None:
	"""Replace a table's contents with `rows`, but only re-embed rows whose `text` actually changed.

	This is the whole-corpus write path for catalog refresh and content-graph scans -- the operations
	that used to call `replace_all_rows` unconditionally and re-embed everything, every time, regardless
	of what changed. `record_hash` covers the complete logical row while `embedding_hash` covers search
	text and model identity. Complete-record changes are therefore persisted even when search text stays
	the same, while an unchanged embedding is reused. `content_hash` mirrors `record_hash` during the
	store-format transition so existing tables can be upgraded in place. Changed/new rows are written in
	`chunk_size`-row batches via `merge_insert`, calling `on_progress(done, total)` after each chunk if
	given. Rows present in the table but absent from `rows` are deleted because this is a snapshot sync.

	A kill between chunks leaves every already-committed chunk intact -- unlike `replace_all_rows`, the
	table is never fully empty mid-operation. `embed=False` stores zero vectors under a distinct model ID
	for keyword-only projection tables, without loading or invoking the embedding model.
	"""
	effective_embedding_model_id = embedding_model_id if embed else KEYWORD_ONLY_EMBEDDING_MODEL_ID
	incoming_ids = {str(row[key_field]) for row in rows}
	existing = {
		str(existing_row[key_field]): existing_row
		for existing_row in table.search().select([
			key_field,
			"text",
			"vector",
			"content_hash",
			"record_hash",
			"embedding_hash",
		]).to_list()
	}

	stale_ids = set(existing) - incoming_ids
	if stale_ids:
		id_list = ", ".join(_sql_string_literal(stale_id) for stale_id in stale_ids)
		table.delete(f"{key_field} IN ({id_list})")

	rows_with_hash = []
	for row in rows:
		record_hash = record_hash_for(row)
		embedding_hash = embedding_hash_for(str(row.get("text") or ""), effective_embedding_model_id)
		rows_with_hash.append({
			**row,
			"content_hash": record_hash,
			"record_hash": record_hash,
			"embedding_hash": embedding_hash,
		})
	changed_rows = [
		row
		for row in rows_with_hash
		if (
			existing.get(str(row[key_field]), {}).get("record_hash") != row["record_hash"]
			or existing.get(str(row[key_field]), {}).get("embedding_hash") != row["embedding_hash"]
		)
	]

	total = len(changed_rows)
	for start in range(0, total, chunk_size):
		chunk = changed_rows[start:start + chunk_size]
		ready_rows: list[dict[str, object]] = []
		rows_to_embed: list[dict[str, object]] = []
		for row in chunk:
			existing_row = existing.get(str(row[key_field]))
			embedding_unchanged = existing_row is not None and (
				existing_row.get("embedding_hash") == row["embedding_hash"]
				or (
					not existing_row.get("embedding_hash")
					and existing_row.get("text") == row.get("text")
				)
			)
			if embedding_unchanged and existing_row.get("vector") is not None:
				ready_rows.append({**row, "vector": existing_row["vector"]})
			else:
				rows_to_embed.append(row)
		if rows_to_embed:
			if embed:
				ready_rows.extend(with_embeddings(rows_to_embed))
			else:
				ready_rows.extend({**row, "vector": [0.0] * EMBEDDING_DIM} for row in rows_to_embed)
		table.merge_insert(key_field).when_matched_update_all().when_not_matched_insert_all().execute(
			ready_rows
		)
		if on_progress is not None:
			on_progress(min(start + chunk_size, total), total)

	if stale_ids or changed_rows:
		_bump_generation()


def optimize_all_tables(repo_root: Path, *, on_progress=None) -> list[str]:
	"""Run LanceDB's built-in maintenance (`Table.optimize()`) on every table: compact small fragments,
	prune file versions older than the default 7-day retention window, and fold newly-written rows into
	the vector/FTS indexes. This never touches row content, only how it's stored on disk -- it's what
	keeps the store from silently accumulating fragment/version files forever, since nothing else in
	this codebase ever calls it. Deliberately left at the default retention rather than
	`cleanup_older_than=timedelta(0)`: an aggressive zero-retention cleanup can break a write that's
	concurrently in flight, which isn't worth the marginal extra disk space for a local desktop store.

	Returns the list of table names optimized, in order, for the caller to report."""
	from tools.lore_editor.reconcile import reconcile_projection, scan_canonical_records
	from tools.lore_editor.write_coordinator import repository_write_lock

	from .generations import staged_projection
	from .schema import TABLE_SCHEMAS, writable_table

	names = list(TABLE_SCHEMAS)
	with repository_write_lock(repo_root):
		reconcile_projection(repo_root)
		content_revision = scan_canonical_records(repo_root).content_revision
		with staged_projection(repo_root, content_revision=content_revision, changed_tables=names) as staged:
			for index, name in enumerate(names):
				writable_table(repo_root, name, store_dir=staged.path).optimize()
				if on_progress is not None:
					on_progress(name, index + 1, len(names))
	return names


def delete_rows(table, where: str) -> None:
	table.delete(where)
	_bump_generation()


def _key_predicate(key_field: str, key: str) -> str:
	if not KEY_FIELD_PATTERN.fullmatch(key_field):
		raise ValueError(f"Invalid store key field '{key_field}'.")
	return f"{key_field} = {_sql_string_literal(key)}"


def delete_row_by_key(table, key_field: str, key: str) -> None:
	"""Delete the row whose `key_field` exactly equals `key`."""
	delete_rows(table, _key_predicate(key_field, key))


def get_row_by_key(table, key_field: str, key: str) -> dict[str, object] | None:
	"""Return the row whose `key_field` exactly equals `key`, if present."""
	return get_row(table, _key_predicate(key_field, key))


def all_rows(table, *, where: str | None = None) -> list[dict[str, object]]:
	if table is None:
		return []
	query = table.search()
	if where is not None:
		query = query.where(where)
	return query.to_list()


def get_row(table, where: str) -> dict[str, object] | None:
	if table is None:
		return None
	rows = table.search().where(where).limit(1).to_list()
	return rows[0] if rows else None

from __future__ import annotations

import hashlib
from pathlib import Path
from threading import Lock

import lancedb
import pyarrow as pa
from lancedb.index import FTS

from .embeddings import EMBEDDING_DIM, embed_texts

STORE_RELATIVE_PATH = Path("webapp/store/data")

# Rows are re-embedded only when their `text` actually changed since the last write -- see
# `sync_snapshot` below. Embedding the full ~20,000-row real catalog measured at ~42 texts/sec during
# investigation (2026-08-22): re-embedding everything on every refresh, unconditionally, is what made
# "Refresh and Validate" hang for 15+ minutes with no progress output and no way to cancel.
SYNC_CHUNK_SIZE = 500

_connections: dict[str, object] = {}
_connections_lock = Lock()

_generation = 0
_generation_lock = Lock()


def current_generation() -> int:
	"""A process-wide counter bumped by every store write.

	This is a single local desktop tool, not a multi-tenant server, so one global counter is enough to
	let callers cheaply invalidate an in-memory computed-view cache (see `tools/lore_editor/api.py`'s
	review snapshot cache) without re-deriving anything from file mtimes the way the old JSON-file store
	had to. Note this is only ever bumped in whichever process performed the write -- tool runs execute
	inside the persistent store worker process (see `webapp/store_worker.py`), a different process from
	the main HTTP server, so this counter cannot be used to detect *that* process's writes from here;
	`webapp/store/health.py` uses on-disk file mtimes instead, for exactly this reason."""
	with _generation_lock:
		return _generation


def _bump_generation() -> None:
	global _generation
	with _generation_lock:
		_generation += 1

VECTOR_FIELD = pa.field("vector", pa.list_(pa.float32(), EMBEDDING_DIM))
TEXT_FIELD = pa.field("text", pa.string())
CONTENT_HASH_FIELD = pa.field("content_hash", pa.string())


def store_path(repo_root: Path) -> Path:
	return repo_root.resolve() / STORE_RELATIVE_PATH


def connect(repo_root: Path):
	path = store_path(repo_root)
	key = str(path)
	with _connections_lock:
		connection = _connections.get(key)
		if connection is None:
			path.mkdir(parents=True, exist_ok=True)
			connection = lancedb.connect(str(path))
			_connections[key] = connection
		return connection


def get_or_create_table(repo_root: Path, name: str, schema: pa.Schema):
	"""Open a table, creating it (with an FTS index on its `text` column) if it doesn't exist yet."""
	connection = connect(repo_root)
	if name in connection.table_names():
		return connection.open_table(name)
	table = connection.create_table(name, schema=schema)
	table.create_index("text", config=FTS())
	return table


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
	return [{**row, "vector": vector} for row, vector in zip(rows, vectors)]


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


def sync_snapshot(
	table,
	key_field: str,
	rows: list[dict[str, object]],
	*,
	chunk_size: int = SYNC_CHUNK_SIZE,
	on_progress=None,
) -> None:
	"""Replace a table's contents with `rows`, but only re-embed rows whose `text` actually changed.

	This is the whole-corpus write path for catalog refresh and content-graph scans -- the operations
	that used to call `replace_all_rows` unconditionally and re-embed everything, every time, regardless
	of what changed. Each row gets a `content_hash` (sha256 of its `text`); rows whose hash matches what's
	already stored are skipped entirely (no embedding call, no write). Changed/new rows are embedded and
	written in `chunk_size`-row batches via `merge_insert`, calling `on_progress(done, total)` after each
	chunk if given, so a caller streaming stdout (see `webapp/tooling.py`) has something to show during a
	genuinely large first-time sync. Rows present in the table but absent from `rows` are deleted (this
	is a *snapshot* sync, not a merge) in one bulk predicate, not row-by-row.

	A kill between chunks leaves every already-committed chunk intact -- unlike `replace_all_rows`, the
	table is never fully empty mid-operation.
	"""
	incoming_ids = {str(row[key_field]) for row in rows}
	existing = {
		str(existing_row[key_field]): existing_row.get("content_hash")
		for existing_row in table.search().select([key_field, "content_hash"]).to_list()
	}

	stale_ids = set(existing) - incoming_ids
	if stale_ids:
		id_list = ", ".join(f"'{stale_id}'" for stale_id in stale_ids)
		table.delete(f"{key_field} IN ({id_list})")

	rows_with_hash = [{**row, "content_hash": content_hash_for(row.get("text") or "")} for row in rows]
	changed_rows = [row for row in rows_with_hash if existing.get(str(row[key_field])) != row["content_hash"]]

	total = len(changed_rows)
	for start in range(0, total, chunk_size):
		chunk = changed_rows[start:start + chunk_size]
		table.merge_insert(key_field).when_matched_update_all().when_not_matched_insert_all().execute(
			with_embeddings(chunk)
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
	from .schema import TABLE_SCHEMAS, table as open_table

	names = list(TABLE_SCHEMAS)
	for index, name in enumerate(names):
		open_table(repo_root, name).optimize()
		if on_progress is not None:
			on_progress(name, index + 1, len(names))
	return names


def delete_rows(table, where: str) -> None:
	table.delete(where)
	_bump_generation()


def all_rows(table, *, where: str | None = None) -> list[dict[str, object]]:
	query = table.search()
	if where is not None:
		query = query.where(where)
	return query.to_list()


def get_row(table, where: str) -> dict[str, object] | None:
	rows = table.search().where(where).limit(1).to_list()
	return rows[0] if rows else None

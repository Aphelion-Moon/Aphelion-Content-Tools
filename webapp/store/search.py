from __future__ import annotations

from pathlib import Path

from .embeddings import embed_texts
from .schema import TABLE_SCHEMAS, decode, table

RRF_K = 60


def _rank_map(rows: list[dict[str, object]]) -> dict[str, int]:
	return {row["id"]: rank for rank, row in enumerate(rows, start=1)}


def _search_table(repo_root: Path, name: str, query: str, limit: int) -> list[dict[str, object]]:
	target_table = table(repo_root, name)
	fts_rows = target_table.search(query, query_type="fts").limit(limit).to_list()
	query_vector = embed_texts([query])[0]
	vector_rows = target_table.search(query_vector, query_type="vector").limit(limit).to_list()

	fts_ranks = _rank_map(fts_rows)
	vector_ranks = _rank_map(vector_rows)
	rows_by_id = {row["id"]: row for row in (*fts_rows, *vector_rows)}

	scored = []
	for row_id, row in rows_by_id.items():
		score = 0.0
		if row_id in fts_ranks:
			score += 1.0 / (RRF_K + fts_ranks[row_id])
		if row_id in vector_ranks:
			score += 1.0 / (RRF_K + vector_ranks[row_id])
		scored.append((score, row))
	scored.sort(key=lambda pair: pair[0], reverse=True)

	results = []
	for score, row in scored[:limit]:
		payload = decode(row)
		results.append({"table": name, "score": score, "id": row["id"], "record": payload})
	return results


def search(repo_root: Path, query: str, *, tables: list[str] | None = None, limit: int = 20) -> list[dict[str, object]]:
	"""Hybrid (keyword + semantic) search across one or more store tables.

	Runs an FTS (BM25) search and a vector-similarity search per table and merges them with reciprocal
	rank fusion -- simple, well-known, and needs no extra dependency. Returns up to `limit` results per
	requested table, each carrying which table it came from and its full decoded record so the caller can
	route a click back to the right tool.
	"""
	if not query.strip():
		return []
	table_names = tables or list(TABLE_SCHEMAS)
	unknown = set(table_names) - set(TABLE_SCHEMAS)
	if unknown:
		raise ValueError(f"Unknown search table(s): {', '.join(sorted(unknown))}.")
	results: list[dict[str, object]] = []
	for name in table_names:
		results.extend(_search_table(repo_root, name, query, limit))
	return results

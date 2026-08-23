from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .embeddings import embed_texts, embedding_status
from .schema import KEYWORD_ONLY_TABLES, TABLE_SCHEMAS, decode, table

RRF_K = 60
CONTEXT_BOOST_MAX = 0.006

TABLE_PRIORITY = {name: priority for priority, name in enumerate(TABLE_SCHEMAS)}
TABLE_TOOL = {
	"catalog_targets": "lore-editor",
	"overrides": "lore-editor",
	"groups": "lore-editor",
	"reviews": "lore-editor",
	"assignments": "lore-editor",
	"graph_nodes": "graph",
	"graph_edges": "graph",
	"unresolved_markers": "graph",
	"manifests": "file-management",
	"references": "file-management",
}
TOOL_ROUTE = {
	"lore-editor": "/lore-editor",
	"graph": "/graph",
	"file-management": "/file-management",
}
TABLE_RECORD_KIND = {
	"catalog_targets": "catalog_target",
	"overrides": "override",
	"groups": "group",
	"reviews": "review",
	"assignments": "assignment",
	"graph_nodes": "graph_node",
	"graph_edges": "graph_edge",
	"unresolved_markers": "unresolved_marker",
	"manifests": "manifest",
	"references": "reference",
}


@dataclass(frozen=True)
class SearchContext:
	tool: str | None = None
	record_kind: str | None = None
	record_id: str | None = None
	type_path: str | None = None
	groups: tuple[str, ...] = ()
	module: str | None = None


@dataclass(frozen=True)
class SearchReport:
	results: tuple[dict[str, object], ...]
	semantic_mode: str
	semantic_model_id: str
	semantic_reason: str | None = None


def _search_table_channels(
	repo_root: Path,
	name: str,
	query: str,
	limit: int,
	query_vector: list[float] | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
	target_table = table(repo_root, name)
	fts_rows = target_table.search(query, query_type="fts").limit(limit).to_list()
	vector_rows = []
	if query_vector is not None and name not in KEYWORD_ONLY_TABLES:
		vector_rows = target_table.search(query_vector, query_type="vector").limit(limit).to_list()
	return fts_rows, vector_rows


def _candidate_key(table_name: str, row: dict[str, object]) -> tuple[str, str]:
	return table_name, str(row["id"])


def _keyword_sort_key(candidate: tuple[str, dict[str, object], int]) -> tuple[float, int, str]:
	table_name, row, channel_rank = candidate
	score = row.get("_score")
	return (
		-float(score) if isinstance(score, int | float) else float(channel_rank),
		TABLE_PRIORITY[table_name],
		str(row["id"]),
	)


def _semantic_sort_key(candidate: tuple[str, dict[str, object], int]) -> tuple[float, int, str]:
	table_name, row, channel_rank = candidate
	distance = row.get("_distance")
	return (
		float(distance) if isinstance(distance, int | float) else float(channel_rank),
		TABLE_PRIORITY[table_name],
		str(row["id"]),
	)


def _string_values(value: object) -> set[str]:
	if isinstance(value, str) and value:
		return {value}
	if isinstance(value, list | tuple):
		return {item for item in value if isinstance(item, str) and item}
	return set()


def _record_module(record: dict[str, object]) -> str | None:
	for key in ("module", "module_id"):
		value = record.get(key)
		if isinstance(value, str) and value:
			return value
	path = record.get("path")
	if not isinstance(path, str):
		return None
	parts = Path(path).as_posix().split("/")
	try:
		return parts[parts.index("modules") + 1]
	except (ValueError, IndexError):
		return None


def _context_score(
	table_name: str,
	row_id: str,
	record: dict[str, object],
	context: SearchContext | None,
) -> tuple[float, str | None]:
	if context is None:
		return 0.0, None
	boost = 0.0
	reasons: list[str] = []
	record_id = record.get("id")
	if context.record_id and context.record_id in (row_id, record_id):
		boost += 0.006
		reasons.append("selected record")
	type_path = record.get("type_path")
	if context.type_path and isinstance(type_path, str):
		if type_path == context.type_path:
			boost += 0.006
			reasons.append("same type path")
		elif type_path.startswith(context.type_path + "/") or context.type_path.startswith(type_path + "/"):
			boost += 0.003
			reasons.append("related type path")
	context_groups = set(context.groups)
	record_groups = set()
	for key in ("group", "groups", "group_ids", "group_labels"):
		record_groups.update(_string_values(record.get(key)))
	if context_groups & record_groups:
		boost += 0.0025
		reasons.append("shared group")
	if context.module and _record_module(record) == context.module:
		boost += 0.0025
		reasons.append("same module")
	if context.tool and TABLE_TOOL[table_name] == context.tool:
		boost += 0.0005
		reasons.append("same tool")
	if not reasons:
		return 0.0, None
	return min(boost, CONTEXT_BOOST_MAX), ", ".join(reasons)


def _navigation(table_name: str, row_id: str, record: dict[str, object]) -> dict[str, object]:
	tool = TABLE_TOOL[table_name]
	type_path = record.get("type_path")
	return {
		"tool": tool,
		"route": TOOL_ROUTE[tool],
		"record_kind": TABLE_RECORD_KIND[table_name],
		"record_id": str(record.get("id") or row_id),
		"type_path": type_path if isinstance(type_path, str) else None,
	}


def _result_sort_key(result: dict[str, object]) -> tuple[float, int, str]:
	score = result["score"]
	if not isinstance(score, int | float):
		raise ValueError("Search result score must be numeric.")
	return -float(score), TABLE_PRIORITY[str(result["table"])], str(result["id"])


def search(
	repo_root: Path,
	query: str,
	*,
	tables: list[str] | None = None,
	limit: int = 20,
	context: SearchContext | None = None,
) -> SearchReport:
	"""Globally rank hybrid search candidates, with a bounded selected-context boost."""
	table_names = tables or list(TABLE_SCHEMAS)
	unknown = set(table_names) - set(TABLE_SCHEMAS)
	if unknown:
		raise ValueError(f"Unknown search table(s): {', '.join(sorted(unknown))}.")
	semantic_status = embedding_status()
	semantic_tables = [name for name in table_names if name not in KEYWORD_ONLY_TABLES]
	semantic_enabled = semantic_status.available and bool(semantic_tables)
	semantic_mode = "hybrid" if semantic_enabled else "keyword-only"
	semantic_reason = (
		semantic_status.reason
		if semantic_tables
		else "Selected tables use keyword search."
	)
	if not query.strip():
		return SearchReport((), semantic_mode, semantic_status.model_id, semantic_reason)

	query_text = query.strip()
	query_vector = embed_texts([query_text])[0] if semantic_enabled else None
	candidate_limit = max(20, min(limit * 4, 200))
	keyword_candidates: list[tuple[str, dict[str, object], int]] = []
	semantic_candidates: list[tuple[str, dict[str, object], int]] = []
	rows_by_key: dict[tuple[str, str], dict[str, object]] = {}
	for table_name in table_names:
		keyword_rows, semantic_rows = _search_table_channels(
			repo_root,
			table_name,
			query_text,
			candidate_limit,
			query_vector,
		)
		for channel_rank, row in enumerate(keyword_rows, start=1):
			keyword_candidates.append((table_name, row, channel_rank))
			rows_by_key[_candidate_key(table_name, row)] = row
		for channel_rank, row in enumerate(semantic_rows, start=1):
			semantic_candidates.append((table_name, row, channel_rank))
			rows_by_key[_candidate_key(table_name, row)] = row

	keyword_candidates.sort(key=_keyword_sort_key)
	semantic_candidates.sort(key=_semantic_sort_key)
	keyword_ranks = {
		_candidate_key(table_name, row): rank
		for rank, (table_name, row, _channel_rank) in enumerate(keyword_candidates, start=1)
	}
	semantic_ranks = {
		_candidate_key(table_name, row): rank
		for rank, (table_name, row, _channel_rank) in enumerate(semantic_candidates, start=1)
	}

	results: list[dict[str, object]] = []
	for (table_name, row_id), row in rows_by_key.items():
		key = (table_name, row_id)
		keyword_rrf = 1.0 / (RRF_K + keyword_ranks[key]) if key in keyword_ranks else 0.0
		semantic_rrf = 1.0 / (RRF_K + semantic_ranks[key]) if key in semantic_ranks else 0.0
		record = decode(row)
		context_boost, context_reason = _context_score(table_name, row_id, record, context)
		final_score = keyword_rrf + semantic_rrf + context_boost
		results.append({
			"table": table_name,
			"score": final_score,
			"id": row_id,
			"record": record,
			"scores": {
				"keyword_rrf": keyword_rrf,
				"semantic_rrf": semantic_rrf,
				"context_boost": context_boost,
				"final": final_score,
			},
			"context_reason": context_reason,
			"navigation": _navigation(table_name, row_id, record),
		})
	results.sort(key=_result_sort_key)
	return SearchReport(tuple(results[:limit]), semantic_mode, semantic_status.model_id, semantic_reason)

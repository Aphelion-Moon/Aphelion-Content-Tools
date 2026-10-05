from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from tools.lore_editor.reconcile import reconcile_projection
from webapp.application_search import search_application
from webapp.git_adapter import workspace_revision
from webapp.store.health import store_health
from webapp.store.search import SearchContext, SearchReport

from ..deps import AppContext, context
from ..models import SearchRequest, SearchResponse, SelectedSearchContext, StoreHealth, WorkspaceRevisionResponse
from .definitions import Service

router = APIRouter(prefix="/api", tags=["store"])

Ctx = Annotated[AppContext, Depends(context)]


@router.get("/store/health", response_model=StoreHealth)
def read_store_health(ctx: Ctx) -> object:
	return store_health(ctx.repo_root, ctx.game_repo_root)


@router.get("/workspace/revision", response_model=WorkspaceRevisionResponse | None)
def read_workspace_revision(ctx: Ctx) -> object:
	try:
		return asdict(workspace_revision(ctx.repo_root, ctx.game_repo_root))
	except (OSError, ValueError):
		return None


@router.post("/store/reconcile")
def reconcile_store(ctx: Ctx) -> object:
	result = reconcile_projection(ctx.repo_root)
	return {
		"counts": result.counts,
		"content_revision": result.content_revision,
		"projection_revision": asdict(result.projection_revision),
	}


@router.get("/search", response_model=SearchResponse)
def hybrid_search(
	ctx: Ctx,
	editor: Service,
	q: Annotated[str, Query(description="Query text.")] = "",
	tables: Annotated[str, Query(description="Comma-separated table names. Empty searches every table.")] = "",
	limit: Annotated[int, Query(ge=1, le=100)] = 20,
	context_tool: str | None = None,
	context_kind: str | None = None,
	context_id: str | None = None,
	context_type_path: str | None = None,
	context_group: Annotated[list[str] | None, Query()] = None,
	context_module: str | None = None,
) -> object:
	"""Hybrid keyword + semantic search across the shared store.

	Runs BM25 full-text and vector-similarity searches per table and merges them with reciprocal rank
	fusion. This spans all ten tables -- catalog targets, overrides, groups, reviews, assignments, graph
	nodes and edges, unresolved markers, manifests, and references -- which is what makes it the app's
	cross-tool lookup rather than any single tool's search.
	"""
	requested = [name for name in tables.split(",") if name] or None
	selected_context = SelectedSearchContext(
		tool=context_tool,
		record_kind=context_kind,
		record_id=context_id,
		type_path=context_type_path,
		groups=context_group or [],
		module=context_module,
	)
	context_value = selected_context if any((
		context_tool,
		context_kind,
		context_id,
		context_type_path,
		context_group,
		context_module,
	)) else None
	return _search_response(search_application(ctx.repo_root, editor.catalogs, q, tables=requested, limit=limit, context=_context(context_value)))


@router.post("/search", response_model=SearchResponse)
def contextual_search(payload: SearchRequest, ctx: Ctx, editor: Service) -> object:
	"""Typed contextual search used by the SPA; scope filters are always explicit."""
	tables = payload.scope.tables or None if payload.scope is not None else None
	return _search_response(
		search_application(
			ctx.repo_root,
			editor.catalogs,
			payload.query,
			tables=tables,
			limit=payload.limit,
			context=_context(payload.selected_context),
		)
	)


def _context(value: SelectedSearchContext | None) -> SearchContext | None:
	if value is None:
		return None
	return SearchContext(
		tool=value.tool,
		record_kind=value.record_kind,
		record_id=value.record_id,
		type_path=value.type_path,
		groups=tuple(value.groups),
		module=value.module,
	)


def _search_response(report: SearchReport) -> dict[str, object]:
	return {
		"results": report.results,
		"semantic_search": {
			"mode": report.semantic_mode,
			"model_id": report.semantic_model_id,
			"reason": report.semantic_reason,
		},
	}

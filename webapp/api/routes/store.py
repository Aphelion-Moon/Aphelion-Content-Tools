from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from webapp.store.health import store_health
from webapp.store.search import search

from ..deps import AppContext, context
from ..models import SearchResponse, StoreHealth

router = APIRouter(prefix="/api", tags=["store"])

Ctx = Annotated[AppContext, Depends(context)]


@router.get("/store/health", response_model=StoreHealth)
def read_store_health(ctx: Ctx) -> object:
	return store_health(ctx.repo_root)


@router.get("/search", response_model=SearchResponse)
def hybrid_search(
	ctx: Ctx,
	q: Annotated[str, Query(description="Query text.")] = "",
	tables: Annotated[str, Query(description="Comma-separated table names. Empty searches every table.")] = "",
	limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> object:
	"""Hybrid keyword + semantic search across the shared store.

	Runs BM25 full-text and vector-similarity searches per table and merges them with reciprocal rank
	fusion. This spans all ten tables -- catalog targets, overrides, groups, reviews, assignments, graph
	nodes and edges, unresolved markers, manifests, and references -- which is what makes it the app's
	cross-tool lookup rather than any single tool's search.
	"""
	requested = [name for name in tables.split(",") if name] or None
	return {"results": search(ctx.repo_root, q, tables=requested, limit=limit)}

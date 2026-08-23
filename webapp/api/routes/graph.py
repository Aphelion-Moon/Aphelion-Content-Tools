from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from tools.content_graph.graph import read_graph_cache
from tools.content_graph.marker_edit import apply_marker_label_edit
from tools.content_graph.queries import edits_for_core_file, modules_missing_readme, unresolved_markers

from ..deps import AppContext, context
from ..models import (
	GraphEditsResponse,
	GraphModulesResponse,
	GraphResponse,
	GraphStatusResponse,
	GraphUnresolvedResponse,
	MarkerEditRequest,
	MarkerEditResponse,
)

router = APIRouter(prefix="/api/graph", tags=["content-graph"])

Ctx = Annotated[AppContext, Depends(context)]


@router.get("", response_model=GraphResponse, response_model_exclude_none=True)
def read_graph(ctx: Ctx) -> object:
	"""The cached content graph. `scanned: false` means no scan has run yet -- not an error."""
	cached = read_graph_cache(ctx.repo_root)
	if cached is None:
		return {"scanned": False, "graph": None, "manifest": None}
	graph, manifest = cached
	return {"scanned": True, "graph": graph, "manifest": manifest.to_dict()}


@router.get("/status", response_model=GraphStatusResponse)
def read_graph_status(ctx: Ctx) -> object:
	cached = read_graph_cache(ctx.repo_root)
	if cached is None:
		return {"scanned": False, "manifest": None}
	_graph, manifest = cached
	return {"scanned": True, "manifest": manifest.to_dict()}


@router.get("/edits", response_model=GraphEditsResponse)
def read_edits(ctx: Ctx, core_file: Annotated[str, Query(min_length=1)]) -> object:
	cached = read_graph_cache(ctx.repo_root)
	if cached is None:
		return {"scanned": False, "edits": []}
	graph, _manifest = cached
	return {"scanned": True, "edits": edits_for_core_file(graph, core_file)}


@router.get("/modules", response_model=GraphModulesResponse)
def read_modules(ctx: Ctx, missing_readme: bool = False) -> object:
	cached = read_graph_cache(ctx.repo_root)
	if cached is None:
		return {"scanned": False, "modules": []}
	graph, _manifest = cached
	modules = (
		modules_missing_readme(graph)
		if missing_readme
		else [node for node in graph["nodes"] if node.get("kind") == "module"]
	)
	return {"scanned": True, "modules": modules}


@router.get("/unresolved", response_model=GraphUnresolvedResponse)
def read_unresolved(ctx: Ctx) -> object:
	"""Markers whose module attribution could not be confirmed against a real module directory."""
	cached = read_graph_cache(ctx.repo_root)
	if cached is None:
		return {"scanned": False, "unresolved_markers": []}
	graph, _manifest = cached
	return {"scanned": True, "unresolved_markers": unresolved_markers(graph)}


@router.post("/markers/edit", response_model=MarkerEditResponse)
def edit_marker(payload: MarkerEditRequest, ctx: Ctx) -> object:
	"""Rewrite one marker label in a game-repository core file.

	`expected_line` is checked against the file's current content first, so an edit computed against a
	stale scan fails loudly instead of overwriting whatever now occupies that line number.
	"""
	apply_marker_label_edit(
		ctx.game_repo_root,
		payload.core_file,
		payload.line_number,
		payload.expected_line,
		payload.new_label,
	)
	return {"edited": True, "core_file": payload.core_file, "line_number": payload.line_number}

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from webapp.tool_registry import load_tool_registry
from webapp.tooling import get_tool_run, list_active_runs, list_tools, start_tool, stop_tool

from ..deps import AppContext, context
from ..errors import NotFound
from ..models import ActiveRunsResponse, ToolListResponse, ToolRun

router = APIRouter(prefix="/api/tools", tags=["tools"])

Ctx = Annotated[AppContext, Depends(context)]


def _labels() -> dict[str, str]:
	return {tool["id"]: tool["label"] for tool in list_tools(load_tool_registry())}


@router.get("", response_model=ToolListResponse)
def list_registered_tools() -> object:
	"""Every tool's background jobs, combined from each tool's own ToolDefinition registry."""
	return {"tools": list_tools(load_tool_registry())}


@router.get("/active", response_model=ActiveRunsResponse)
def list_active(ctx: Ctx) -> object:
	labels = _labels()
	runs = [
		{**run, "tool_label": labels.get(run["tool_id"], run["tool_id"])}
		for run in list_active_runs(ctx.repo_root)
	]
	return {"active_runs": runs}


@router.get("/runs/{run_id}", response_model=ToolRun)
def read_run(run_id: str) -> object:
	try:
		return get_tool_run(run_id)
	except ValueError as exc:
		# An unknown run id is a missing resource, not malformed input.
		raise NotFound(str(exc)) from exc


@router.post("/runs/{run_id}/stop", response_model=ToolRun)
def stop_run(run_id: str) -> object:
	try:
		return stop_tool(run_id)
	except ValueError as exc:
		raise NotFound(str(exc)) from exc


@router.post("/{tool_id}", response_model=ToolRun)
def start_run(tool_id: str, ctx: Ctx) -> object:
	return start_tool(ctx.repo_root, load_tool_registry(), tool_id, game_repo_root=ctx.game_repo_root)

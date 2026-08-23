from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from tools.lore_editor.export import apply_export, prepare_export
from webapp.git_adapter import open_in_github_desktop

from ..deps import AppContext, context
from ..errors import BadRequest
from ..models import ApplyExportRequest, ApplyExportResponse, ExportStagesResponse, PrepareExportResponse

router = APIRouter(prefix="/api/export", tags=["export"])

Ctx = Annotated[AppContext, Depends(context)]


def _stage_path(ctx: AppContext, stage_name: str) -> Path:
	"""Resolve a stage name to a directory, refusing anything outside the staging root.

	The name arrives from the client, so absolute paths and traversal are rejected explicitly rather
	than trusted -- this resolves under the staging root and verifies containment after resolution.
	"""
	if not stage_name or Path(stage_name).is_absolute():
		raise BadRequest("Export stage must be a non-empty repository-relative path.")
	stage_root = ctx.export_stage_root
	stage_path = (stage_root / Path(stage_name)).resolve()
	if not stage_path.is_relative_to(stage_root) or not stage_path.is_dir():
		raise BadRequest("Export stage is not inside the local staging directory.")
	return stage_path


@router.get("/stages", response_model=ExportStagesResponse)
def read_stages(ctx: Ctx) -> object:
	stage_root = ctx.export_stage_root
	stages: list[dict[str, object]] = []
	if stage_root.is_dir():
		for manifest_path in sorted(stage_root.glob("*/manifest.json"), key=lambda path: path.parent.name):
			try:
				manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
			except (OSError, json.JSONDecodeError):
				# One unreadable stage should not hide every other prepared stage from the picker.
				continue
			stages.append({"stage": manifest_path.parent.name, "manifest": manifest})
	return {"stages": stages}


@router.post("/prepare", response_model=PrepareExportResponse)
def post_prepare(ctx: Ctx) -> object:
	"""Build a staged export outside the game checkout. Always safe -- never writes to Meridian-Rift."""
	stage_root = ctx.export_stage_root
	prepared = prepare_export(ctx.repo_root, ctx.game_repo_root, stage_root)
	return {
		"prepared": True,
		"stage": prepared.directory.resolve().relative_to(stage_root).as_posix(),
		"artifact": prepared.artifact_path.resolve().relative_to(prepared.directory.resolve()).as_posix(),
		"manifest": prepared.manifest.to_dict(),
	}


@router.post("/apply", response_model=ApplyExportResponse)
def post_apply(payload: ApplyExportRequest, ctx: Ctx) -> object:
	"""Write a prepared stage into the game checkout, then open GitHub Desktop to review the diff.

	A dirty checkout, changed revision, or unexpected artifact hash is always refused by apply_export.
	"""
	artifact_path = apply_export(
		_stage_path(ctx, payload.stage),
		ctx.game_repo_root,
	)
	opened = False
	desktop_error: str | None = None
	try:
		open_in_github_desktop(ctx.game_repo_root)
		opened = True
	except (OSError, ValueError) as exc:
		# The export itself succeeded; failing to launch GitHub Desktop is reported, not raised, so the
		# user is not told the apply failed when it did not.
		desktop_error = str(exc)
	return {
		"applied": True,
		"artifact": artifact_path.resolve().relative_to(ctx.game_repo_root.resolve()).as_posix(),
		"opened_in_github_desktop": opened,
		"github_desktop_error": desktop_error,
	}

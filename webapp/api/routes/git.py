from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from webapp.git_adapter import (
	create_branch,
	git_diff,
	github_blob_url,
	line_history,
	list_branches,
	open_file_in_default_app,
	open_in_github_desktop,
	repository_status,
	reveal_file_in_file_explorer,
	stage_and_commit,
	switch_branch,
)

from ..deps import AppContext, context
from ..models import (
	BranchListResponse,
	BranchRequest,
	BranchResponse,
	CommitRequest,
	CommitResponse,
	DiffResponse,
	GithubUrlResponse,
	MarkerHistoryResponse,
	OpenFileRequest,
	OpenFileResponse,
	OpenRequest,
	OpenResponse,
	RepositoryName,
	RepositoryStatus,
)

router = APIRouter(prefix="/api/git", tags=["git"])

Ctx = Annotated[AppContext, Depends(context)]
Repo = Annotated[RepositoryName, Query(description="Which checkout: this tool's own, or the game repository.")]


@router.get("/status", response_model=RepositoryStatus)
def read_status(ctx: Ctx, repository: Repo = "tool") -> object:
	status = repository_status(ctx.repository(repository))
	return asdict(status) | {"conflicted": status.conflicted}


@router.get("/branches", response_model=BranchListResponse)
def read_branches(ctx: Ctx, repository: Repo = "tool") -> object:
	return {"repository": repository, "branches": list_branches(ctx.repository(repository))}


@router.get("/diff", response_model=DiffResponse)
def read_diff(ctx: Ctx, path: Annotated[str, Query(min_length=1)], repository: Repo = "tool") -> object:
	return {"diff": git_diff(ctx.repository(repository), path)}


@router.get("/github-url", response_model=GithubUrlResponse)
def read_github_url(ctx: Ctx, path: Annotated[str, Query(min_length=1)], repository: Repo = "tool") -> object:
	return {"url": github_blob_url(ctx.repository(repository), path)}


@router.get("/marker-history", response_model=MarkerHistoryResponse)
def read_marker_history(
	ctx: Ctx,
	core_file: Annotated[str, Query(min_length=1)],
	line: Annotated[int, Query(ge=1)],
) -> object:
	"""Commit history for one line of a game-repository core file, behind an edit marker."""
	return {"commits": line_history(ctx.game_repo_root, core_file, line)}


@router.post("/branch", response_model=BranchResponse)
def post_branch(payload: BranchRequest, ctx: Ctx) -> object:
	create_branch(ctx.repository(payload.repository), payload.name)
	return {"repository": payload.repository, "branch": payload.name}


@router.post("/switch-branch", response_model=BranchResponse)
def post_switch_branch(payload: BranchRequest, ctx: Ctx) -> object:
	switch_branch(ctx.repository(payload.repository), payload.name)
	return {"repository": payload.repository, "branch": payload.name}


@router.post("/commit", response_model=CommitResponse)
def post_commit(payload: CommitRequest, ctx: Ctx) -> object:
	"""Stage the given paths and commit them locally.

	Local commits only, by design: pushes, pull requests, and merge-conflict resolution stay in GitHub
	Desktop, which owns authentication.
	"""
	commit_sha = stage_and_commit(ctx.repository(payload.repository), tuple(payload.paths), payload.message)
	return {"repository": payload.repository, "commit": commit_sha}


@router.post("/open", response_model=OpenResponse)
def post_open(payload: OpenRequest, ctx: Ctx) -> object:
	open_in_github_desktop(ctx.repository(payload.repository))
	return {"repository": payload.repository, "opened": True}


@router.post("/open-file", response_model=OpenFileResponse)
def post_open_file(payload: OpenFileRequest, ctx: Ctx) -> object:
	action = open_file_in_default_app if payload.target == "editor" else reveal_file_in_file_explorer
	action(ctx.repository(payload.repository), payload.path)
	return {"repository": payload.repository, "path": payload.path, "opened": True}

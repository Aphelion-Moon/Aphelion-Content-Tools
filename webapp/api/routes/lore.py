from __future__ import annotations

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from tools.lore_editor.api import (
	catalog_response,
	create_entry,
	delete_entry,
	find_type_definition,
	generate_output,
	groups_response,
	icon_files_response,
	icon_states_response,
	list_entity_files,
	list_entries_response,
	list_icon_choices,
	list_review_response,
	save_entry,
	save_group_response,
	save_review_response,
	validate_entries,
	validate_entry,
)
from tools.lore_editor.icon_preview import IconPreviewNotFound, render_icon_preview

from ..deps import AppContext, context
from ..errors import BadRequest, NotFound
from ..models import DefinitionResponse, DeleteEntryRequest, SaveEntryRequest, SaveEntryResponse, ValidateRequest

router = APIRouter(prefix="/api", tags=["lore-editor"])

Ctx = Annotated[AppContext, Depends(context)]


@router.get("/catalog")
def read_catalog(ctx: Ctx) -> object:
	return catalog_response(ctx.repo_root)


@router.get("/entries")
def read_entries(ctx: Ctx, q: str = "", category: str = "") -> object:
	return list_entries_response(ctx.repo_root, query=q, category=category, asset_root=ctx.game_repo_root)


@router.get("/review")
def read_review(
	ctx: Ctx,
	q: str = "",
	category: str = "",
	group: Annotated[list[str] | None, Query()] = None,
	status: Annotated[list[str] | None, Query()] = None,
	sort: str = "name",
	include_directional: bool = False,
	include_redundant: bool = False,
	offset: Annotated[int, Query(ge=0)] = 0,
	limit: Annotated[int | None, Query(ge=1)] = None,
) -> object:
	"""The catalog review feed.

	Directional subtypes and redundant inherited descriptions stay hidden unless explicitly requested --
	they are a large, noisy tail that a writer opts into rather than wades through.
	"""
	return list_review_response(
		ctx.repo_root,
		query=q,
		category=category,
		groups=tuple(group or ()),
		statuses=tuple(status or ()),
		sort=sort,
		include_directional=include_directional,
		include_redundant=include_redundant,
		offset=offset,
		limit=limit,
		asset_root=ctx.game_repo_root,
	)


@router.get("/groups")
def read_groups(ctx: Ctx) -> object:
	return groups_response(ctx.repo_root)


@router.post("/groups")
def post_group(payload: dict[str, object], ctx: Ctx) -> object:
	return save_group_response(ctx.repo_root, payload)


@router.put("/groups/{group_id}")
def put_group(group_id: str, payload: dict[str, object], ctx: Ctx) -> object:
	return save_group_response(ctx.repo_root, {**payload, "id": group_id})


@router.put("/reviews/{type_path:path}")
def put_review(type_path: str, payload: dict[str, object], ctx: Ctx) -> object:
	return save_review_response(ctx.repo_root, type_path, payload)


@router.get("/entity-files")
def read_entity_files(ctx: Ctx) -> object:
	return {"files": list_entity_files(ctx.repo_root)}


@router.get("/lore/definition", response_model=DefinitionResponse)
def read_definition(ctx: Ctx, type_path: Annotated[str, Query(min_length=1)]) -> object:
	definition = find_type_definition(ctx.game_repo_root, type_path)
	return {
		"path": definition["path"] if definition else None,
		"line": definition["line"] if definition else None,
	}


@router.post("/entries", response_model=SaveEntryResponse)
def post_entry(payload: SaveEntryRequest, ctx: Ctx) -> object:
	created = create_entry(
		ctx.repo_root,
		source_file=payload.source_file,
		entry=payload.entry,
		asset_root=ctx.game_repo_root,
	)
	return {"saved": True, "created": True, "entry": created, "issues": []}


@router.put("/entries/{entry_id}", response_model=SaveEntryResponse)
def put_entry(entry_id: str, payload: SaveEntryRequest, ctx: Ctx) -> object:
	if "/" in entry_id:
		raise BadRequest("A single lore entry id is required.")
	saved = save_entry(
		ctx.repo_root,
		entry_id=entry_id,
		source_file=payload.source_file,
		entry=payload.entry,
		asset_root=ctx.game_repo_root,
	)
	return {"saved": True, "entry": saved, "issues": []}


@router.delete("/entries/{entry_id}")
def remove_entry(entry_id: str, payload: DeleteEntryRequest, ctx: Ctx) -> object:
	if "/" in entry_id:
		raise BadRequest("A single lore entry id is required.")
	return delete_entry(ctx.repo_root, entry_id=entry_id, source_file=payload.source_file)


@router.post("/validate")
def post_validate(payload: ValidateRequest, ctx: Ctx) -> object:
	if payload.entries is not None:
		return validate_entries(
			ctx.repo_root,
			entries=payload.entries,
			source_file=payload.source_file,
			asset_root=ctx.game_repo_root,
		)
	if payload.source_file is None:
		raise BadRequest("Request must contain a string source_file.")
	return validate_entry(
		ctx.repo_root,
		source_file=payload.source_file,
		entry=payload.entry,
		asset_root=ctx.game_repo_root,
	)


@router.post("/generate")
def post_generate(ctx: Ctx) -> object:
	"""Build and validate the runtime DM artifact. Never touches the game checkout, so always safe to run."""
	return generate_output(ctx.repo_root)


# ---- Icons ----------------------------------------------------------------------------------------


@router.get("/icons")
def read_icons(ctx: Ctx) -> object:
	return {"icons": list_icon_choices(ctx.repo_root, asset_root=ctx.game_repo_root)}


@router.get("/icon-files")
def read_icon_files(ctx: Ctx) -> object:
	return icon_files_response(ctx.repo_root, asset_root=ctx.game_repo_root)


@router.get("/icon-states")
def read_icon_states(ctx: Ctx, file: Annotated[str, Query(min_length=1)]) -> object:
	return icon_states_response(ctx.repo_root, file, asset_root=ctx.game_repo_root)


@router.get("/icon", response_class=Response)
def read_icon_preview(
	ctx: Ctx,
	file: Annotated[str, Query(min_length=1)],
	state: Annotated[str, Query(min_length=1)],
) -> Response:
	"""Render one DMI icon state as a PNG.

	A path outside the selected game checkout, or a state that does not exist in the file, is a clear
	404 -- never a silently substituted placeholder image from an unrelated entry.
	"""
	try:
		png = render_icon_preview(ctx.game_repo_root, file, state)
	except IconPreviewNotFound as exc:
		raise NotFound(str(exc)) from exc
	return Response(content=png, media_type="image/png", status_code=HTTPStatus.OK)

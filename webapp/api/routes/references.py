from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from webapp.references import add_reference, list_references, remove_reference

from ..deps import AppContext, context
from ..errors import BadRequest
from ..models import AddReferenceRequest, DeleteResponse, Reference, ReferenceListResponse

router = APIRouter(prefix="/api/references", tags=["references"])

Ctx = Annotated[AppContext, Depends(context)]


@router.get("", response_model=ReferenceListResponse)
def read_references(ctx: Ctx) -> object:
	return {"references": list_references(ctx.repo_root)}


@router.post("", response_model=Reference)
def post_reference(payload: AddReferenceRequest, ctx: Ctx) -> object:
	# The domain function does its own validation too; the model catches malformed input earlier and
	# produces a field-level message instead of a generic one.
	return add_reference(ctx.repo_root, payload.model_dump(exclude_none=True))


@router.delete("/{reference_id}", response_model=DeleteResponse)
def delete_reference(reference_id: str, ctx: Ctx) -> object:
	if "/" in reference_id:
		raise BadRequest("A single reference id is required.")
	remove_reference(ctx.repo_root, reference_id)
	return {"deleted": True, "id": reference_id}

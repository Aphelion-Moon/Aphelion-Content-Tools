from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, Response

from tools.definition_editor.inspection import source_excerpt
from tools.definition_editor.items import item_image, item_preview
from tools.definition_editor.models import (
	CatalogStatus,
	Definition,
	DefinitionConstant,
	DefinitionList,
	DefinitionReference,
	DraftAction,
	DraftList,
	EditorApplyRequest,
	EditorKind,
	EditorRun,
	EditorStage,
	ItemPreview,
	PreviewRequest,
	RebaseProposal,
	SavedDraft,
	SaveDraftRequest,
	SourceExcerpt,
)
from tools.definition_editor.query import classified, query_definitions
from tools.definition_editor.service import EditorService
from webapp.capabilities import CAPABILITIES, CapabilityStatus

from ..models import GameChangeReceipt

router = APIRouter(prefix='/api/definitions', tags=['definition-editors'])


def service(request: Request) -> EditorService:
	return request.app.state.definition_editors


Service = Annotated[EditorService, Depends(service)]


@router.get('/capabilities', response_model=list[CapabilityStatus])
def capabilities(editor: Service) -> list[CapabilityStatus]:
	status = editor.status()
	return [CapabilityStatus(capability=item, catalog_available=status.current, native_available=status.byond_available and status.analyzer_available, reason=status.reason) if item.id in ('job-editor', 'outfit-editor') else CapabilityStatus(capability=item) for item in CAPABILITIES]


@router.get('/status', response_model=CatalogStatus)
def status(editor: Service) -> CatalogStatus:
	return editor.status()


@router.post('/index', response_model=EditorRun)
def index(editor: Service) -> EditorRun:
	return editor.index()


@router.get('/catalog', response_model=DefinitionList)
def definitions(editor: Service, kind: str = 'outfit', query: str = '', subtype_of: str | None = None, offset: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=200)] = 80) -> DefinitionList:
	catalog_id, catalog, _ = editor.catalogs.read()
	matches = query_definitions(catalog, kind, query, subtype_of)
	# List results deliberately omit heavy source/procedure payloads; the inspector
	# resolves one full definition against the same generation.
	return DefinitionList(catalog_id=catalog_id, definitions=[classified(item, catalog).model_copy(update={'procedures': [], 'references': []}) for item in matches[offset:offset + limit]], total=len(matches))


@router.get('/definition', response_model=Definition)
def definition(editor: Service, type_path: str, catalog_id: str) -> Definition:
	current_id, catalog, _ = editor.catalogs.read()
	if current_id != catalog_id:
		raise ValueError('Selected definition belongs to a stale catalog.')
	for item in catalog.definitions:
		if item.type_path == type_path:
			return classified(item, catalog)
	raise ValueError('Definition no longer exists in this snapshot.')


@router.get('/constants', response_model=list[DefinitionConstant])
def constants(editor: Service, catalog_id: str, query: str = '') -> list[DefinitionConstant]:
	current_id, catalog, _ = editor.catalogs.read()
	if current_id != catalog_id:
		raise ValueError('Constants belong to a different source snapshot.')
	return [item for item in catalog.constants if query.casefold() in item.name.casefold()][:300]


@router.get('/item-preview', response_model=ItemPreview)
def item_metadata(editor: Service, type_path: str, catalog_id: str, slot: str | None = None) -> ItemPreview:
	return item_preview(editor.game, definition(editor, type_path, catalog_id), catalog_id, slot=slot, constants=editor.catalogs.read()[1].constants)


@router.get('/source', response_model=SourceExcerpt)
def source(editor: Service, type_path: str, catalog_id: str, member: str | None = None) -> SourceExcerpt:
	return source_excerpt(editor.game, definition(editor, type_path, catalog_id), catalog_id, member)


@router.get('/item-image')
def item_png(editor: Service, type_path: str, catalog_id: str, asset_hash: str, direction: int = 2, frame: Annotated[int, Query(ge=0)] = 0) -> Response:
	metadata = item_preview(editor.game, definition(editor, type_path, catalog_id), catalog_id)
	return Response(item_image(editor.game, metadata, asset_hash, direction, frame), media_type='image/png', headers={'Cache-Control': 'no-store'})


@router.get('/thumbnail')
def thumbnail(editor: Service, type_path: str, catalog_id: str) -> Response:
	metadata = item_preview(editor.game, definition(editor, type_path, catalog_id), catalog_id)
	return Response(item_image(editor.game, metadata, metadata.asset_sha256, 2, 0), media_type='image/png', headers={'Cache-Control': 'no-store', 'X-Catalog-ID': catalog_id, 'X-Asset-SHA256': metadata.asset_sha256})


@router.get('/drafts', response_model=DraftList)
def drafts(editor: Service, kind: EditorKind) -> DraftList:
	return DraftList(drafts=editor.drafts.list(kind))


@router.get('/references', response_model=list[DefinitionReference])
def references(editor: Service, target_type: str, catalog_id: str) -> list[DefinitionReference]:
	current_id, catalog, _ = editor.catalogs.read()
	if current_id != catalog_id:
		raise ValueError('Reference selection belongs to a stale catalog.')
	return list({ref.id: ref for item in catalog.definitions for ref in item.references if ref.target_type == target_type}.values())


@router.post('/drafts', response_model=SavedDraft)
def save_draft(payload: SaveDraftRequest, editor: Service) -> SavedDraft:
	return editor.save(payload)


@router.post('/rebase', response_model=RebaseProposal)
def rebase(payload: DraftAction, editor: Service) -> RebaseProposal:
	return editor.rebase(payload)


@router.post('/validate', response_model=EditorRun)
def validate(payload: DraftAction, editor: Service) -> EditorRun:
	return editor.validate(payload)


@router.post('/analyze', response_model=EditorRun)
def analyze(payload: DraftAction, editor: Service) -> EditorRun:
	return editor.validate(payload, compile_game=False)


@router.post('/prepare', response_model=EditorStage)
def prepare(payload: DraftAction, editor: Service) -> EditorStage:
	return editor.prepare(payload)


@router.post('/apply', response_model=GameChangeReceipt)
def apply(payload: EditorApplyRequest, editor: Service) -> dict[str, object]:
	return editor.apply(payload)


@router.post('/preview', response_model=EditorRun)
def preview(payload: PreviewRequest, editor: Service) -> EditorRun:
	return editor.preview(payload)


@router.get('/runs', response_model=list[EditorRun])
def runs(editor: Service) -> list[EditorRun]:
	return editor.runs()


@router.post('/runs/{run_id}/stop', response_model=dict[str, bool])
def stop(run_id: str, editor: Service) -> dict[str, bool]:
	editor.stop(run_id)
	return {'stopping': True}


@router.get('/runs/{run_id}/log', response_model=str)
def run_log(run_id: str, editor: Service) -> str:
	return editor.log(run_id)


@router.get('/runs/{run_id}/images/{image_index}')
def image(run_id: str, image_index: int, editor: Service) -> FileResponse:
	return FileResponse(editor.artifact(run_id, image_index), media_type='image/png')

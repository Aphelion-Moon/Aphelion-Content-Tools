from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

EditorKind = Literal['job', 'outfit']
DefinitionKind = Literal['job', 'outfit', 'id_trim', 'item', 'related']
TypePath = str


def validate_type_path(value: str) -> str:
	import re
	if not re.fullmatch(r'/[A-Za-z_][A-Za-z_0-9]*(?:/[A-Za-z_][A-Za-z_0-9]*)*', value):
		raise ValueError('Invalid DreamMaker type path.')
	return value


class SourceSpan(BaseModel):
	path: str
	start: int = Field(ge=0)
	end: int = Field(ge=0)
	sha256: str = Field(pattern=r'^[a-f0-9]{64}$')

	@model_validator(mode='after')
	def valid(self) -> SourceSpan:
		from pathlib import PurePosixPath
		path = PurePosixPath(self.path)
		if self.end < self.start or path.is_absolute() or '\\' in self.path or ':' in self.path or '..' in path.parts or '.git' in path.parts:
			raise ValueError('Invalid physical source range.')
		return self


class SourceInput(BaseModel):
	path: str
	sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
	encoding: str = 'utf-8'


class FieldOccurrence(BaseModel):
	source: SourceSpan | None = None
	expression: str | None = None
	editable: bool = False


class DefinitionField(BaseModel):
	name: str
	expression: str | None = None
	value: JsonValue = None
	value_known: bool = False
	owner_type: str
	source: SourceSpan | None = None
	editable: bool = False
	occurrences: list[FieldOccurrence] = Field(default_factory=list)
	local: bool = False


class DefinitionProcedure(BaseModel):
	name: str
	owner_type: str
	source: SourceSpan | None = None
	text: str = ''
	editable: bool = False
	occurrences: list[SourceSpan] = Field(default_factory=list)
	local: bool = False
	override_index: int = 0


class DefinitionReference(BaseModel):
	id: str
	target_type: str
	source: SourceSpan
	editable: bool = False
	reason: str | None = None


class Definition(BaseModel):
	type_path: str
	parent_type: str | None = None
	kind: DefinitionKind
	source: SourceSpan | None = None
	fields: list[DefinitionField] = Field(default_factory=list)
	procedures: list[DefinitionProcedure] = Field(default_factory=list)
	references: list[DefinitionReference] = Field(default_factory=list)
	occurrences: list[SourceSpan] = Field(default_factory=list)
	job_category: Literal['station', 'special', 'base', 'unresolved'] | None = None
	player_selectable: bool | None = None


class DefinitionConstant(BaseModel):
	name: str
	expression: str | None = None
	value: JsonValue = None
	value_known: bool = False
	source: SourceSpan | None = None


class AuthoringCatalog(BaseModel):
	schema_version: Literal[1] = 1
	analyzer_version: str
	analyzer_package_sha256: str | None = None
	spacemandmm_revision: str = 'unknown'
	spacemandmm_local_patch_sha256: str = 'unknown'
	environment: str = 'tgstation.dme'
	input_files: list[SourceInput]
	definitions: list[Definition]
	diagnostics: list[str] = Field(default_factory=list)
	constants: list[DefinitionConstant] = Field(default_factory=list)
	configuration: dict[str, JsonValue] = Field(default_factory=dict)


class DefinitionEdit(BaseModel):
	model_config = ConfigDict(extra='forbid')
	kind: Literal['job', 'outfit', 'id_trim']
	operation: Literal['override', 'update', 'create', 'replace']
	source_type: str | None = None
	type_path: str
	parent_type: str | None = None
	target_file: str | None = None
	# Expressions and complete procedure fragments are the single canonical source.
	fields: dict[str, str] = Field(default_factory=dict)
	procedures: dict[str, str] = Field(default_factory=dict)
	reference_ids: list[str] = Field(default_factory=list)
	old_job_selection: Literal['retain', 'retire'] | None = None

	@field_validator('type_path', 'parent_type', 'source_type')
	@classmethod
	def type_path_valid(cls, value: str | None) -> str | None:
		return validate_type_path(value) if value is not None else None

	@model_validator(mode='after')
	def valid_edit(self) -> DefinitionEdit:
		import re

		from .fragments import expression_fragment, procedure_fragment
		for name in (*self.fields, *self.procedures):
			if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', name):
				raise ValueError('Invalid field or procedure name.')
		for source in (*self.fields.values(), *self.procedures.values()):
			if '\0' in source or len(source) > 200_000 or re.search(r'^\s*#', source, re.MULTILINE):
				raise ValueError('Source fragments cannot contain preprocessor directives or NUL bytes.')
		for expression in self.fields.values():
			expression_fragment(expression)
		for name, source in self.procedures.items():
			procedure_fragment(source, self.type_path, name)
		if self.operation == 'replace' and self.kind == 'job' and self.old_job_selection is None:
			raise ValueError('Choose whether the original job remains selectable.')
		return self


class DefinitionDraft(BaseModel):
	model_config = ConfigDict(extra='forbid')
	schema_version: Literal[1] = 1
	id: str = Field(pattern=r'^[a-z0-9][a-z0-9_-]{0,95}$')
	kind: EditorKind
	label: str = Field(default='', max_length=200)
	catalog_id: str = Field(min_length=1, max_length=128)
	edits: list[DefinitionEdit] = Field(min_length=1, max_length=64)
	baseline: list[Definition] = Field(default_factory=list)
	source_hashes: dict[str, str] = Field(default_factory=dict)
	applied_stage_ids: list[str] = Field(default_factory=list)


class SavedDraft(BaseModel):
	draft: DefinitionDraft
	record_hash: str


class SaveDraftRequest(BaseModel):
	draft: DefinitionDraft
	expected_record_hash: str | None = None


class DraftList(BaseModel):
	drafts: list[SavedDraft]


class CatalogStatus(BaseModel):
	catalog_id: str | None = None
	game_revision: str | None = None
	current: bool = False
	analyzer_available: bool = False
	byond_available: bool = False
	reason: str | None = None


class DefinitionList(BaseModel):
	catalog_id: str
	definitions: list[Definition]
	total: int


class DraftAction(BaseModel):
	kind: EditorKind
	id: str
	record_hash: str


class RebaseProposal(BaseModel):
	draft: DefinitionDraft
	expected_record_hash: str
	changes: list[str]


class DefinitionSelection(BaseModel):
	type_path: str
	catalog_id: str
	kind: DefinitionKind


class ItemPreview(BaseModel):
	type_path: str
	catalog_id: str
	file: str
	state: str
	asset_sha256: str
	directions: list[int]
	frames: int
	diagnostics: list[str]


class SourceExcerpt(BaseModel):
	catalog_id: str
	path: str
	sha256: str
	line: int
	text: str


class PreviewRequest(DraftAction):
	mode: Literal['render', 'interactive']
	type_path: str
	species: str | None = None
	body_gender: Literal['male', 'female'] | None = None
	body_type: Literal['male', 'female'] | None = None


class EditorRun(BaseModel):
	id: str
	operation: str
	status: Literal['queued', 'running', 'ready', 'failed', 'cancelled']
	draft_hash: str | None = None
	message: str = ''
	diagnostics: list[str] = Field(default_factory=list)
	images: list[str] = Field(default_factory=list)
	connection_url: str | None = None
	effective: list[Definition] = Field(default_factory=list)
	preview_settings: dict[str, JsonValue] = Field(default_factory=dict)
	equipment: list[dict[str, JsonValue]] = Field(default_factory=list)


class EditorStage(BaseModel):
	stage_id: str
	base_revision: str
	preview: str
	paths: list[str]
	compatibility_report: list[str]


class EditorApplyRequest(DraftAction):
	stage_id: str

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# The single definition of every shape crossing the HTTP boundary.
#
# These models are simultaneously: request validation (replacing hand-rolled `isinstance` ladders),
# response schema, OpenAPI documentation, and -- via `npm run gen:api` -- the TypeScript types the
# frontend compiles against. One definition, so a renamed field breaks the build instead of arriving in
# the UI as `undefined`.
#
# Storage is unchanged: the store still persists records as `raw_json` in LanceDB. What changes is that
# `raw_json` stops being the *interface*; it is decoded into a model at the boundary.

RepositoryName = Literal["tool", "game"]
RecordHash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class ErrorResponse(BaseModel):
	error: str = Field(description="Human-readable message, suitable for display.")
	code: str = Field(description="Stable machine-readable error code; branch on this, not on `error`.")


class RecordConflictResponse(ErrorResponse):
	"""Optimistic-write conflict with all three records needed for a safe comparison UI."""

	record_id: str
	expected_hash: str | None
	current_hash: str | None
	base: dict[str, object] | None
	current: dict[str, object] | None
	proposed: dict[str, object] | None


# ---- Store ----------------------------------------------------------------------------------------


class SemanticSearchHealth(BaseModel):
	mode: Literal["hybrid", "keyword-only"]
	model_id: str
	reason: str | None = None


class ProjectionHealth(BaseModel):
	current: bool
	reason: str | None = None
	path: str
	content_revision: str
	active: dict[str, object] | None = None


class ProjectionWriteState(BaseModel):
	current: bool
	reason: str | None = None
	content_revision: str | None = None


class DatasetHealth(BaseModel):
	kind: str
	required: bool
	state: Literal["current", "stale", "missing", "failed"]
	current: bool
	source_revision: str | None = None
	selected_revision: str | None = None
	schema_version: int | None = None
	content_sha256: str | None = None
	reason: str | None = None


class WorkspaceHealth(BaseModel):
	current: bool
	reason: str | None = None
	selected_game_revision: str | None = None
	datasets: list[DatasetHealth]


class StoreHealth(BaseModel):
	tables: dict[str, int] = Field(description="Row count per table.")
	total_rows: int
	disk_bytes: int
	last_write_time: float | None = Field(
		default=None,
		description="Unix timestamp of the most recent write, from file mtimes. Null if the store is empty.",
	)
	semantic_search: SemanticSearchHealth
	projection: ProjectionHealth
	workspace: WorkspaceHealth


class SelectedSearchContext(BaseModel):
	tool: str | None = None
	record_kind: str | None = None
	record_id: str | None = None
	type_path: str | None = None
	groups: list[str] = Field(default_factory=list)
	module: str | None = None
	catalog_id: str | None = None


class SearchScope(BaseModel):
	tables: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
	query: str = ""
	limit: int = Field(default=20, ge=1, le=100)
	selected_context: SelectedSearchContext | None = None
	scope: SearchScope | None = None


class SearchScoreComponents(BaseModel):
	keyword_rrf: float
	semantic_rrf: float
	context_boost: float
	final: float


class SearchNavigation(BaseModel):
	tool: str
	route: str
	record_kind: str
	record_id: str
	type_path: str | None = None
	catalog_id: str | None = None


class SearchResult(BaseModel):
	table: str
	score: float = Field(description="Global hybrid score after the bounded selected-context boost.")
	id: str
	record: dict[str, object]
	scores: SearchScoreComponents
	context_reason: str | None = None
	navigation: SearchNavigation


class SearchResponse(BaseModel):
	results: list[SearchResult]
	semantic_search: SemanticSearchHealth


# ---- Background tool runs -------------------------------------------------------------------------

RunStatus = Literal["queued", "running", "succeeded", "failed", "stopped"]


class ToolSummary(BaseModel):
	id: str
	label: str
	description: str


class ToolListResponse(BaseModel):
	tools: list[ToolSummary]


class ActiveRun(BaseModel):
	run_id: str
	tool_id: str
	tool_label: str | None = None
	status: RunStatus
	queued_at: float


class ActiveRunsResponse(BaseModel):
	active_runs: list[ActiveRun]


class ToolRun(BaseModel):
	run_id: str
	tool_id: str
	status: RunStatus
	queued_at: float
	exit_code: int | None = None
	output: str = ""
	log_path: str | None = None


# ---- Git ------------------------------------------------------------------------------------------


class OwnedChange(BaseModel):
	path: str
	kind: str
	record_id: str
	summary: str


class RepositoryStatus(BaseModel):
	"""Mirrors webapp.git_adapter.RepositoryStatus, plus its derived `conflicted` flag.

	`changed_files` and `conflict_files` are repository-relative path strings, not objects -- kept that
	way because that is what the adapter produces and what every consumer wants.
	"""

	# Every field is required: this is built from `asdict()` of the adapter's frozen dataclass, so the
	# server always supplies all of them. Giving them defaults would mark them optional in the schema and
	# force every TypeScript consumer to null-check a value that is never absent.
	branch: str
	upstream: str | None
	ahead: int
	behind: int
	dirty: bool
	changed_files: list[str]
	conflict_files: list[str]
	truncated_change_count: int = Field(description="Changes omitted from `changed_files` because the list was capped.")
	conflicted: bool = Field(description="True when conflict_files is non-empty.")
	owned_changes: list[OwnedChange] = Field(default_factory=list)
	unowned_changes: list[str] = Field(default_factory=list)


class BranchListResponse(BaseModel):
	repository: RepositoryName
	branches: list[str]


class DiffResponse(BaseModel):
	diff: str


class GithubUrlResponse(BaseModel):
	url: str | None


class BranchRequest(BaseModel):
	name: str = Field(min_length=1, description="Branch name to create or switch to.")
	repository: RepositoryName = "tool"


class CommitRequest(BaseModel):
	message: str = Field(min_length=1)
	paths: list[str] = Field(description="Repository-relative paths to stage. Empty means nothing is staged.")
	repository: RepositoryName = "tool"


class CommitResponse(BaseModel):
	repository: RepositoryName
	commit: str


class BranchResponse(BaseModel):
	repository: RepositoryName
	branch: str


class OpenRequest(BaseModel):
	repository: RepositoryName = "tool"


class OpenResponse(BaseModel):
	repository: RepositoryName
	opened: bool


class OpenFileRequest(BaseModel):
	path: str = Field(min_length=1)
	target: Literal["editor", "explorer"]
	repository: RepositoryName = "tool"


class OpenFileResponse(BaseModel):
	repository: RepositoryName
	path: str
	opened: bool


class CommitInfo(BaseModel):
	commit: str
	short_commit: str
	author: str
	date: str
	subject: str
	diff: str
	pr_url: str | None = None


class MarkerHistoryResponse(BaseModel):
	commits: list[CommitInfo]


# ---- Content graph --------------------------------------------------------------------------------


GraphNodeKind = Literal["module", "master_file", "core_file", "directory", "file"]
GraphNodeOwner = Literal["nova", "aphelion"]
GraphEdgeRelation = Literal[
	"master_files_mirror",
	"marker_edit",
	"contains",
	"module_reference",
	"core_reference",
]
GraphEditType = Literal["addition", "removal", "change", "unspecified"]


class GraphNodeModel(BaseModel):
	id: str
	kind: GraphNodeKind
	owner: GraphNodeOwner | None = None
	module_id: str | None = None
	path: str | None = None
	name: str | None = None
	core_path: str | None = None
	has_readme: bool | None = None
	marker_count: int | None = None
	file_count: int | None = None
	total_bytes: int | None = None
	size_bytes: int | None = None
	line_count: int | None = None


class GraphEdgeModel(BaseModel):
	source: str
	target: str
	relation: GraphEdgeRelation
	edit_type: GraphEditType | None = None
	attribution: str | None = None
	line_number: int | None = None
	raw_label: str | None = None
	original_text: str | None = None


class UnresolvedMarkerModel(BaseModel):
	core_file: str
	owner: Literal["NOVA", "APHELION"]
	edit_type: GraphEditType
	line_number: int
	source_module_id: str | None = None
	attribution: Literal["exact", "path-derived", "unattributed"]
	raw_label: str
	original_text: str | None = None
	line_text: str


class GraphCountsModel(BaseModel):
	module_count: int
	master_files_count: int
	core_file_count: int
	marker_count: int
	unresolved_marker_count: int
	file_count: int
	directory_count: int
	reference_count: int


class GraphDocumentModel(BaseModel):
	nodes: list[GraphNodeModel]
	edges: list[GraphEdgeModel]
	unresolved_markers: list[UnresolvedMarkerModel]
	counts: GraphCountsModel


class GraphManifestModel(BaseModel):
	format_version: int
	snapshot_sha256: str
	game_repo_revision: str
	generated_at: str
	node_count: int
	edge_count: int
	module_count: int
	master_files_count: int
	marker_count: int
	file_count: int
	directory_count: int
	reference_count: int
	source_sha256: str | None = None
	source_observation: str | None = None


class GraphResponse(BaseModel):
	scanned: bool
	graph: GraphDocumentModel | None = None
	manifest: GraphManifestModel | None = None


class GraphStatusResponse(BaseModel):
	scanned: bool
	manifest: GraphManifestModel | None = None


class GraphEditModel(BaseModel):
	resolved: bool
	source: str | None = None
	target: str | None = None
	relation: GraphEdgeRelation | None = None
	core_file: str | None = None
	owner: str | None = None
	edit_type: GraphEditType | None = None
	line_number: int | None = None
	source_module_id: str | None = None
	attribution: str | None = None
	raw_label: str | None = None
	original_text: str | None = None
	line_text: str | None = None


class GraphEditsResponse(BaseModel):
	scanned: bool
	edits: list[GraphEditModel] = Field(default_factory=list)


class GraphModulesResponse(BaseModel):
	scanned: bool
	modules: list[GraphNodeModel] = Field(default_factory=list)


class GraphUnresolvedResponse(BaseModel):
	scanned: bool
	unresolved_markers: list[UnresolvedMarkerModel] = Field(default_factory=list)


class MarkerEditRequest(BaseModel):
	core_file: str = Field(min_length=1)
	line_number: int = Field(ge=1)
	expected_line: str = Field(description="The line's current content, checked before writing to avoid a stale edit.")
	new_label: str = Field(min_length=1)


class MarkerEditResponse(BaseModel):
	stage_id: str
	base_revision: str
	preview: str
	paths: list[str]


class GameChangeApplyRequest(BaseModel):
	stage_id: str = Field(min_length=1, max_length=128)


class GameChangeReceipt(BaseModel):
	stage_id: str
	base_revision: str
	paths: list[str]
	sha256: dict[str, str]
	refresh_warning: str | None = None


# ---- Lore editor ----------------------------------------------------------------------------------


class ValidationIssueModel(BaseModel):
	path: str
	message: str
	severity: str


class ReviewRecordModel(BaseModel):
	status: Literal["reviewed", "needs-attention"]
	reviewed_by: str
	reviewed_at: str
	notes: str
	record_hash: RecordHash


class ReviewGroupModel(BaseModel):
	id: str
	label: str
	color: str | None = None
	keywords: list[str] = Field(default_factory=list)
	type_path_prefixes: list[str] = Field(default_factory=list)
	keyword_scope: list[str] = Field(default_factory=list)
	record_hash: RecordHash | None = None
	count: int = 0


class ReviewEntryModel(BaseModel):
	id: str
	type_path: str
	name: str | None = None
	description: str | None = None
	special_desc_requirement: str | None = None
	special_desc: str | None = None
	source_file: str | None = None
	category: str
	field_profile: str | None = None
	label: str | None = None
	editable_root: str | None = None
	parent_type: str | None = None
	base_name: str | None = None
	base_description: str | None = None
	icon_metadata: dict[str, object] = Field(default_factory=dict)
	raw: dict[str, object] | None = None
	record_hash: RecordHash | None = None
	approved: bool = False
	has_override: bool = False
	base_status: str
	status: str
	issues: list[ValidationIssueModel] = Field(default_factory=list)
	groups: list[str] = Field(default_factory=list)
	group_labels: list[str] = Field(default_factory=list)
	group_match_reasons: dict[str, list[str]] = Field(default_factory=dict)
	review: ReviewRecordModel | None = None
	directional: bool = False
	redundant: bool = False
	suppression_reasons: list[str] = Field(default_factory=list)


class ReviewFeedResponse(BaseModel):
	entries: list[ReviewEntryModel]
	matched_entry_count: int
	returned_entry_count: int
	has_more: bool
	offset: int
	limit: int | None = None
	catalog_count: int
	approved_count: int
	review_count: int
	status_counts: dict[str, int]
	group_counts: dict[str, int]
	visible_entry_count: int
	visible_catalog_count: int
	suppressed_counts: dict[str, int]
	groups: list[ReviewGroupModel]
	issues: list[ValidationIssueModel]


class GroupsResponse(BaseModel):
	groups: list[ReviewGroupModel]
	assignments: dict[str, list[str]]
	assignment_record_hashes: dict[str, RecordHash]
	counts: dict[str, int]


class GroupWriteResponse(BaseModel):
	group: ReviewGroupModel
	issues: list[ValidationIssueModel] = Field(default_factory=list)
	projection: ProjectionWriteState


class ReviewWriteResponse(BaseModel):
	review: ReviewRecordModel | None
	issues: list[ValidationIssueModel] = Field(default_factory=list)
	projection: ProjectionWriteState


class AssignmentRecordModel(BaseModel):
	type_path: str
	group_ids: list[str]


class AssignmentWriteResponse(BaseModel):
	assignment: AssignmentRecordModel | None
	record_hash: RecordHash | None = None
	issues: list[ValidationIssueModel] = Field(default_factory=list)
	projection: ProjectionWriteState


class EntityFilesResponse(BaseModel):
	files: list[str]


class IconFilesResponse(BaseModel):
	files: list[str]


class IconStatesResponse(BaseModel):
	states: list[str]


class ValidationResponse(BaseModel):
	valid: bool
	issues: list[ValidationIssueModel]


class DeleteEntryResponse(BaseModel):
	deleted: bool
	id: str
	projection: ProjectionWriteState


class CreateEntryRequest(BaseModel):
	source_file: str = Field(min_length=1)
	entry: dict[str, object]


class SaveEntryRequest(CreateEntryRequest):
	expected_record_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class DeleteEntryRequest(BaseModel):
	source_file: str = Field(min_length=1)
	expected_record_hash: RecordHash


class ValidateRequest(BaseModel):
	source_file: str | None = None
	entry: dict[str, object] | None = None
	entries: list[dict[str, object]] | None = Field(
		default=None,
		description="Validate a batch. When present, `entry` is ignored.",
	)


class SaveEntryResponse(BaseModel):
	saved: bool
	created: bool = False
	entry: dict[str, object]
	record_hash: str
	issues: list[dict[str, object]] = Field(default_factory=list)
	projection: ProjectionWriteState


class DefinitionResponse(BaseModel):
	path: str | None
	line: int | None


class GroupFields(BaseModel):
	label: str = Field(min_length=1)
	color: str = Field(min_length=1)
	keywords: list[str] = Field(default_factory=list)
	type_path_prefixes: list[str] = Field(default_factory=list)
	keyword_scope: list[str] | None = None
	assignments: list[str] = Field(default_factory=list)


class CreateGroupRequest(GroupFields):
	id: str = Field(min_length=1)


class UpdateGroupRequest(GroupFields):
	id: str | None = None
	expected_record_hash: RecordHash


class DeleteGroupRequest(BaseModel):
	expected_record_hash: RecordHash


class DeleteGroupResponse(BaseModel):
	deleted: bool
	id: str
	updated_assignments: int
	projection: ProjectionWriteState


class ReviewWriteRequest(BaseModel):
	status: Literal["reviewed", "needs-attention"] | None
	reviewed_by: str = ""
	notes: str = ""
	expected_record_hash: RecordHash | None


class AssignmentWriteRequest(BaseModel):
	group_ids: list[str]
	expected_record_hash: RecordHash | None


# ---- Export ---------------------------------------------------------------------------------------


class ExportStage(BaseModel):
	stage: str
	manifest: dict[str, object]


class ExportStagesResponse(BaseModel):
	stages: list[ExportStage]


class PrepareExportResponse(BaseModel):
	prepared: bool
	stage: str
	artifact: str
	manifest: dict[str, object]


class ApplyExportRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	stage: str = Field(min_length=1)


class ApplyExportResponse(BaseModel):
	applied: bool
	artifact: str
	opened_in_github_desktop: bool
	github_desktop_error: str | None = None


# ---- AphelionDMM collaboration -------------------------------------------------------------------


class CollaborationCapabilitiesResponse(BaseModel):
	configured: bool
	version: bool
	session_access: bool = False
	join: bool = False
	checkpoint: bool = False
	reason: str


class CollaborationVersionResponse(BaseModel):
	build: str
	revision: str
	protocol_versions: list[int]
	schema_versions: list[int]
	compatible: bool


class CollaborationSessionResponse(BaseModel):
	session_id: str
	document_id: str
	protocol_version: int
	schema_version: int
	revision: int
	map_hash: RecordHash


class CollaborationJoinRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	role: Literal["viewer", "editor"]
	display_name: str = Field(min_length=1, max_length=128)


class CollaborationJoinResponse(BaseModel):
	token: str = Field(min_length=1, max_length=128)
	actor_id: str
	role: Literal["viewer", "editor"]
	expires_at: str


class CollaborationCheckpointRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	revision: int = Field(ge=0)
	map_hash: RecordHash
	idempotency_key: str = Field(min_length=1, max_length=128)

	@field_validator("idempotency_key")
	@classmethod
	def validate_idempotency_key(cls, value: str) -> str:
		if not value.strip() or len(value.encode("utf-8")) > 128:
			raise ValueError("Idempotency key must be nonblank and at most 128 UTF-8 bytes.")
		return value


class CollaborationCheckpointResponse(BaseModel):
	checkpoint_id: str
	revision: int = Field(ge=0)
	map_hash: RecordHash
	status: Literal["pending", "accepted", "rejected"]


# ---- References -----------------------------------------------------------------------------------

ReferenceTool = Literal["lore-editor", "graph", "file-management", "job-editor", "outfit-editor"]
ReferenceKind = Literal["catalog_target", "graph_node", "file", "definition"]


class Reference(BaseModel):
	catalog_id: str | None = None
	id: str
	tool: ReferenceTool
	kind: ReferenceKind
	key: str
	label: str
	path: str | None = None
	note: str | None = None
	created_at: str


class ReferenceListResponse(BaseModel):
	references: list[Reference]


class AddReferenceRequest(BaseModel):
	catalog_id: str | None = Field(default=None, max_length=128)
	tool: ReferenceTool
	kind: ReferenceKind
	key: str = Field(min_length=1)
	label: str = Field(min_length=1)
	path: str | None = None
	note: str | None = None


class DeleteResponse(BaseModel):
	deleted: bool
	id: str


# ---- Live updates ---------------------------------------------------------------------------------

class ProjectionRevisionResponse(BaseModel):
	schema_version: int
	content_revision: str
	embedding_model_id: str
	state: Literal["current", "stale"]


class GameSourceRevisionResponse(BaseModel):
	worktree_id: str
	head: str
	dirty: bool | None = None
	graph_observation: str | None = None


class WorkspaceRevisionResponse(BaseModel):
	worktree_id: str
	branch: str
	head: str
	content_revision: str
	projection_revision: ProjectionRevisionResponse | None
	projection_generation_id: str | None
	game_source: GameSourceRevisionResponse | None
	definition_revision: str | None = None
	definition_catalog_id: str | None = None


LiveMessageType = Literal["health", "active_runs", "workspace_revision", "definition_runs"]


class LiveMessage(BaseModel):
	"""One frame pushed over /ws.

	Documented as a model so the generated TypeScript describes the socket protocol too, rather than
	leaving the frontend to hand-write frame shapes that can drift from what the server sends.
	"""

	type: LiveMessageType
	data: dict[str, object] | list[dict[str, object]] | None

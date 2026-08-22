from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

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


class ErrorResponse(BaseModel):
	error: str = Field(description="Human-readable message, suitable for display.")
	code: str = Field(description="Stable machine-readable error code; branch on this, not on `error`.")


# ---- Store ----------------------------------------------------------------------------------------


class StoreHealth(BaseModel):
	tables: dict[str, int] = Field(description="Row count per table.")
	total_rows: int
	disk_bytes: int
	last_write_time: float | None = Field(
		default=None,
		description="Unix timestamp of the most recent write, from file mtimes. Null if the store is empty.",
	)


class SearchResult(BaseModel):
	table: str
	score: float = Field(description="Reciprocal-rank-fusion score combining full-text and vector rank.")
	id: str
	record: dict[str, object]


class SearchResponse(BaseModel):
	results: list[SearchResult]


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
	sha: str
	author: str | None = None
	date: str | None = None
	summary: str | None = None


class MarkerHistoryResponse(BaseModel):
	commits: list[CommitInfo]


# ---- Content graph --------------------------------------------------------------------------------


class GraphResponse(BaseModel):
	scanned: bool
	graph: dict[str, object] | None = None
	manifest: dict[str, object] | None = None


class GraphStatusResponse(BaseModel):
	scanned: bool
	manifest: dict[str, object] | None = None


class GraphEditsResponse(BaseModel):
	scanned: bool
	edits: list[dict[str, object]] = Field(default_factory=list)


class GraphModulesResponse(BaseModel):
	scanned: bool
	modules: list[dict[str, object]] = Field(default_factory=list)


class GraphUnresolvedResponse(BaseModel):
	scanned: bool
	unresolved_markers: list[dict[str, object]] = Field(default_factory=list)


class MarkerEditRequest(BaseModel):
	core_file: str = Field(min_length=1)
	line_number: int = Field(ge=1)
	expected_line: str = Field(description="The line's current content, checked before writing to avoid a stale edit.")
	new_label: str = Field(min_length=1)


class MarkerEditResponse(BaseModel):
	edited: bool
	core_file: str
	line_number: int


# ---- Lore editor ----------------------------------------------------------------------------------


class SaveEntryRequest(BaseModel):
	source_file: str = Field(min_length=1)
	entry: dict[str, object] | None = None


class DeleteEntryRequest(BaseModel):
	source_file: str = Field(min_length=1)


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
	issues: list[dict[str, object]] = Field(default_factory=list)


class DefinitionResponse(BaseModel):
	path: str | None
	line: int | None


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
	stage: str = Field(min_length=1)
	force: bool = Field(
		default=False,
		description="Apply to a dirty checkout. Off by default -- a dirty checkout is normally a stop condition.",
	)


class ApplyExportResponse(BaseModel):
	applied: bool
	artifact: str
	opened_in_github_desktop: bool
	github_desktop_error: str | None = None


# ---- References -----------------------------------------------------------------------------------

ReferenceTool = Literal["lore-editor", "graph", "file-management"]
ReferenceKind = Literal["catalog_target", "graph_node", "file"]


class Reference(BaseModel):
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

LiveMessageType = Literal["health", "active_runs"]


class LiveMessage(BaseModel):
	"""One frame pushed over /ws.

	Documented as a model so the generated TypeScript describes the socket protocol too, rather than
	leaving the frontend to hand-write frame shapes that can drift from what the server sends.
	"""

	type: LiveMessageType
	data: dict[str, object] | list[dict[str, object]]

from __future__ import annotations

from webapp.tooling import ToolDefinition

TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = (
	ToolDefinition(
		id="rebuild-search-embeddings",
		label="Rebuild search embeddings",
		description=(
			"Re-embed every row's search text across the shared data store (catalog targets, overrides, "
			"groups, reviews, content-graph nodes/edges, references). Run this after changing the embedding "
			"model, or if semantic search results look stale -- it never touches keyword (full-text) search, "
			"which stays current automatically as rows are written."
		),
		tool_root="webapp/store",
		commands=(("rebuild-embeddings",),),
	),
	ToolDefinition(
		id="optimize-store",
		label="Optimize database",
		description=(
			"Compact small fragment files into larger ones, prune file versions past the 7-day retention "
			"window, and fold newly-written rows into every index -- LanceDB's own maintenance routine. "
			"Run this periodically (it also runs once automatically shortly after the app starts) to keep "
			"the store's on-disk size and read performance from degrading as rows are written over time; "
			"it never changes what's stored, only how efficiently it's stored."
		),
		tool_root="webapp/store",
		commands=(("optimize",),),
	),
)

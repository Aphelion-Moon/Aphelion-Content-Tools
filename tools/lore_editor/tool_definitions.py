from __future__ import annotations

from webapp.tooling import ToolDefinition

TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = (
	ToolDefinition(
		id="catalog-reload",
		label="Load release catalog",
		description=(
			"Replace the current catalog with the verified release supplied by the maintainer. "
			"Checks the release manifest, target data, and selected game revision before activation. "
			"Your authored records are preserved; a failed download leaves the current catalog available. "
			"Requires a matching catalog-seed.json release manifest."
		),
		tool_root="tools/lore_editor",
		commands=(("catalog-reload",),),
		game_repo_commands=frozenset({"catalog-reload"}),
	),
	ToolDefinition(
		id="catalog-refresh",
		label="Refresh catalog",
		description=(
			"Run the BYOND catalog probe against the game checkout to update local authoring targets. "
			"Use after changes that add, remove, or rename reviewable types. This requires the maintained "
			"game probe and build tools. Local probe output remains unverified for export; load a matching "
			"release catalog before preparing an export."
		),
		tool_root="tools/lore_editor",
		commands=(("catalog-refresh",),),
		game_repo_commands=frozenset({"catalog-refresh"}),
	),
	ToolDefinition(
		id="validate",
		label="Validate content",
		description=(
			"Check every lore override JSON record for structural and reference errors (missing base "
			"types, broken icon/group references, malformed special-description rules), then confirm the "
			"checked-in generated DM artifact still matches what the current overrides would produce. Run "
			"this before preparing a Game Repository Export, or any time after hand-editing override JSON "
			"files outside the Lore Editor UI, to catch mistakes before they reach the game checkout."
		),
		tool_root="tools/lore_editor",
		commands=(("validate", "--check-generated"),),
		game_repo_commands=frozenset({"validate"}),
	),
	ToolDefinition(
		id="generate",
		label="Generate DM",
		description=(
			"Regenerate the checked-in lore override DM artifact from the current override JSON records, "
			"without touching the game checkout. Useful for previewing what a Game Repository Export would "
			"produce, or refreshing the artifact locally after editing overrides, before running Validate "
			"or preparing an export."
		),
		tool_root="tools/lore_editor",
		commands=(("generate",),),
	),
	ToolDefinition(
		id="refresh-validate",
		label="Refresh and validate",
		description=(
			"Run the local BYOND catalog probe, then validate authored records and generated output. "
			"This updates local authoring data but does not verify compiler provenance for export. "
			"Load a matching release catalog before preparing a Game Repository Export."
		),
		tool_root="tools/lore_editor",
		commands=(("catalog-refresh",), ("validate", "--check-generated")),
		game_repo_commands=frozenset({"catalog-refresh", "validate"}),
	),
)

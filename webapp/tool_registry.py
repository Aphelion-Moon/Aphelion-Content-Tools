from __future__ import annotations

from .tooling import ToolDefinition


def load_tool_registry() -> tuple[ToolDefinition, ...]:
	"""Combine every tool's registered `ToolDefinition`s into one tuple.

	Shared by `webapp/server.py` (to list/dispatch tools from the main HTTP server) and
	`webapp/store_worker.py` (to resolve a `tool_id` back into a definition inside the worker process),
	so there is exactly one place that knows the full set of tools.
	"""
	from tools.content_graph.tool_definitions import TOOL_DEFINITIONS as GRAPH_TOOL_DEFINITIONS
	from tools.lore_editor.tool_definitions import TOOL_DEFINITIONS as LORE_TOOL_DEFINITIONS
	from webapp.store.tool_definitions import TOOL_DEFINITIONS as STORE_TOOL_DEFINITIONS
	return LORE_TOOL_DEFINITIONS + GRAPH_TOOL_DEFINITIONS + STORE_TOOL_DEFINITIONS

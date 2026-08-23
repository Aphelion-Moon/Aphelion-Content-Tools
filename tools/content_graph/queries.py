from __future__ import annotations

from .models import ContentGraph, GraphNode, UnresolvedMarker


def edits_for_core_file(graph: ContentGraph, core_file: str) -> list[dict[str, object]]:
	"""All marker edges touching `core_file`, resolved and unresolved alike."""
	edits: list[dict[str, object]] = []
	for edge in graph["edges"]:
		if edge.get("relation") != "marker_edit":
			continue
		if edge.get("target") != f"core_file:{core_file}":
			continue
		edits.append({**edge, "resolved": True})
	for marker in graph["unresolved_markers"]:
		if marker.get("core_file") != core_file:
			continue
		edits.append({**marker, "resolved": False})
	def line_number(edit: dict[str, object]) -> int:
		value = edit.get("line_number")
		return value if isinstance(value, int) else 0

	edits.sort(key=line_number)
	return edits


def modules_missing_readme(graph: ContentGraph) -> list[GraphNode]:
	return [node for node in graph["nodes"] if node.get("kind") == "module" and not node.get("has_readme")]


def unresolved_markers(graph: ContentGraph) -> list[UnresolvedMarker]:
	return list(graph["unresolved_markers"])

from __future__ import annotations

from typing import Literal, Required, TypedDict, cast

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
MarkerOwner = Literal["NOVA", "APHELION"]
MarkerAttribution = Literal["exact", "path-derived", "unattributed"]


class GraphNode(TypedDict, total=False):
	id: Required[str]
	kind: Required[GraphNodeKind]
	owner: GraphNodeOwner
	module_id: str
	path: str
	name: str
	core_path: str
	has_readme: bool
	marker_count: int
	file_count: int
	total_bytes: int
	size_bytes: int | None
	line_count: int | None


class GraphEdge(TypedDict, total=False):
	source: Required[str]
	target: Required[str]
	relation: Required[GraphEdgeRelation]
	edit_type: GraphEditType
	attribution: MarkerAttribution
	line_number: int
	raw_label: str
	original_text: str | None


class UnresolvedMarker(TypedDict):
	core_file: str
	owner: MarkerOwner
	edit_type: GraphEditType
	line_number: int
	source_module_id: str | None
	attribution: MarkerAttribution
	raw_label: str
	original_text: str | None
	line_text: str


class GraphCounts(TypedDict):
	module_count: int
	master_files_count: int
	core_file_count: int
	marker_count: int
	unresolved_marker_count: int
	file_count: int
	directory_count: int
	reference_count: int


class ContentGraph(TypedDict):
	nodes: list[GraphNode]
	edges: list[GraphEdge]
	unresolved_markers: list[UnresolvedMarker]
	counts: GraphCounts


_NODE_KINDS = frozenset(("module", "master_file", "core_file", "directory", "file"))
_EDGE_RELATIONS = frozenset(("master_files_mirror", "marker_edit", "contains", "module_reference", "core_reference"))


def parse_graph_node(payload: object) -> GraphNode:
	if not isinstance(payload, dict):
		raise ValueError("Graph node must be an object.")
	if not isinstance(payload.get("id"), str) or payload.get("kind") not in _NODE_KINDS:
		raise ValueError("Graph node requires a string id and supported kind.")
	return cast(GraphNode, payload)


def parse_graph_edge(payload: object) -> GraphEdge:
	if not isinstance(payload, dict):
		raise ValueError("Graph edge must be an object.")
	if not isinstance(payload.get("source"), str) or not isinstance(payload.get("target"), str):
		raise ValueError("Graph edge requires string source and target ids.")
	if payload.get("relation") not in _EDGE_RELATIONS:
		raise ValueError("Graph edge has an unsupported relation.")
	return cast(GraphEdge, payload)


def parse_unresolved_marker(payload: object) -> UnresolvedMarker:
	if not isinstance(payload, dict):
		raise ValueError("Unresolved marker must be an object.")
	if not isinstance(payload.get("core_file"), str) or not isinstance(payload.get("line_number"), int):
		raise ValueError("Unresolved marker requires a core file and line number.")
	return cast(UnresolvedMarker, payload)


def parse_graph_counts(payload: object) -> GraphCounts:
	if not isinstance(payload, dict):
		raise ValueError("Graph counts must be an object.")
	fields = (
		"module_count", "master_files_count", "core_file_count", "marker_count",
		"unresolved_marker_count", "file_count", "directory_count", "reference_count",
	)
	if any(not isinstance(payload.get(field), int) or payload[field] < 0 for field in fields):
		raise ValueError("Graph counts must be non-negative integers.")
	return cast(GraphCounts, payload)


def content_graph_from_cache(
	nodes: list[object],
	edges: list[object],
	unresolved_markers: list[object],
	counts: object,
) -> ContentGraph:
	return {
		"nodes": [parse_graph_node(node) for node in nodes],
		"edges": [parse_graph_edge(edge) for edge in edges],
		"unresolved_markers": [parse_unresolved_marker(marker) for marker in unresolved_markers],
		"counts": parse_graph_counts(counts),
	}

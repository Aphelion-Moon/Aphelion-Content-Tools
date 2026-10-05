from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from tools.lore_editor.reconcile import reconcile_projection, scan_canonical_records
from tools.lore_editor.write_coordinator import repository_write_lock
from webapp.game_repository import validate_game_repository
from webapp.git_adapter import repository_revision
from webapp.json_storage import canonical_json_bytes
from webapp.manifest_base import sha256_bytes
from webapp.store import db
from webapp.store.generations import staged_projection
from webapp.store.lifecycle import with_projection_read
from webapp.store.schema import decode, encode, table, writable_table

from .inputs import GraphInputs, capture_graph_inputs, verify_graph_inputs
from .manifest import GraphManifest
from .markers import MarkerEdge, parse_markers
from .models import (
	ContentGraph,
	GraphEdge,
	GraphNode,
	UnresolvedMarker,
	content_graph_from_cache,
)
from .references import find_text_references
from .scanner import (
	CORE_SCAN_ROOT,
	MARKER_FILE_SUFFIXES,
	CoreFileContent,
	ModuleContent,
)


def _module_node_id(owner: str, module_id: str) -> str:
	return f"module:{owner}:{module_id}"


def _master_file_node_id(owner: str, path: str) -> str:
	return f"master_file:{owner}:{path}"


def _core_file_node_id(path: str) -> str:
	return f"core_file:{path}"


ROOT_DIR_ID = "dir:."


def _basename(posix_path: str) -> str:
	return posix_path.rsplit("/", 1)[-1]


def _parent_posix(posix_path: str) -> str:
	return posix_path.rsplit("/", 1)[0] if "/" in posix_path else ""


def _add_full_tree(
	nodes: list[GraphNode],
	edges: list[GraphEdge],
	path_to_id: dict[str, str],
	tracked_paths: tuple[str, ...],
) -> int:
	"""Add directory/file nodes and `contains` edges for every tracked path not already represented.

	`path_to_id` is pre-seeded with the paths already covered by module/master_file/core_file nodes, so
	this only mints generic `dir:`/`file:` nodes for the rest of the checkout -- while still wiring the
	existing specialized nodes into the same containment tree, rooted at `ROOT_DIR_ID`. Returns the
	total number of unique directories in the tree (including module directories and the root).
	"""
	dir_created: set[str] = set()

	def ensure_dir(dir_posix: str) -> str:
		node_id = ROOT_DIR_ID if dir_posix == "" else path_to_id.get(dir_posix, f"dir:{dir_posix}")
		if node_id in dir_created:
			return node_id
		dir_created.add(node_id)
		parent_id = ensure_dir(_parent_posix(dir_posix)) if dir_posix != "" else None
		if dir_posix not in path_to_id:
			nodes.append({
				"id": node_id,
				"kind": "directory",
				"path": dir_posix or ".",
				"name": _basename(dir_posix) if dir_posix else "(repository root)",
			})
		if parent_id is not None:
			edges.append({"source": parent_id, "target": node_id, "relation": "contains"})
		return node_id

	for file_path in tracked_paths:
		parent_id = ensure_dir(_parent_posix(file_path))
		node_id = path_to_id.get(file_path)
		if node_id is None:
			node_id = f"file:{file_path}"
			nodes.append({
				"id": node_id,
				"kind": "file",
				"path": file_path,
				"name": _basename(file_path),
			})
		edges.append({"source": parent_id, "target": node_id, "relation": "contains"})

	return len(dir_created)


def _marker_payload(core_path: str, marker: MarkerEdge) -> UnresolvedMarker:
	return {
		"core_file": core_path,
		"owner": marker.owner,
		"edit_type": marker.edit_type,
		"line_number": marker.line_number,
		"source_module_id": marker.source_module_id,
		"attribution": marker.attribution,
		"raw_label": marker.raw_label,
		"original_text": marker.original_text,
		"line_text": marker.line_text,
	}


def build_content_graph(game_repo_root: Path) -> ContentGraph:
	"""Scan a game checkout and return a JSON-serializable node/edge graph document.

	Modules, master_files overrides, and marker-bearing core files get the specialized `module`/
	`master_file`/`core_file` node kinds with their semantic edges (`master_files_mirror`,
	`marker_edit`), as before. Every other Git-tracked path in the checkout is additionally represented
	as a generic `directory`/`file` node, connected into the same tree via `contains` edges rooted at
	`dir:.` -- so every node has at least one edge, and the full checkout is browsable even where no
	semantic relationship has been extracted.
	"""
	return build_content_graph_from_inputs(capture_graph_inputs(game_repo_root))


def build_content_graph_from_inputs(inputs: GraphInputs) -> ContentGraph:
	"""Build from immutable captured bytes so markers and metadata describe the same source."""
	inventory = inputs.inventory
	modules = inventory.modules
	known_module_ids = frozenset(module.id for module in modules)
	master_files = inventory.master_files
	files = dict(inputs.files)
	markers_by_path = {}
	for path in inventory.core_paths:
		if Path(path).is_relative_to(CORE_SCAN_ROOT) and Path(path).suffix.casefold() in MARKER_FILE_SUFFIXES and path in files:
			markers = parse_markers(files[path].decode("utf-8", errors="replace"), known_module_ids)
			if markers:
				markers_by_path[path] = tuple(markers)
	core_paths = {master_file.core_path for master_file in master_files} | set(markers_by_path.keys())
	module_parts: dict[str, list[bytes]] = {}
	for owner, path in inventory.module_paths:
		if path in files:
			module_parts.setdefault(owner, []).append(files[path])
	module_contents = {}
	for module in modules:
		parts = module_parts.get(module.path, [])
		module_contents[module.path] = ModuleContent(
			text="\n".join(part.decode("utf-8", errors="replace") for part in parts),
			file_count=len(parts), total_bytes=sum(len(part) for part in parts),
		)
	core_contents = {}
	for path in core_paths:
		if path not in files:
			continue
		data = files[path]
		text = data.decode("utf-8", errors="replace")
		line_count = 0 if not text else text.count("\n") + (0 if text.endswith("\n") else 1)
		core_contents[path] = CoreFileContent(text, len(data), line_count)

	nodes: list[GraphNode] = []
	for module in modules:
		content = module_contents.get(module.path)
		nodes.append({
			"id": _module_node_id(module.owner, module.id),
			"kind": "module",
			"owner": module.owner,
			"module_id": module.id,
			"path": module.path,
			"has_readme": module.has_readme,
			"file_count": content.file_count if content else 0,
			"total_bytes": content.total_bytes if content else 0,
		})
	master_sizes = dict(inventory.master_sizes)
	for master_file in master_files:
		size_bytes = master_sizes[master_file.path]
		nodes.append({
			"id": _master_file_node_id(master_file.owner, master_file.path),
			"kind": "master_file",
			"owner": master_file.owner,
			"path": master_file.path,
			"core_path": master_file.core_path,
			"size_bytes": size_bytes,
		})
	for core_path in sorted(core_paths):
		content = core_contents.get(core_path)
		nodes.append({
			"id": _core_file_node_id(core_path),
			"kind": "core_file",
			"path": core_path,
			"marker_count": len(markers_by_path.get(core_path, ())),
			"size_bytes": content.size_bytes if content else None,
			"line_count": content.line_count if content else None,
		})

	edges: list[GraphEdge] = []
	for master_file in master_files:
		edges.append({
			"source": _master_file_node_id(master_file.owner, master_file.path),
			"target": _core_file_node_id(master_file.core_path),
			"relation": "master_files_mirror",
		})

	# Best-effort cross-references: a module or core file whose text literally mentions another
	# module's/core file's path (e.g. a comment referencing "modular_nova/modules/other_module", or one
	# core file's marker text mentioning another core file) surfaces coupling that the structural edges
	# above don't capture. This is a textual scan, not real DM/BYOND parsing -- see references.py.
	module_fragment_ids = {module.path: _module_node_id(module.owner, module.id) for module in modules}
	module_texts = {path: content.text for path, content in module_contents.items()}
	for source_id, target_id in find_text_references(module_texts, module_fragment_ids):
		edges.append({"source": source_id, "target": target_id, "relation": "module_reference"})

	core_fragment_ids = {path: _core_file_node_id(path) for path in core_paths}
	core_texts = {path: content.text for path, content in core_contents.items()}
	for source_id, target_id in find_text_references(core_texts, core_fragment_ids):
		edges.append({"source": source_id, "target": target_id, "relation": "core_reference"})

	unresolved_markers: list[UnresolvedMarker] = []
	marker_count = 0
	for core_path, markers in sorted(markers_by_path.items()):
		for marker in markers:
			marker_count += 1
			if marker.attribution == "exact" and marker.source_module_id is not None:
				edges.append({
					"source": _module_node_id(marker.owner.casefold(), marker.source_module_id),
					"target": _core_file_node_id(core_path),
					"relation": "marker_edit",
					"edit_type": marker.edit_type,
					"attribution": marker.attribution,
					"line_number": marker.line_number,
					"raw_label": marker.raw_label,
					"original_text": marker.original_text,
				})
			else:
				unresolved_markers.append(_marker_payload(core_path, marker))

	path_to_id = {node["path"]: node["id"] for node in nodes if "path" in node}
	tracked_paths = inventory.tracked_paths
	directory_count = _add_full_tree(nodes, edges, path_to_id, tracked_paths)

	reference_count = sum(1 for edge in edges if edge["relation"] in ("module_reference", "core_reference"))

	return {
		"nodes": nodes,
		"edges": edges,
		"unresolved_markers": unresolved_markers,
		"counts": {
			"module_count": len(modules),
			"master_files_count": len(master_files),
			"core_file_count": len(core_paths),
			"marker_count": marker_count,
			"unresolved_marker_count": len(unresolved_markers),
			"file_count": len(tracked_paths),
			"directory_count": directory_count,
			"reference_count": reference_count,
		},
	}


def _node_text(node: GraphNode) -> str:
	return " ".join(str(node.get(field)) for field in ("id", "kind", "path", "name", "module_id") if node.get(field))


def scan_and_cache_content_graph(repo_root: Path, game_repo_root: Path) -> GraphManifest:
	"""Validate the game checkout, scan it, and atomically publish the graph projection."""
	resolved_repo_root = repo_root.resolve()
	resolved_game_root = game_repo_root.resolve()
	validate_game_repository(resolved_game_root)

	try:
		game_revision = repository_revision(resolved_game_root)
	except (OSError, ValueError):
		game_revision = "unknown"
	inputs = capture_graph_inputs(resolved_game_root)
	graph = build_content_graph_from_inputs(inputs)
	graph_bytes = canonical_json_bytes(graph)

	counts = graph["counts"]
	manifest = GraphManifest(
		snapshot_sha256=sha256_bytes(graph_bytes),
		game_repo_revision=game_revision,
		source_sha256=inputs.source_sha256,
		source_observation=inputs.inventory.observation,
		generated_at=datetime.now(UTC).isoformat(),
		node_count=len(graph["nodes"]),
		edge_count=len(graph["edges"]),
		module_count=counts["module_count"],
		master_files_count=counts["master_files_count"],
		marker_count=counts["marker_count"],
		file_count=counts["file_count"],
		directory_count=counts["directory_count"],
		reference_count=counts["reference_count"],
	)

	def _print_progress(label: str):
		def report(done: int, total: int) -> None:
			print(f"{label}: embedded {done}/{total} changed row(s)...", flush=True)
		return report

	with repository_write_lock(resolved_repo_root):
		reconcile_projection(resolved_repo_root)
		content_revision = scan_canonical_records(resolved_repo_root).content_revision
		with staged_projection(resolved_repo_root, content_revision=content_revision, changed_tables={"graph_nodes", "graph_edges", "unresolved_markers", "manifests"}) as staged:
			db.sync_snapshot(writable_table(resolved_repo_root, "graph_nodes", store_dir=staged.path), "id", [
				{
					"id": node["id"],
					"kind": node.get("kind", ""),
					"path": node.get("path", ""),
					"raw_json": encode(node),
					"text": _node_text(node),
				}
				for node in graph["nodes"]
			], embed=False, on_progress=_print_progress("Nodes"))
			# Edge/marker ids must be stable across scans for the above diffing to mean anything -- a positional
			# index (the previous scheme) shifts for every edge/marker whenever an earlier one is added or
			# removed, which would make nearly everything look "changed" on every scan even when it wasn't. A
			# content hash of the edge/marker's own fields is stable regardless of list order.
			db.sync_snapshot(writable_table(resolved_repo_root, "graph_edges", store_dir=staged.path), "id", [
				{
					"id": db.content_hash_for(encode(edge))[:24],
					"source": edge["source"],
					"target": edge["target"],
					"relation": edge["relation"],
					"raw_json": encode(edge),
					"text": f"{edge['source']} {edge['target']} {edge['relation']}",
				}
				for edge in graph["edges"]
			], embed=False, on_progress=_print_progress("Edges"))
			db.sync_snapshot(writable_table(resolved_repo_root, "unresolved_markers", store_dir=staged.path), "id", [
				{
					"id": db.content_hash_for(encode(marker))[:24],
					"core_file": marker["core_file"],
					"raw_json": encode(marker),
					"text": f"{marker['core_file']} {marker.get('raw_label', '')} {marker.get('original_text', '')}",
				}
				for marker in graph["unresolved_markers"]
			], embed=False, on_progress=_print_progress("Unresolved markers"))
			db.upsert_rows(writable_table(resolved_repo_root, "manifests", store_dir=staged.path), "id", [{
				"id": "graph",
				"raw_json": encode({"manifest": manifest.to_dict(), "counts": counts, "graph": graph}),
				"text": "",
			}, {
				"id": "graph-health",
				"raw_json": encode(manifest.to_dict()),
				"text": "",
			}])
			verify_graph_inputs(resolved_game_root, inputs)
			try:
				current_revision = repository_revision(resolved_game_root)
			except (OSError, ValueError):
				current_revision = "unknown"
			if current_revision != game_revision:
				raise ValueError("Game source changed during graph generation. Run the scan again.")
	return manifest


@with_projection_read
def read_graph_cache(repo_root: Path) -> tuple[ContentGraph, GraphManifest] | None:
	"""Return the cached (graph, manifest) pair, or None if no scan has been run yet."""
	resolved_root = repo_root.resolve()
	pinned_store = db.store_path(resolved_root)
	manifest_row = db.get_row_by_key(table(resolved_root, "manifests", store_dir=pinned_store), "id", "graph")
	if manifest_row is None:
		return None
	stored = decode(manifest_row)
	manifest = GraphManifest.from_dict(stored["manifest"])
	stored_graph = stored.get("graph")
	if isinstance(stored_graph, dict):
		stored_nodes = stored_graph.get("nodes")
		stored_edges = stored_graph.get("edges")
		stored_markers = stored_graph.get("unresolved_markers")
		counts = stored_graph.get("counts")
		if not isinstance(stored_nodes, list) or not isinstance(stored_edges, list) or not isinstance(stored_markers, list):
			raise ValueError("Stored graph snapshot is missing its node, edge, or marker list.")
		return content_graph_from_cache(stored_nodes, stored_edges, stored_markers, counts), manifest

	nodes: list[object] = [decode(row) for row in db.all_rows(table(resolved_root, "graph_nodes", store_dir=pinned_store))]
	edges: list[object] = [decode(row) for row in db.all_rows(table(resolved_root, "graph_edges", store_dir=pinned_store))]
	unresolved_markers: list[object] = [decode(row) for row in db.all_rows(table(resolved_root, "unresolved_markers", store_dir=pinned_store))]
	graph = content_graph_from_cache(nodes, edges, unresolved_markers, stored["counts"])
	return graph, manifest

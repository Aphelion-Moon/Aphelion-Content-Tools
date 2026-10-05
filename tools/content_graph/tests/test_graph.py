from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.content_graph.graph import (
	build_content_graph,
	build_content_graph_from_inputs,
	read_graph_cache,
	scan_and_cache_content_graph,
)
from tools.content_graph.inputs import capture_graph_inputs, observe_graph_inputs, verify_graph_inputs
from tools.lore_editor.reconcile import scan_canonical_records
from tools.lore_editor.records import atomic_write_record, record_path
from webapp.store import db
from webapp.store.metadata import active_projection_metadata
from webapp.store.schema import decode, encode, table


def run_git(repo_root: Path, *arguments: str) -> None:
	subprocess.run(["git", "-C", str(repo_root), *arguments], check=True, capture_output=True, text=True)


def make_fixture_game_repo(game_root: Path) -> None:
	game_root.mkdir(parents=True)
	(game_root / "tgstation.dme").write_text("", encoding="utf-8")

	module_dir = game_root / "modular_nova" / "modules" / "shuttle_toggle" / "code"
	module_dir.mkdir(parents=True)
	(module_dir / "shuttle_toggle.dm").write_text(
		"/obj/docking_port/shuttle_toggle\n"
		"// See modular_nova/modules/no_readme_module for related config.\n",
		encoding="utf-8",
	)
	(game_root / "modular_nova" / "modules" / "shuttle_toggle" / "readme.md").write_text("# Shuttle toggle\n", encoding="utf-8")

	# a module with no readme.md
	(game_root / "modular_nova" / "modules" / "no_readme_module" / "code").mkdir(parents=True)

	master_files_root = game_root / "modular_nova" / "master_files" / "code" / "modules" / "shuttle"
	master_files_root.mkdir(parents=True)
	(master_files_root / "shuttle.dm").write_text("/obj/docking_port\n", encoding="utf-8")

	core_file = game_root / "code" / "modules" / "shuttle" / "shuttle.dm"
	core_file.parent.mkdir(parents=True)
	core_file.write_text(
		"/obj/docking_port\n"
		"\t// NOVA EDIT ADDITION START - SHUTTLE_TOGGLE - allow manual recall\n"
		"\tvar/adminEmergencyNoRecall = FALSE\n"
		"\t// NOVA EDIT ADDITION END\n",
		encoding="utf-8",
	)

	# a core file with an unresolved marker (references a module that doesn't exist)
	other_core_file = game_root / "code" / "modules" / "other" / "other.dm"
	other_core_file.parent.mkdir(parents=True)
	other_core_file.write_text(
		"/obj/item/other\n"
		"\t// NOVA EDIT ADDITION - some future module\n"
		"\t// Also touches code/modules/shuttle/shuttle.dm\n",
		encoding="utf-8",
	)

	# non-modular repo content -- not a module, master_files override, or marker-bearing core file
	(game_root / ".github" / "workflows").mkdir(parents=True)
	(game_root / ".github" / "workflows" / "ci.yml").write_text("name: CI\n", encoding="utf-8")
	(game_root / "README.md").write_text("# Meridian-Rift\n", encoding="utf-8")
	(game_root / "icons" / "obj").mkdir(parents=True)
	(game_root / "icons" / "obj" / "example.dmi").write_text("", encoding="utf-8")


class ContentGraphScanTests(unittest.TestCase):
	def setUp(self) -> None:
		model = patch("webapp.store.embeddings._load_model", return_value=None)
		model.start()
		self.addCleanup(model.stop)

	def test_unreadable_master_subtree_cannot_be_omitted_from_verified_source(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			game_root = Path(temp_dir) / "game"
			make_fixture_game_repo(game_root)
			blocked = game_root / "modular_nova/master_files/code"
			scandir = os.scandir

			def fail_unreadable(path):
				if Path(path) == blocked:
					raise PermissionError("Fixture subtree is unreadable")
				return scandir(path)

			with patch("os.scandir", side_effect=fail_unreadable), self.assertRaises(PermissionError):
				capture_graph_inputs(game_root)

	def test_graph_assembly_uses_captured_bytes_and_verification_rejects_changed_bytes(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			game_root = Path(temp_dir) / "game"
			make_fixture_game_repo(game_root)
			inputs = capture_graph_inputs(game_root)
			before = build_content_graph_from_inputs(inputs)
			core = game_root / "code/modules/shuttle/shuttle.dm"
			core.write_text("// ordinary source with no marker\n", encoding="utf-8")
			self.assertEqual(build_content_graph_from_inputs(inputs), before)
			# Even if the metadata observation is restored, publication must check the raw bytes.
			stamps = dict(inputs.inventory.file_stamps)
			with (
				patch("tools.content_graph.inputs.observe_graph_inputs", return_value=inputs.inventory),
				patch("tools.content_graph.inputs._stamp", side_effect=lambda path: stamps[path.relative_to(game_root).as_posix()]),
				self.assertRaisesRegex(ValueError, "source changed"),
			):
				verify_graph_inputs(game_root, inputs)

	def test_markerless_input_changes_and_missing_mirrors_are_part_of_source(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			game_root = Path(temp_dir) / "game"
			make_fixture_game_repo(game_root)
			core = game_root / "code/markerless.dm"
			core.write_bytes(b"// no marker\n\xff")
			mirror = game_root / "code/modules/shuttle/shuttle.dm"
			mirror.unlink()
			before = capture_graph_inputs(game_root)
			self.assertIsNone(dict(before.inventory.file_stamps)["code/modules/shuttle/shuttle.dm"])
			core.write_bytes(b"// no marker\n\xfe")
			after = capture_graph_inputs(game_root)
			self.assertNotEqual(before.source_sha256, after.source_sha256)
			mirror.write_text("// restored\n", encoding="utf-8")
			self.assertNotEqual(after.inventory.observation, observe_graph_inputs(game_root).observation)

	def test_source_change_before_activation_preserves_the_previous_graph(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			tool_root, game_root = root / "tool", root / "game"
			tool_root.mkdir()
			make_fixture_game_repo(game_root)
			run_git(game_root, "init", "--initial-branch=main")
			run_git(game_root, "config", "user.name", "Writer")
			run_git(game_root, "config", "user.email", "writer@example.invalid")
			run_git(game_root, "add", "--all")
			run_git(game_root, "commit", "-m", "Fixture")
			scan_and_cache_content_graph(tool_root, game_root)
			before = active_projection_metadata(tool_root)
			cached = read_graph_cache(tool_root)
			original_upsert = db.upsert_rows

			def change_source_after_manifest(*args, **kwargs):
				result = original_upsert(*args, **kwargs)
				if any(row.get("id") == "graph-health" for row in args[2]):
					(game_root / "code/new-source.dm").write_text("// APHELION EDIT - late\n", encoding="utf-8")
				return result

			with patch("tools.content_graph.graph.db.upsert_rows", side_effect=change_source_after_manifest), self.assertRaisesRegex(ValueError, "source changed"):
				scan_and_cache_content_graph(tool_root, game_root)
			self.assertEqual(active_projection_metadata(tool_root), before)
			self.assertEqual(read_graph_cache(tool_root), cached)

	def test_build_content_graph_produces_expected_nodes_and_edges(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			game_root = Path(temp_dir) / "game"
			make_fixture_game_repo(game_root)

			graph = build_content_graph(game_root)

		node_kinds = [node["kind"] for node in graph["nodes"]]
		self.assertEqual(2, node_kinds.count("module"))
		self.assertEqual(1, node_kinds.count("master_file"))
		self.assertEqual(2, node_kinds.count("core_file"))

		module_ids = {node["id"] for node in graph["nodes"] if node["kind"] == "module"}
		self.assertIn("module:nova:shuttle_toggle", module_ids)
		self.assertIn("module:nova:no_readme_module", module_ids)

		readme_flags = {node["module_id"]: node["has_readme"] for node in graph["nodes"] if node["kind"] == "module"}
		self.assertTrue(readme_flags["shuttle_toggle"])
		self.assertFalse(readme_flags["no_readme_module"])

		mirror_edges = [edge for edge in graph["edges"] if edge["relation"] == "master_files_mirror"]
		self.assertEqual(1, len(mirror_edges))
		self.assertEqual("core_file:code/modules/shuttle/shuttle.dm", mirror_edges[0]["target"])

		marker_edges = [edge for edge in graph["edges"] if edge["relation"] == "marker_edit"]
		self.assertEqual(1, len(marker_edges))
		self.assertEqual("module:nova:shuttle_toggle", marker_edges[0]["source"])
		self.assertEqual("core_file:code/modules/shuttle/shuttle.dm", marker_edges[0]["target"])
		self.assertEqual("addition", marker_edges[0]["edit_type"])

		self.assertEqual(1, len(graph["unresolved_markers"]))
		self.assertEqual("code/modules/other/other.dm", graph["unresolved_markers"][0]["core_file"])
		self.assertEqual("unattributed", graph["unresolved_markers"][0]["attribution"])

		self.assertEqual(2, graph["counts"]["module_count"])
		self.assertEqual(1, graph["counts"]["master_files_count"])
		self.assertEqual(2, graph["counts"]["marker_count"])
		self.assertEqual(1, graph["counts"]["unresolved_marker_count"])

		module_reference_edges = [edge for edge in graph["edges"] if edge["relation"] == "module_reference"]
		self.assertEqual(1, len(module_reference_edges))
		self.assertEqual("module:nova:shuttle_toggle", module_reference_edges[0]["source"])
		self.assertEqual("module:nova:no_readme_module", module_reference_edges[0]["target"])

		core_reference_edges = [edge for edge in graph["edges"] if edge["relation"] == "core_reference"]
		self.assertEqual(1, len(core_reference_edges))
		self.assertEqual("core_file:code/modules/other/other.dm", core_reference_edges[0]["source"])
		self.assertEqual("core_file:code/modules/shuttle/shuttle.dm", core_reference_edges[0]["target"])

		self.assertEqual(2, graph["counts"]["reference_count"])

		module_nodes = {node["module_id"]: node for node in graph["nodes"] if node["kind"] == "module"}
		self.assertEqual(1, module_nodes["shuttle_toggle"]["file_count"])
		self.assertGreater(module_nodes["shuttle_toggle"]["total_bytes"], 0)
		self.assertEqual(0, module_nodes["no_readme_module"]["file_count"])

		core_file_nodes = {node["path"]: node for node in graph["nodes"] if node["kind"] == "core_file"}
		self.assertIsNotNone(core_file_nodes["code/modules/shuttle/shuttle.dm"]["size_bytes"])
		self.assertGreater(core_file_nodes["code/modules/shuttle/shuttle.dm"]["line_count"], 0)

		master_file_nodes = [node for node in graph["nodes"] if node["kind"] == "master_file"]
		self.assertIsNotNone(master_file_nodes[0]["size_bytes"])

	def test_full_tree_connects_every_tracked_file_without_duplicating_specialized_nodes(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			game_root = Path(temp_dir) / "game"
			make_fixture_game_repo(game_root)

			graph = build_content_graph(game_root)

		nodes_by_id = {node["id"]: node for node in graph["nodes"]}
		self.assertIn("dir:.", nodes_by_id)
		self.assertEqual("directory", nodes_by_id["dir:."]["kind"])

		# non-modular content becomes generic file/directory nodes
		self.assertIn("file:README.md", nodes_by_id)
		self.assertIn("file:.github/workflows/ci.yml", nodes_by_id)
		self.assertIn("dir:.github/workflows", nodes_by_id)
		self.assertIn("file:icons/obj/example.dmi", nodes_by_id)

		# every path is reachable from the root via exactly one parent "contains" edge
		contains_edges = [edge for edge in graph["edges"] if edge["relation"] == "contains"]
		parent_by_child = {edge["target"]: edge["source"] for edge in contains_edges}
		self.assertIn("file:README.md", parent_by_child)
		self.assertEqual("dir:.", parent_by_child["file:README.md"])
		self.assertIn("dir:.github", parent_by_child)

		# module/master_file/core_file paths are wired into the tree, not duplicated as file:/dir: nodes
		self.assertIn("module:nova:shuttle_toggle", parent_by_child)
		self.assertNotIn("dir:modular_nova/modules/shuttle_toggle", nodes_by_id)
		self.assertIn("core_file:code/modules/shuttle/shuttle.dm", parent_by_child)
		self.assertNotIn("file:code/modules/shuttle/shuttle.dm", nodes_by_id)

		self.assertGreater(graph["counts"]["file_count"], 0)
		self.assertGreater(graph["counts"]["directory_count"], 0)

	def test_scan_and_cache_writes_atomically_readable_cache(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			tool_root = root / "tool"
			game_root = root / "game"
			(tool_root / "tools/lore_editor/catalog").mkdir(parents=True)
			make_fixture_game_repo(game_root)
			run_git(game_root, "init", "--initial-branch=main")
			run_git(game_root, "config", "user.name", "Writer")
			run_git(game_root, "config", "user.email", "writer@example.invalid")
			run_git(game_root, "add", "--all")
			run_git(game_root, "commit", "-m", "Initial")

			manifest = scan_and_cache_content_graph(tool_root, game_root)

			self.assertEqual(2, manifest.module_count)
			self.assertEqual(1, manifest.master_files_count)
			self.assertEqual(2, manifest.marker_count)
			self.assertGreater(manifest.file_count, 0)
			self.assertGreater(manifest.directory_count, 0)
			self.assertNotEqual("unknown", manifest.game_repo_revision)
			compact_manifest = decode(db.get_row_by_key(table(tool_root, "manifests"), "id", "graph-health"))
			self.assertEqual(compact_manifest, manifest.to_dict())

			cached = read_graph_cache(tool_root)
			self.assertIsNotNone(cached)
			graph, cached_manifest = cached
			self.assertEqual(manifest.snapshot_sha256, cached_manifest.snapshot_sha256)
			self.assertEqual(2, len([node for node in graph["nodes"] if node["kind"] == "module"]))

			with patch("tools.content_graph.graph.db.all_rows", side_effect=AssertionError("snapshot should be self-contained")):
				graph_from_snapshot, _manifest = read_graph_cache(tool_root)
			self.assertEqual(graph, graph_from_snapshot)

	def test_failed_scan_preserves_active_graph_generation_and_tables(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			tool_root = root / "tool"
			game_root = root / "game"
			(tool_root / "tools/lore_editor/catalog").mkdir(parents=True)
			make_fixture_game_repo(game_root)
			run_git(game_root, "init", "--initial-branch=main")
			run_git(game_root, "config", "user.name", "Writer")
			run_git(game_root, "config", "user.email", "writer@example.invalid")
			run_git(game_root, "add", "--all")
			run_git(game_root, "commit", "-m", "Initial")
			scan_and_cache_content_graph(tool_root, game_root)

			active_before = active_projection_metadata(tool_root)
			cache_before = read_graph_cache(tool_root)

			def table_snapshot(name: str) -> list[tuple[str, str]]:
				return sorted(
					(str(row["id"]), str(row["raw_json"]))
					for row in db.all_rows(table(tool_root, name))
				)

			tables_before = {name: table_snapshot(name) for name in ("graph_nodes", "graph_edges", "unresolved_markers")}
			new_module = game_root / "modular_nova/modules/new_module/code/new_module.dm"
			new_module.parent.mkdir(parents=True)
			new_module.write_text("/obj/new_module\n", encoding="utf-8")
			run_git(game_root, "add", "--all")
			run_git(game_root, "commit", "-m", "Add graph content")

			original_sync = db.sync_snapshot
			call_count = 0

			def fail_on_second_sync(*args, **kwargs):
				nonlocal call_count
				call_count += 1
				if call_count == 2:
					raise RuntimeError("graph publication interrupted")
				return original_sync(*args, **kwargs)

			with patch("tools.content_graph.graph.db.sync_snapshot", side_effect=fail_on_second_sync), self.assertRaisesRegex(RuntimeError, "graph publication interrupted"):
				scan_and_cache_content_graph(tool_root, game_root)

			self.assertGreaterEqual(call_count, 2)
			self.assertEqual(active_projection_metadata(tool_root), active_before)
			self.assertEqual(read_graph_cache(tool_root), cache_before)
			self.assertEqual(
				{name: table_snapshot(name) for name in tables_before},
				tables_before,
			)

	def test_scan_reconciles_external_canonical_changes_before_publishing_graph(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			tool_root = root / "tool"
			game_root = root / "game"
			(tool_root / "tools/lore_editor/catalog").mkdir(parents=True)
			make_fixture_game_repo(game_root)
			run_git(game_root, "init", "--initial-branch=main")
			run_git(game_root, "config", "user.name", "Writer")
			run_git(game_root, "config", "user.email", "writer@example.invalid")
			run_git(game_root, "add", "--all")
			run_git(game_root, "commit", "-m", "Initial")
			scan_and_cache_content_graph(tool_root, game_root)

			atomic_write_record(record_path(tool_root, "group", "items"), {
				"id": "items",
				"label": "Items",
				"color": "#fff",
				"keywords": [],
				"type_path_prefixes": [],
			})

			scan_and_cache_content_graph(tool_root, game_root)

			active = active_projection_metadata(tool_root)
			self.assertIsNotNone(active)
			self.assertEqual(active.revision.content_revision, scan_canonical_records(tool_root).content_revision)
			group = db.get_row_by_key(table(tool_root, "groups"), "id", "items")
			self.assertIsNotNone(group)

	def test_graph_cache_pins_fallback_table_reads_to_one_generation(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			tool_root = root / "tool"
			game_root = root / "game"
			(tool_root / "tools/lore_editor/catalog").mkdir(parents=True)
			make_fixture_game_repo(game_root)
			run_git(game_root, "init", "--initial-branch=main")
			run_git(game_root, "config", "user.name", "Writer")
			run_git(game_root, "config", "user.email", "writer@example.invalid")
			run_git(game_root, "add", "--all")
			run_git(game_root, "commit", "-m", "Initial")
			scan_and_cache_content_graph(tool_root, game_root)

			from tools.lore_editor.tests.store_helpers import fixture_table

			with fixture_table(tool_root, "manifests") as manifest_table:
				stored = decode(db.get_row_by_key(manifest_table, "id", "graph"))
				stored.pop("graph")
				db.upsert_rows(manifest_table, "id", [{"id": "graph", "raw_json": encode(stored), "text": ""}])
			pinned_store = db.store_path(tool_root)

			with patch("tools.content_graph.graph.table", wraps=table) as table_spy:
				cached = read_graph_cache(tool_root)

			self.assertIsNotNone(cached)
			self.assertGreaterEqual(table_spy.call_count, 4)
			self.assertTrue(all(call.kwargs.get("store_dir") == pinned_store for call in table_spy.call_args_list))

	def test_read_graph_cache_returns_none_when_never_scanned(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			tool_root = Path(temp_dir)
			(tool_root / "tools/lore_editor/catalog").mkdir(parents=True)

			self.assertIsNone(read_graph_cache(tool_root))

	def test_scan_rejects_game_repository_missing_marker_file(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			tool_root = root / "tool"
			game_root = root / "game"
			(tool_root / "tools/lore_editor/catalog").mkdir(parents=True)
			game_root.mkdir(parents=True)

			with self.assertRaisesRegex(ValueError, "does not look like a Meridian-Rift checkout"):
				scan_and_cache_content_graph(tool_root, game_root)


if __name__ == "__main__":
	unittest.main()

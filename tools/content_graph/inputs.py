from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

from webapp.git_adapter import GitAdapterError, list_tracked_files
from webapp.json_storage import canonical_json_bytes
from webapp.path_safety import resolve_repo_path

from .scanner import (
	CORE_SCAN_ROOT,
	FULL_TREE_WALK_EXCLUDED_DIR_NAMES,
	MARKER_FILE_SUFFIXES,
	MASTER_FILES_ROOTS,
	MODULE_ROOTS,
	MasterFileNode,
	ModuleNode,
)


@dataclass(frozen=True)
class GraphInventory:
	modules: tuple[ModuleNode, ...]
	master_files: tuple[MasterFileNode, ...]
	master_sizes: tuple[tuple[str, int], ...]
	tracked_paths: tuple[str, ...]
	module_paths: tuple[tuple[str, str], ...]
	core_paths: tuple[str, ...]
	file_stamps: tuple[tuple[str, tuple[int, ...] | None], ...]
	observation: str

	def source_metadata(self) -> dict[str, object]:
		return {
			"modules": [asdict(module) for module in self.modules],
			"master_files": [asdict(master) for master in self.master_files],
			"master_sizes": self.master_sizes,
			"tracked_paths": self.tracked_paths,
			"module_paths": self.module_paths,
			"core_paths": self.core_paths,
		}


@dataclass(frozen=True)
class GraphInputs:
	inventory: GraphInventory
	files: tuple[tuple[str, bytes], ...]
	source_sha256: str


def _stamp(path: Path) -> tuple[int, ...] | None:
	try:
		value = path.stat()
	except FileNotFoundError:
		return None
	return _file_stamp(value)


def _file_stamp(value: os.stat_result) -> tuple[int, ...]:
	# Windows directory entries provide these fields without another file open. Inode/device
	# are not populated consistently by scandir there; explicit builds prove bytes separately.
	return (value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _source_directory(root: Path, relative_root: Path) -> Path | None:
	start = resolve_repo_path(root, relative_root)
	if start != root / relative_root:
		raise ValueError("Graph source directories must not contain aliases.")
	try:
		mode = start.stat().st_mode
	except FileNotFoundError:
		return None
	if not stat.S_ISDIR(mode):
		raise ValueError(f"Graph source directory is not a directory: {relative_root.as_posix()}")
	return start


def _entry_stat(entry: os.DirEntry[str]) -> os.stat_result:
	value = entry.stat(follow_symlinks=False)
	# Windows scandir already has these attributes; resolving every file and ancestor instead
	# makes the freshness poll much more expensive. Byte reads still resolve containment.
	if stat.S_ISLNK(value.st_mode) or getattr(value, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
		raise ValueError("Graph source paths must not contain aliases.")
	return value


def _source_files(root: Path, relative_root: Path, *, excluded: frozenset[str] = frozenset()) -> Iterator[tuple[str, os.stat_result]]:
	start = _source_directory(root, relative_root)
	if start is None:
		return
	pending = [(str(start), "" if relative_root == Path(".") else relative_root.as_posix())]
	while pending:
		# Unlike Path.rglob, scandir propagates unreadable-subtree errors on all supported Python
		# versions. An omitted input must never be published as a verified absence.
		directory, relative_directory = pending.pop()
		with os.scandir(directory) as entries:
			for entry in entries:
				if entry.name in excluded:
					continue
				value = _entry_stat(entry)
				relative = f"{relative_directory}/{entry.name}" if relative_directory else entry.name
				if stat.S_ISDIR(value.st_mode):
					pending.append((entry.path, relative))
				elif stat.S_ISREG(value.st_mode):
					yield relative, value


def _modules(root: Path) -> tuple[ModuleNode, ...]:
	modules: list[ModuleNode] = []
	for owner, relative in MODULE_ROOTS:
		start = _source_directory(root, relative)
		if start is None:
			continue
		with os.scandir(start) as entries:
			for entry in sorted(entries, key=lambda item: item.name):
				if not stat.S_ISDIR(_entry_stat(entry).st_mode):
					continue
				path = Path(entry.path)
				try:
					readme = stat.S_ISREG((path / "readme.md").stat().st_mode)
				except FileNotFoundError:
					readme = False
				modules.append(ModuleNode(entry.name, owner, (relative / entry.name).as_posix(), readme))
	return tuple(modules)


def _tracked_paths(root: Path) -> tuple[str, ...]:
	try:
		return list_tracked_files(root)
	except GitAdapterError:
		if (root / ".git").exists():
			raise
		return tuple(sorted(path for path, _ in _source_files(root, Path("."), excluded=FULL_TREE_WALK_EXCLUDED_DIR_NAMES)))


def observe_graph_inputs(game_root: Path) -> GraphInventory:
	"""Observe topology and file metadata without reading source bytes or parsing markers.

	The signature detects ordinary edits, including ignored inputs. It is a UI freshness hint,
	not byte verification or authority to write; explicit builds verify source bytes separately.
	"""
	root = game_root.resolve()
	modules = _modules(root)
	masters = [
		(MasterFileNode(owner, path, path[len(relative_root.as_posix()) + 1:]), value.st_size)
		for owner, relative_root in MASTER_FILES_ROOTS
		for path, value in sorted(_source_files(root, relative_root))
	]
	master_files = tuple(master for master, _ in masters)
	file_stamps: dict[str, tuple[int, ...] | None] = {}
	module_paths_list: list[tuple[str, str]] = []
	for module in modules:
		for path, value in sorted(_source_files(root, Path(module.path))):
			if os.path.splitext(path)[1].casefold() in MARKER_FILE_SUFFIXES:
				module_paths_list.append((module.path, path))
				file_stamps[path] = _file_stamp(value)
	module_paths = tuple(module_paths_list)
	core_set = set()
	for path, value in _source_files(root, CORE_SCAN_ROOT):
		if os.path.splitext(path)[1].casefold() in MARKER_FILE_SUFFIXES:
			core_set.add(path)
			file_stamps[path] = _file_stamp(value)
	for master in master_files:
		core_set.add(master.core_path)
		if master.core_path not in file_stamps:
			file_stamps[master.core_path] = _stamp(root / master.core_path)
	core_paths = tuple(sorted(core_set))
	stamps = tuple(sorted(file_stamps.items()))
	master_sizes = tuple((master.path, size) for master, size in masters)
	inventory = GraphInventory(
		modules, master_files, master_sizes, _tracked_paths(root), module_paths, core_paths, stamps, "",
	)
	observation = hashlib.sha256(canonical_json_bytes({
		**inventory.source_metadata(), "file_stamps": stamps,
	})).hexdigest()
	return GraphInventory(
		modules, master_files, master_sizes, inventory.tracked_paths, module_paths, core_paths, stamps, observation,
	)


def _source_hash(inventory: GraphInventory, digests: list[tuple[str, str | None]]) -> str:
	return hashlib.sha256(canonical_json_bytes({**inventory.source_metadata(), "file_hashes": digests})).hexdigest()


def capture_graph_inputs(game_root: Path) -> GraphInputs:
	root = game_root.resolve()
	inventory = observe_graph_inputs(root)
	files: list[tuple[str, bytes]] = []
	digests: list[tuple[str, str | None]] = []
	for relative, stamp in inventory.file_stamps:
		if stamp is None:
			digests.append((relative, None))
			continue
		path = resolve_repo_path(root, Path(relative))
		data = path.read_bytes()
		if _stamp(path) != stamp:
			raise ValueError("Game source changed during graph capture. Run the scan again.")
		files.append((relative, data))
		digests.append((relative, hashlib.sha256(data).hexdigest()))
	return GraphInputs(inventory, tuple(files), _source_hash(inventory, digests))


def verify_graph_inputs(game_root: Path, inputs: GraphInputs) -> None:
	"""Recheck the captured bytes immediately before publication, without retaining another copy."""
	root = game_root.resolve()
	inventory = observe_graph_inputs(root)
	if inventory.observation != inputs.inventory.observation:
		raise ValueError("Game source changed during graph generation. Run the scan again.")
	digests: list[tuple[str, str | None]] = []
	for relative, stamp in inventory.file_stamps:
		if stamp is None:
			digests.append((relative, None))
			continue
		path = resolve_repo_path(root, Path(relative))
		with path.open("rb") as stream:
			digest = hashlib.file_digest(stream, "sha256").hexdigest()
		if _stamp(path) != stamp:
			raise ValueError("Game source changed during graph verification. Run the scan again.")
		digests.append((relative, digest))
	if _source_hash(inventory, digests) != inputs.source_sha256 or observe_graph_inputs(root).observation != inventory.observation:
		raise ValueError("Game source changed during graph verification. Run the scan again.")

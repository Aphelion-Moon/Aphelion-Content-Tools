from __future__ import annotations

from dataclasses import asdict
from enum import Enum
from pathlib import Path

from tools.lore_editor.reconcile import scan_canonical_records
from webapp.git_adapter import GameSourceRevision, observe_game_source
from webapp.manifest_base import MANIFEST_FORMAT_VERSION

from . import db
from .embeddings import embedding_status
from .lifecycle import selected_projection, with_projection_read
from .metadata import ActiveProjection, projection_status, projection_table_paths
from .schema import TABLE_SCHEMAS, decode, table


def _directory_stats(path: Path) -> tuple[int, float | None]:
	"""Total size in bytes and the most recent mtime among every file under `path`.

	Computed straight from disk rather than from any in-memory counter: tool runs execute inside the
	persistent store worker process (`webapp/store_worker.py`), a different process from the one serving
	`/api/store/health` (the main HTTP server, see `webapp/server.py`), so an in-memory "last write"
	timestamp kept by one process would never see the other's writes. File mtimes are correct regardless
	of which process wrote them.
	"""
	if not path.exists():
		return 0, None
	total_size = 0
	latest_mtime: float | None = None
	for entry in path.rglob("*"):
		if not entry.is_file():
			continue
		stat = entry.stat()
		total_size += stat.st_size
		if latest_mtime is None or stat.st_mtime > latest_mtime:
			latest_mtime = stat.st_mtime
	return total_size, latest_mtime


def _game_dataset_health(
	repo_root: Path,
	kind: str,
	selected_revision: str | None,
	*,
	store_dir: Path,
	selected_source: GameSourceRevision | None = None,
) -> dict[str, object]:
	# Graph delivery includes the complete graph; polling only needs its compact manifest.
	manifest_key = "graph-health" if kind == "graph" else kind
	row = db.get_row_by_key(table(repo_root, "manifests", store_dir=store_dir), "id", manifest_key)
	if row is None:
		return {
			"kind": kind,
			"required": True,
			"state": "missing",
			"current": False,
			"source_revision": None,
			"selected_revision": selected_revision,
			"schema_version": None,
			"content_sha256": None,
			"reason": "Graph freshness metadata is unavailable. Refresh the Content Graph." if kind == "graph" else f"No {kind} dataset is active.",
		}
	payload = decode(row)
	manifest = payload.get("manifest") if isinstance(payload.get("manifest"), dict) else payload
	assert isinstance(manifest, dict)
	source_revision = manifest.get("game_repo_revision")
	current = isinstance(source_revision, str) and selected_revision is not None and source_revision == selected_revision
	reason = None if current else f"The {kind} dataset was built from a different game revision."
	if current and manifest.get("format_version") != MANIFEST_FORMAT_VERSION:
		current, reason = False, f"The {kind} dataset schema is unsupported. Rebuild the dataset."
	if current and kind == "graph":
		observation = manifest.get("source_observation")
		if not isinstance(observation, str) or not isinstance(manifest.get("source_sha256"), str):
			current, reason = False, "Graph source provenance is unavailable. Refresh the Content Graph."
		elif selected_source is None or observation != selected_source.graph_observation:
			current, reason = False, "Game source files changed after the Content Graph scan. Refresh the Content Graph."
	if current and kind == "catalog":
		if manifest.get("source_provenance") != "release-seed":
			current, reason = False, "This catalog's game-source version is unverified. Local build output remains available for authoring."
		elif selected_source is None or selected_source.dirty is not False:
			current, reason = False, "The selected game checkout has unverified working changes; catalog freshness requires a clean source revision."
	return {
		"kind": kind,
		"required": True,
		"state": "current" if current else "stale",
		"current": current,
		"source_revision": source_revision if isinstance(source_revision, str) else None,
		"selected_revision": selected_revision,
		"schema_version": manifest.get("format_version") if isinstance(manifest.get("format_version"), int) else None,
		"content_sha256": manifest.get("snapshot_sha256") if isinstance(manifest.get("snapshot_sha256"), str) else None,
		"reason": reason,
	}


class _SourceObservation(Enum):
	OMITTED = "omitted"


@with_projection_read
def store_health(repo_root: Path, game_repo_root: Path | None = None, *, game_source: GameSourceRevision | None | _SourceObservation = _SourceObservation.OMITTED) -> dict[str, object]:
	"""A small snapshot of the store itself -- row counts, on-disk size, and staleness -- for the
	"Database and Git" panel's health readout. Answers "what is actually in this database" directly,
	rather than leaving it as a black box behind a handful of job buttons."""
	pinned_projection: ActiveProjection = selected_projection(repo_root)
	pinned_store = pinned_projection.path
	tables = {}
	for name in TABLE_SCHEMAS:
		opened = table(repo_root, name, store_dir=pinned_store)
		tables[name] = opened.count_rows() if opened is not None else 0
	stats = [_directory_stats(path) for path in set(projection_table_paths(repo_root, pinned_projection).values())]
	disk_bytes = sum(size for size, _ in stats)
	last_write_time = max((modified for _, modified in stats if modified is not None), default=None)
	semantic_status = embedding_status(initialize=False)
	canonical_snapshot = scan_canonical_records(repo_root)
	projection = projection_status(repo_root, canonical_snapshot.content_revision, active=pinned_projection)
	selected_game_revision: str | None = None
	game_datasets: list[dict[str, object]] = []
	if game_repo_root is not None:
		selected_source = observe_game_source(game_repo_root) if game_source is _SourceObservation.OMITTED else game_source
		selected_game_revision = selected_source.head if selected_source else None
		game_datasets = [
			_game_dataset_health(repo_root, "catalog", selected_game_revision, store_dir=pinned_store, selected_source=selected_source),
			_game_dataset_health(repo_root, "graph", selected_game_revision, store_dir=pinned_store, selected_source=selected_source),
		]
	lore_dataset = {
		"kind": "lore",
		"required": True,
		"state": "current" if projection.current else "stale",
		"current": projection.current,
		"source_revision": canonical_snapshot.content_revision,
		"selected_revision": canonical_snapshot.content_revision,
		"schema_version": projection.active.revision.schema_version if projection.active is not None else None,
		"content_sha256": canonical_snapshot.content_revision,
		"reason": projection.reason,
	}
	datasets = [lore_dataset, *game_datasets]
	workspace_current = all(bool(dataset["current"]) for dataset in datasets if dataset["required"])
	workspace_reasons = [str(dataset["reason"]) for dataset in datasets if dataset["required"] and dataset["reason"]]
	return {
		"tables": tables,
		"total_rows": sum(tables.values()),
		"disk_bytes": disk_bytes,
		"last_write_time": last_write_time,
		"semantic_search": {
			"mode": "hybrid" if semantic_status.available else "keyword-only",
			"model_id": semantic_status.model_id,
			"reason": semantic_status.reason,
		},
		"projection": {
			"current": projection.current,
			"reason": projection.reason,
			"path": str(projection.path),
			"content_revision": canonical_snapshot.content_revision,
			"active": {"generation_id": projection.active.generation_id, "revision": asdict(projection.active.revision)} if projection.active is not None else None,
		},
		"workspace": {
			"current": workspace_current,
			"reason": None if workspace_current else " ".join(workspace_reasons),
			"selected_game_revision": selected_game_revision,
			"datasets": datasets,
		},
	}

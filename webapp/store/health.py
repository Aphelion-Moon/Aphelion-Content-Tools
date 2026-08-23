from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from tools.lore_editor.reconcile import scan_canonical_records

from .db import store_path
from .embeddings import embedding_status
from .metadata import projection_status
from .schema import TABLE_SCHEMAS, table


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


def store_health(repo_root: Path) -> dict[str, object]:
	"""A small snapshot of the store itself -- row counts, on-disk size, and staleness -- for the
	"Database and Git" panel's health readout. Answers "what is actually in this database" directly,
	rather than leaving it as a black box behind a handful of job buttons."""
	tables = {name: table(repo_root, name).count_rows() for name in TABLE_SCHEMAS}
	disk_bytes, last_write_time = _directory_stats(store_path(repo_root))
	semantic_status = embedding_status()
	canonical_snapshot = scan_canonical_records(repo_root)
	projection = projection_status(repo_root, canonical_snapshot.content_revision)
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
			"active": asdict(projection.active) if projection.active is not None else None,
		},
	}

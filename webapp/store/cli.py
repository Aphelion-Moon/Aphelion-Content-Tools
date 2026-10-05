from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

if __package__ in (None, ""):
	sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
	from tools.lore_editor.reconcile import reconcile_projection, scan_canonical_records
	from tools.lore_editor.write_coordinator import repository_write_lock
	from webapp.store.db import SYNC_CHUNK_SIZE, embedding_hash_for, optimize_all_tables, with_embeddings
	from webapp.store.embeddings import EmbeddingUnavailableError, embeddings_available
	from webapp.store.generations import staged_projection
	from webapp.store.metadata import backup_projection, projection_status, restore_projection
	from webapp.store.schema import KEYWORD_ONLY_TABLES, TABLE_SCHEMAS, writable_table
else:
	from tools.lore_editor.reconcile import reconcile_projection, scan_canonical_records
	from tools.lore_editor.write_coordinator import repository_write_lock

	from .db import SYNC_CHUNK_SIZE, embedding_hash_for, optimize_all_tables, with_embeddings
	from .embeddings import EmbeddingUnavailableError, embeddings_available
	from .generations import staged_projection
	from .metadata import backup_projection, projection_status, restore_projection
	from .schema import KEYWORD_ONLY_TABLES, TABLE_SCHEMAS, writable_table


def rebuild_embeddings(repo_root: Path, *, on_progress=None) -> dict[str, int]:
	"""Re-embed every row's `text` column in every table -- useful after changing the embedding model,
	or to recover rows that were written while embeddings were unavailable (offline, declined download).

	Unlike a normal refresh/scan, this genuinely means to touch every row (the model changed, so every
	stored vector is stale) -- but it still chunks the work and reports progress so an operator can see
	it moving and isn't left staring at a silent console for a large table."""
	if not embeddings_available():
		raise EmbeddingUnavailableError("Embedding model is unavailable; existing vectors were preserved.")

	counts: dict[str, int] = {}
	with repository_write_lock(repo_root):
		reconcile_projection(repo_root)
		content_revision = scan_canonical_records(repo_root).content_revision
		with staged_projection(repo_root, content_revision=content_revision, changed_tables=TABLE_SCHEMAS.keys() - KEYWORD_ONLY_TABLES, embeddings_rebuilt=True) as staged:
			for name in TABLE_SCHEMAS:
				if name in KEYWORD_ONLY_TABLES:
					counts[name] = 0
					continue
				target_table = writable_table(repo_root, name, store_dir=staged.path)
				row_ids = [str(row["id"]) for row in target_table.search().select(["id"]).to_list()]
				if not row_ids:
					counts[name] = 0
					continue
				columns = [column for column in target_table.schema.names if column != "vector"]
				for start in range(0, len(row_ids), SYNC_CHUNK_SIZE):
					chunk_ids = row_ids[start:start + SYNC_CHUNK_SIZE]
					predicate = "id IN (" + ", ".join(_sql_string_literal(row_id) for row_id in chunk_ids) + ")"
					chunk = target_table.search().where(predicate).select(columns).to_list()
					re_embedded = with_embeddings([
						{**row, "embedding_hash": embedding_hash_for(str(row.get("text") or ""))}
						for row in chunk
					])
					target_table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(re_embedded)
					if on_progress is not None:
						on_progress(name, min(start + SYNC_CHUNK_SIZE, len(row_ids)), len(row_ids))
				counts[name] = len(row_ids)
	return counts


def _sql_string_literal(value: str) -> str:
	return "'" + value.replace("'", "''") + "'"


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Maintain the shared Aphelion Content Tools data store.")
	subparsers = parser.add_subparsers(dest="command", required=True)

	rebuild_parser = subparsers.add_parser("rebuild-embeddings", help="Re-embed every table's search text.")
	rebuild_parser.add_argument("--repo-root", type=Path, required=True)

	optimize_parser = subparsers.add_parser(
		"optimize", help="Compact fragments, prune old versions, and reindex every table (LanceDB maintenance)."
	)
	optimize_parser.add_argument("--repo-root", type=Path, required=True)

	for command, help_text in (
		("status", "Report whether the active projection matches canonical Git records."),
		("reconcile", "Build and atomically activate a projection of canonical Git records."),
		("rebuild", "Force a fresh atomic projection generation."),
	):
		command_parser = subparsers.add_parser(command, help=help_text)
		command_parser.add_argument("--repo-root", type=Path, required=True)

	backup_parser = subparsers.add_parser("backup", help="Copy the active projection to a labeled recovery snapshot.")
	backup_parser.add_argument("--repo-root", type=Path, required=True)
	backup_parser.add_argument("--output", type=Path, required=True)
	backup_parser.add_argument("--label", required=True)

	restore_parser = subparsers.add_parser("restore", help="Activate a labeled recovery snapshot as stale projection data.")
	restore_parser.add_argument("--repo-root", type=Path, required=True)
	restore_parser.add_argument("--backup", type=Path, required=True)

	return parser


def main(argv: list[str] | None = None) -> int:
	args = build_parser().parse_args(argv)
	try:
		if args.command == "status":
			snapshot = scan_canonical_records(args.repo_root.resolve())
			status = projection_status(args.repo_root.resolve(), snapshot.content_revision)
			print(json.dumps({
				"current": status.current,
				"reason": status.reason,
				"path": str(status.path),
				"content_revision": snapshot.content_revision,
				"active": asdict(status.active) if status.active is not None else None,
			}, sort_keys=True))
			return 0
		if args.command in ("reconcile", "rebuild"):
			result = reconcile_projection(args.repo_root.resolve(), rebuild=args.command == "rebuild")
			print(json.dumps({
				"counts": result.counts,
				"content_revision": result.content_revision,
				"projection_revision": asdict(result.projection_revision),
			}, sort_keys=True))
			return 0
		if args.command == "backup":
			path = backup_projection(args.repo_root.resolve(), args.output, label=args.label)
			print(json.dumps({"backup": str(path), "label": args.label}, sort_keys=True))
			return 0
		if args.command == "restore":
			metadata = restore_projection(args.repo_root.resolve(), args.backup)
			print(json.dumps({
				"generation_id": metadata.generation_id,
				**asdict(metadata.revision),
			}, sort_keys=True))
			return 0
		if args.command == "rebuild-embeddings":
			def _report_progress(name: str, done: int, total: int) -> None:
				print(f"{name}: embedded {done}/{total}...", flush=True)

			counts = rebuild_embeddings(args.repo_root.resolve(), on_progress=_report_progress)
			for name, count in counts.items():
				print(f"{name}: re-embedded {count} row(s).")
			return 0
		if args.command == "optimize":
			def _report_progress(name: str, done: int, total: int) -> None:
				print(f"Optimized {name} ({done}/{total})...", flush=True)

			names = optimize_all_tables(args.repo_root.resolve(), on_progress=_report_progress)
			print(f"Optimized {len(names)} table(s).")
			return 0
	except (EmbeddingUnavailableError, OSError, ValueError) as exc:
		print(f"error: {exc}", file=sys.stderr)
		return 1
	return 2


if __name__ == "__main__":
	raise SystemExit(main())

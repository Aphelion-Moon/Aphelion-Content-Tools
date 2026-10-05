from __future__ import annotations

import shutil
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from pathlib import Path

from tools.lore_editor.write_coordinator import repository_write_lock

from . import db
from .lifecycle import retire_projections
from .metadata import (
	ProjectionMetadata,
	activate_projection,
	active_projection,
	new_projection_metadata,
	projection_path,
	projection_table_paths,
	write_projection_marker,
)


@dataclass
class _WritableStage:
	names: frozenset[str]
	active: bool = True

	def require_active(self) -> None:
		if not self.active:
			raise ValueError("Projection write stage has finished.")


_writable_stages: ContextVar[dict[Path, _WritableStage] | None] = ContextVar("writable_projection_stages", default=None)


@dataclass
class StagedProjection:
	path: Path
	metadata: ProjectionMetadata


def require_staged_table(path: Path, name: str) -> _WritableStage:
	stage = (_writable_stages.get() or {}).get(path.resolve())
	if stage is None or name not in stage.names:
		raise ValueError(f"Table '{name}' is not declared writable in this projection stage.")
	return stage


@contextmanager
def staged_projection(
	repo_root: Path, *, content_revision: str, changed_tables: Iterable[str] | None = None, embeddings_rebuilt: bool = False,
) -> Iterator[StagedProjection]:
	"""Copy changed tables; publish a flat map to immutable owners for the rest."""
	from .schema import KEYWORD_ONLY_TABLES, TABLE_SCHEMAS

	resolved_root = repo_root.resolve()
	changed = frozenset(TABLE_SCHEMAS if changed_tables is None else changed_tables)
	if changed - TABLE_SCHEMAS.keys():
		raise ValueError("Projection stage declares an unknown table.")
	if embeddings_rebuilt and (TABLE_SCHEMAS.keys() - KEYWORD_ONLY_TABLES) - changed:
		raise ValueError("An embedding rebuild must update every semantic table.")
	with repository_write_lock(resolved_root):
		metadata = new_projection_metadata(content_revision)
		destination = projection_path(resolved_root, metadata.generation_id)
		source = active_projection(resolved_root)
		if source.metadata is not None and not embeddings_rebuilt:
			# Partial writes and compaction cannot certify untouched vectors from an older model.
			metadata = replace(metadata, revision=replace(metadata.revision, embedding_model_id=source.metadata.revision.embedding_model_id))
		sources = projection_table_paths(resolved_root, source)
		migrating = source.metadata is None or source.metadata.table_owners is None or source.metadata.revision.schema_version != metadata.revision.schema_version
		copy_names = set(sources) if migrating else changed & sources.keys()
		owners = dict(source.metadata.table_owners or {}) if source.metadata is not None else {}
		token = None
		writable = _WritableStage(changed)
		try:
			destination.mkdir(parents=True, exist_ok=False)
			for name in copy_names:
				shutil.copytree(sources[name], destination / f"{name}.lance")
				owners[name] = metadata.generation_id
				if name in TABLE_SCHEMAS:
					db.get_or_create_table(resolved_root, name, TABLE_SCHEMAS[name], store_dir=destination)
			metadata = replace(metadata, table_owners=owners)
			staged = StagedProjection(path=destination, metadata=metadata)
			token = _writable_stages.set({**(_writable_stages.get() or {}), destination: writable})
			yield staged
			writable.active = False
			metadata = replace(metadata, table_owners={
				**owners,
				**{name: metadata.generation_id for name in changed if (destination / f"{name}.lance").is_dir()},
			})
			staged.metadata = metadata
			write_projection_marker(resolved_root, metadata)
			activate_projection(resolved_root, metadata)
		except Exception:
			db.discard_connection(destination)
			shutil.rmtree(destination, ignore_errors=True)
			raise
		finally:
			writable.active = False
			if token is not None:
				_writable_stages.reset(token)
		retire_projections(resolved_root)

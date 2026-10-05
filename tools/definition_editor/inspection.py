from __future__ import annotations

import hashlib
from pathlib import Path

from webapp.path_safety import resolve_repo_path

from .models import Definition, SourceExcerpt
from .source import decode_source


def source_excerpt(root: Path, definition: Definition, catalog_id: str, member: str | None) -> SourceExcerpt:
	span = definition.source or next(iter(definition.occurrences), None)
	if member:
		span = next((field.source for field in definition.fields if field.name == member), None)
	if span is None:
		raise ValueError('This occurrence has no qualified physical source range.')
	data = resolve_repo_path(root, Path(span.path)).read_bytes()
	if hashlib.sha256(data).hexdigest() != span.sha256 or span.end > len(data):
		raise ValueError('Source changed after indexing; refresh before inspecting this range.')
	start = max(0, data.rfind(b'\n', 0, max(0, span.start - 1500)) + 1)
	end = min(len(data), span.end + 3000)
	return SourceExcerpt(catalog_id=catalog_id, path=span.path, sha256=span.sha256, line=data[:start].count(b'\n') + 1, text=decode_source(data[start:end])[0])

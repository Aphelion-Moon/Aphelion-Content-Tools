from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from tools.definition_editor.catalog import CatalogStore
from tools.definition_editor.query import query_definitions
from tools.definition_editor.storage import DraftStore
from webapp.store.search import SearchContext, SearchReport, search

DEFINITION_TABLES = frozenset({'job_definitions', 'outfit_definitions'})


def search_application(root: Path, catalog_store: CatalogStore, query: str, *, tables: list[str] | None, limit: int, context: SearchContext | None) -> SearchReport:
	store_tables = [name for name in tables if name not in DEFINITION_TABLES] if tables else None
	report = search(root, query, tables=store_tables, limit=limit, context=context) if tables is None or store_tables else SearchReport((), 'keyword-only', '', 'Definition search supports exact paths and name substrings; no semantic search.')
	if not query.strip() or tables is not None and not set(tables) & DEFINITION_TABLES:
		return report
	try:
		catalog_id, catalog, _ = catalog_store.read()
	except (ValueError, OSError):
		return report
	results = list(report.results)
	needle = query.casefold()
	def add(kind: str, identity: str, label: str, type_path: str | None, snapshot: str, *, draft: bool = False) -> None:
		table = f'{kind}_definitions'
		if tables is not None and table not in tables:
			return
		score = .018 if identity.casefold() == needle or label.casefold() == needle else .012
		boost = .0005 if context and context.tool == f'{kind}-editor' else 0
		results.append({'table': table, 'id': ('draft:' if draft else '') + identity, 'score': score + boost,
			'record': {'id': identity, 'label': label, 'type_path': type_path, 'catalog_id': snapshot},
			'scores': {'keyword_rrf': score, 'semantic_rrf': 0, 'context_boost': boost, 'final': score + boost},
			'context_reason': 'Exact identity / name substring search',
			'navigation': {'tool': f'{kind}-editor', 'route': f'/{kind}-editor', 'record_kind': 'definition_draft' if draft else 'definition', 'record_id': identity, 'type_path': type_path, 'catalog_id': snapshot}})
	for item in query_definitions(catalog, 'all', query):
		if item.kind not in ('job', 'outfit', 'id_trim'):
			continue
		label = next((field.value for field in item.fields if field.name in ('title', 'name') and isinstance(field.value, str)), item.type_path)
		add('outfit' if item.kind == 'outfit' else 'job', item.type_path, str(label), item.type_path, catalog_id)
	for kind in ('job', 'outfit'):
		for saved in DraftStore(root).list(kind):
			if needle in (saved.draft.label + ' ' + saved.draft.id + ' ' + ' '.join(edit.type_path for edit in saved.draft.edits)).casefold():
				add(kind, saved.draft.id, saved.draft.label or saved.draft.id, None, saved.draft.catalog_id, draft=True)
	results.sort(key=lambda item: (-float(str(item['score'])), str(item['table']), str(item['id'])))
	return replace(report, results=tuple(results[:limit]))

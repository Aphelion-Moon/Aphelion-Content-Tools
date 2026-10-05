from __future__ import annotations

from .models import AuthoringCatalog, Definition


def classified(definition: Definition, catalog: AuthoringCatalog) -> Definition:
	if definition.kind != 'job':
		return definition
	constants = {item.name: item.value for item in catalog.constants if item.value_known}
	flags = next((field.value for field in definition.fields if field.name == 'job_flags' and field.value_known), None)
	crew, joinable = constants.get('JOB_CREW_MEMBER'), constants.get('JOB_NEW_PLAYER_JOINABLE')
	category = 'base' if definition.type_path == '/datum/job' else 'unresolved'
	selectable = None
	if isinstance(flags, int) and isinstance(crew, int) and isinstance(joinable, int):
		if category != 'base':
			category = 'station' if flags & crew else 'special'
		selectable = bool(flags & joinable)
	return definition.model_copy(update={'job_category': category, 'player_selectable': selectable})


def query_definitions(catalog: AuthoringCatalog, kind: str, query: str = '', subtype_of: str | None = None) -> list[Definition]:
	parents = {item.type_path: item.parent_type for item in catalog.definitions}
	def included(item: Definition) -> bool:
		if kind != 'all' and item.kind != kind:
			return False
		if subtype_of:
			current: str | None = item.type_path
			visited: set[str] = set()
			while current != subtype_of:
				if current is None or current in visited:
					return False
				visited.add(current)
				current = parents.get(current)
		return query.casefold() in (item.type_path + ' ' + ' '.join(str(field.value) for field in item.fields if field.name in ('name', 'title'))).casefold()
	return [item for item in catalog.definitions if included(item)]

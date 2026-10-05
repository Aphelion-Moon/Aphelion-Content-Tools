import type { components } from '~/lib/api-schema';
import type { SearchResult, SelectedContext } from '~/store/appStore';

type SearchRequest = components['schemas']['SearchRequest'];

export function buildSearchRequest(
	query: string,
	selectedContext: SelectedContext | null,
	limit: number,
	tables: readonly string[] = [],
): SearchRequest {
	return {
		query,
		limit,
		...(selectedContext ? { selected_context: selectedContext } : {}),
		...(tables.length > 0 ? { scope: { tables: [...tables] } } : {}),
	};
}

function stringList(value: unknown): string[] {
	if (typeof value === 'string' && value) return [value];
	if (!Array.isArray(value)) return [];
	return value.filter((item): item is string => typeof item === 'string' && Boolean(item));
}

export function contextFromResult(result: SearchResult): SelectedContext {
	const groups = ['group', 'groups', 'group_ids', 'group_labels'].flatMap((key) => stringList(result.record[key]));
	const module = result.record.module ?? result.record.module_id;
	return {
		tool: result.navigation.tool,
		record_kind: result.navigation.record_kind,
		record_id: result.navigation.record_id,
		type_path: result.navigation.type_path ?? null,
		...(result.navigation.catalog_id ? { catalog_id: result.navigation.catalog_id } : {}),
		groups: [...new Set(groups)],
		module: typeof module === 'string' ? module : null,
	};
}

export function navigationRoute(result: SearchResult): string {
	const params = new URLSearchParams({ selected: result.navigation.record_id });
	if (result.navigation.type_path) params.set('type_path', result.navigation.type_path);
	if (result.navigation.catalog_id) params.set('catalog_id', result.navigation.catalog_id);
	if (result.navigation.record_kind === 'definition_draft') params.set('draft_id', result.navigation.record_id);
	return `${result.navigation.route}?${params.toString()}`;
}

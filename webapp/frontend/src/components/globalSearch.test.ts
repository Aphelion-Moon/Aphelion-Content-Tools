import { describe, expect, it } from 'vitest';
import type { SearchResult, SelectedContext } from '~/store/appStore';
import { buildSearchRequest, contextFromResult, navigationRoute } from './globalSearchModel';

const result: SearchResult = {
	table: 'catalog_targets',
	score: 0.02,
	id: '/obj/item/radio',
	record: { label: 'Radio', type_path: '/obj/item/radio', group_ids: ['items'] },
	scores: { keyword_rrf: 0.016, semantic_rrf: 0, context_boost: 0.004, final: 0.02 },
	context_reason: 'related type path',
	navigation: {
		tool: 'lore-editor',
		route: '/lore-editor',
		record_kind: 'catalog_target',
		record_id: '/obj/item/radio',
		type_path: '/obj/item/radio',
	},
};

describe('contextual global search', () => {
	it('sends selected context as a boost input without inventing a scope filter', () => {
		const context: SelectedContext = {
			tool: 'lore-editor',
			record_kind: 'catalog_target',
			record_id: '/obj/item/radio/headset',
			type_path: '/obj/item/radio/headset',
			groups: ['items'],
		};

		expect(buildSearchRequest('radio', context, 6)).toEqual({
			query: 'radio',
			limit: 6,
			selected_context: context,
		});
	});

	it('only adds a table scope when the writer explicitly selects one', () => {
		expect(buildSearchRequest('radio', null, 6, ['catalog_targets', 'overrides'])).toEqual({
			query: 'radio',
			limit: 6,
			scope: { tables: ['catalog_targets', 'overrides'] },
		});
	});

	it('builds an exact deep link and promotes the chosen result to shared context', () => {
		expect(navigationRoute(result)).toBe(
			'/lore-editor?selected=%2Fobj%2Fitem%2Fradio&type_path=%2Fobj%2Fitem%2Fradio',
		);
		expect(contextFromResult(result)).toMatchObject({
			tool: 'lore-editor',
			record_kind: 'catalog_target',
			record_id: '/obj/item/radio',
			type_path: '/obj/item/radio',
			groups: ['items'],
		});
	});
});

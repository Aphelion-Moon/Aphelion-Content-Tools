import { describe, expect, it } from 'vitest';
import type { ReviewEntry } from './reviewFeed';
import { buildEntryPayload, draftFromEntry, entryIdForTypePath } from './entryDraft';

const entry = {
	id: 'catalog:/obj/item/radio',
	type_path: '/obj/item/radio',
	category: 'catalog',
	status: 'unreviewed',
	base_status: 'unreviewed',
	approved: false,
	has_override: false,
	groups: [],
	group_labels: [],
	group_match_reasons: {},
	issues: [],
	directional: false,
	redundant: false,
	suppression_reasons: [],
	icon_metadata: {},
} as ReviewEntry;

describe('lore entry drafts', () => {
	it('uses a reversible path-based id that does not collide with underscores', () => {
		expect(entryIdForTypePath('/obj/a_b')).toBe('lore.obj.a_b');
		expect(entryIdForTypePath('/obj/a/b')).toBe('lore.obj.a.b');
	});

	it('builds a minimal override while preserving supported icon and wiki fields', () => {
		const draft = draftFromEntry(entry);
		draft.name = 'Long-range radio';
		draft.icons.icon = { file: 'icons/obj/radio.dmi', state: 'radio' };
		draft.wiki.enabled = true;
		draft.wiki.slug = 'long-range-radio';
		draft.wiki.summary = 'A long-range radio.';
		draft.wiki.export_icon = true;

		expect(buildEntryPayload(draft)).toEqual({
			id: 'lore.obj.item.radio',
			type_path: '/obj/item/radio',
			name: 'Long-range radio',
			icons: { icon: { file: 'icons/obj/radio.dmi', state: 'radio' } },
			wiki: {
				enabled: true,
				slug: 'long-range-radio',
				summary: 'A long-range radio.',
				export_icon: true,
			},
		});
	});
});

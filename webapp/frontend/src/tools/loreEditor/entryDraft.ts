import type { ReviewEntry } from './reviewFeed';

export type IconSlot = 'icon' | 'worn_icon' | 'inhand_icon';

export interface IconDraft {
	file: string;
	state: string;
}

export interface EntryDraft {
	id: string;
	type_path: string;
	name: string;
	description: string;
	special_desc_requirement: string;
	special_desc: string;
	icons: Record<IconSlot, IconDraft>;
	wiki: {
		enabled: boolean;
		slug: string;
		summary: string;
		export_icon: boolean;
	};
}

const ICON_SLOTS: readonly IconSlot[] = ['icon', 'worn_icon', 'inhand_icon'];

export function entryIdForTypePath(typePath: string): string {
	return `lore.${typePath.replace(/^\//, '').replaceAll('/', '.')}`;
}

function iconDraft(raw: Record<string, unknown>, slot: IconSlot): IconDraft {
	const icons = raw['icons'];
	const record = icons && typeof icons === 'object' ? (icons as Record<string, unknown>)[slot] : null;
	if (!record || typeof record !== 'object') return { file: '', state: '' };
	const values = record as Record<string, unknown>;
	return {
		file: typeof values['file'] === 'string' ? values['file'] : '',
		state: typeof values['state'] === 'string' ? values['state'] : '',
	};
}

export function draftFromEntry(entry: ReviewEntry): EntryDraft {
	const raw = entry.raw ?? {};
	const wikiValue = raw['wiki'];
	const wiki = wikiValue && typeof wikiValue === 'object' ? wikiValue as Record<string, unknown> : {};
	return {
		id: entry.has_override ? entry.id : entryIdForTypePath(entry.type_path),
		type_path: entry.type_path,
		name: typeof raw['name'] === 'string' ? raw['name'] : '',
		description: typeof raw['description'] === 'string' ? raw['description'] : '',
		special_desc_requirement: typeof raw['special_desc_requirement'] === 'string' ? raw['special_desc_requirement'] : '',
		special_desc: typeof raw['special_desc'] === 'string' ? raw['special_desc'] : '',
		icons: {
			icon: iconDraft(raw, 'icon'),
			worn_icon: iconDraft(raw, 'worn_icon'),
			inhand_icon: iconDraft(raw, 'inhand_icon'),
		},
		wiki: {
			enabled: wiki['enabled'] === true,
			slug: typeof wiki['slug'] === 'string' ? wiki['slug'] : '',
			summary: typeof wiki['summary'] === 'string' ? wiki['summary'] : '',
			export_icon: wiki['export_icon'] === true,
		},
	};
}

export function buildEntryPayload(draft: EntryDraft): Record<string, unknown> {
	const payload: Record<string, unknown> = { id: draft.id, type_path: draft.type_path };
	for (const field of ['name', 'description', 'special_desc_requirement', 'special_desc'] as const) {
		const value = draft[field].trim();
		if (value) payload[field] = value;
	}
	const icons: Record<string, IconDraft> = {};
	for (const slot of ICON_SLOTS) {
		const file = draft.icons[slot].file.trim();
		const state = draft.icons[slot].state.trim();
		if (file && state) icons[slot] = { file, state };
	}
	if (Object.keys(icons).length) payload['icons'] = icons;
	if (draft.wiki.enabled) {
		payload['wiki'] = {
			enabled: true,
			slug: draft.wiki.slug.trim(),
			summary: draft.wiki.summary.trim(),
			export_icon: draft.wiki.export_icon,
		};
	}
	return payload;
}

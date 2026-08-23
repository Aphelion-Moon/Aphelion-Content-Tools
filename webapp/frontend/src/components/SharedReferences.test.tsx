import { Route, Router } from '@solidjs/router';
import axe from 'axe-core';
import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '~/lib/api';
import { appState } from '~/store/appStore';
import SharedReferences, { contextFromReference, referenceRoute } from './SharedReferences';

const reference = {
	id: 'reference-1',
	tool: 'lore-editor' as const,
	kind: 'catalog_target' as const,
	key: '/obj/item/radio',
	label: 'Radio',
	path: null,
	note: null,
	created_at: '2026-08-22T10:00:00+00:00',
};

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	document.body.replaceChildren();
});

describe('shared references', () => {
	it('maps a pinned entity to exact navigation and selected search context', () => {
		expect(referenceRoute(reference)).toBe('/lore-editor?selected=%2Fobj%2Fitem%2Fradio&type_path=%2Fobj%2Fitem%2Fradio');
		expect(contextFromReference(reference)).toEqual({
			tool: 'lore-editor',
			record_kind: 'catalog_target',
			record_id: '/obj/item/radio',
			type_path: '/obj/item/radio',
			groups: [],
			module: null,
		});
	});

	it('lists, selects, and removes references accessibly', async () => {
		vi.spyOn(api, 'get').mockResolvedValue({ references: [reference] });
		const remove = vi.spyOn(api, 'delete').mockResolvedValue({ deleted: true, id: reference.id });
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(
			() => <Router><Route path="*" component={() => <SharedReferences />} /></Router>,
			host,
		);
		await settle();

		const radio = [...host.querySelectorAll('button')].find((button) => button.textContent === 'Radio')!;
		vi.stubGlobal('scrollTo', vi.fn());
		radio.click();
		expect(appState.selectedContext?.record_id).toBe('/obj/item/radio');

		const removeButton = host.querySelector<HTMLButtonElement>('button[aria-label="Remove Radio from references"]')!;
		removeButton.click();
		await settle();
		expect(remove).toHaveBeenCalledWith('/api/references/reference-1');

		const accessibility = await axe.run(host, { rules: { 'color-contrast': { enabled: false } } });
		expect(accessibility.violations).toEqual([]);
		dispose();
	});
});

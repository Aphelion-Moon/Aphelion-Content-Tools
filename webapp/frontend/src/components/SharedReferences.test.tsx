import { Route, Router } from '@solidjs/router';
import axe from 'axe-core';
import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '~/lib/api';
import { appState, setWorkspaceRevision } from '~/store/appStore';
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
	setWorkspaceRevision(null);
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

	it('does not repopulate references from a request started before a workspace revision change', async () => {
		let resolveOld!: (value: unknown) => void;
		let resolveCurrent!: (value: unknown) => void;
		vi.spyOn(api, 'get')
			.mockReturnValueOnce(new Promise((done) => { resolveOld = done; }))
			.mockReturnValueOnce(new Promise((done) => { resolveCurrent = done; }));
		setWorkspaceRevision({ worktree_id: 'worktree', branch: 'main', head: 'head-1', content_revision: 'content-1', projection_revision: null, projection_generation_id: null, game_source: null });
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(
			() => <Router><Route path="*" component={() => <SharedReferences />} /></Router>,
			host,
		);
		await settle();
		setWorkspaceRevision({ worktree_id: 'worktree', branch: 'main', head: 'head-2', content_revision: 'content-2', projection_revision: null, projection_generation_id: null, game_source: null });
		resolveOld({ references: [reference] });
		await settle();

		expect(host.querySelector('button[title="/obj/item/radio"]')).toBeNull();
		expect(host.textContent).toContain('Workspace changed. Refreshing references');
		resolveCurrent({ references: [] });
		dispose();
	});
});

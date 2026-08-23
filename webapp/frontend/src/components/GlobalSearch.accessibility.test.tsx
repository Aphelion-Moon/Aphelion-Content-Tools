import { Route, Router } from '@solidjs/router';
import axe from 'axe-core';
import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '~/lib/api';
import GlobalSearch from './GlobalSearch';

const searchResponse = {
	results: [{
		table: 'catalog_targets',
		score: 0.02,
		id: '/obj/item/radio',
		record: { label: 'Radio', type_path: '/obj/item/radio' },
		scores: { keyword_rrf: 0.02, semantic_rrf: 0, context_boost: 0, final: 0.02 },
		context_reason: null,
		navigation: {
			tool: 'lore-editor',
			route: '/lore-editor',
			record_kind: 'catalog_target',
			record_id: '/obj/item/radio',
			type_path: '/obj/item/radio',
		},
	}],
	semantic_search: { mode: 'hybrid', model_id: 'test-model', reason: null },
} as const;

afterEach(() => {
	vi.useRealTimers();
	vi.restoreAllMocks();
	document.body.replaceChildren();
});

describe('global search combobox accessibility', () => {
	it('connects the combobox to its listbox and announces result status', async () => {
		vi.useFakeTimers();
		vi.spyOn(api, 'post').mockResolvedValue(searchResponse);
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Router><Route path="*" component={GlobalSearch} /></Router>, host);
		const input = host.querySelector<HTMLInputElement>('#global-search')!;

		input.focus();
		input.value = 'radio';
		input.dispatchEvent(new InputEvent('input', { bubbles: true }));
		await vi.advanceTimersByTimeAsync(250);

		expect(input.getAttribute('role')).toBe('combobox');
		expect(input.getAttribute('aria-expanded')).toBe('true');
		const listboxId = input.getAttribute('aria-controls');
		const listbox = host.querySelector<HTMLElement>(`#${listboxId}`)!;
		expect(listbox.getAttribute('role')).toBe('listbox');
		expect(listbox.querySelectorAll('[role="option"]').length).toBeGreaterThan(0);
		expect(host.querySelector('[role="status"]')?.textContent).toContain('result');
		vi.useRealTimers();
		const accessibility = await axe.run(host, {
			rules: { region: { enabled: false }, 'color-contrast': { enabled: false } },
		});
		expect(accessibility.violations).toEqual([]);
		dispose();
	});

	it('moves through options with arrows, activates with Enter, and closes with Escape', async () => {
		vi.useFakeTimers();
		vi.spyOn(api, 'post').mockResolvedValue(searchResponse);
		vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined);
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Router><Route path="*" component={GlobalSearch} /></Router>, host);
		const input = host.querySelector<HTMLInputElement>('#global-search')!;

		input.focus();
		input.value = 'radio';
		input.dispatchEvent(new InputEvent('input', { bubbles: true }));
		await vi.advanceTimersByTimeAsync(250);
		input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
		const activeId = input.getAttribute('aria-activedescendant');
		expect(activeId).toBeTruthy();
		expect(host.querySelector(`#${activeId}`)?.getAttribute('aria-selected')).toBe('true');

		input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
		expect(input.getAttribute('aria-expanded')).toBe('false');
		expect(document.activeElement).toBe(input);

		input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
		input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
		expect(input.getAttribute('aria-expanded')).toBe('false');
		dispose();
	});
});

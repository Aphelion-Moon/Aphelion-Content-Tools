import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '~/lib/api';
import TypePicker from './TypePicker';

afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); document.body.replaceChildren(); });

describe('definition type selection', () => {
	it('supports arrow and Enter selection and clears the old selection immediately when filters change', async () => {
		vi.useFakeTimers();
		const select = vi.fn();
		vi.spyOn(api, 'get').mockResolvedValue({ catalog_id: 'catalog-1', total: 2, definitions: [{ type_path: '/obj/item/first', kind: 'item' }, { type_path: '/obj/item/second', kind: 'item' }] });
		const host = document.createElement('div'); document.body.append(host);
		const dispose = render(() => <TypePicker kind="item" label="Choose equipment" catalogId="catalog-1" onPick={select} />, host);
		try {
			await vi.advanceTimersByTimeAsync(160);
			const input = host.querySelector<HTMLInputElement>('[role="combobox"]')!;
			input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
			input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
			expect(select).toHaveBeenCalledWith(expect.objectContaining({ type_path: '/obj/item/second' }));
			select.mockClear();
			input.value = 'different'; input.dispatchEvent(new InputEvent('input', { bubbles: true }));
			input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
			expect(select).not.toHaveBeenCalled(); expect(input.hasAttribute('aria-activedescendant')).toBe(false);
		} finally { dispose(); }
	});

	it('refuses a result from a different catalog generation', async () => {
		vi.useFakeTimers();
		const select = vi.fn();
		vi.spyOn(api, 'get').mockResolvedValue({ catalog_id: 'other-catalog', total: 1, definitions: [{ type_path: '/obj/item/stale', kind: 'item' }] });
		const host = document.createElement('div'); document.body.append(host);
		const dispose = render(() => <TypePicker kind="item" label="Choose equipment" catalogId="catalog-1" onPick={select} />, host);
		try { await vi.advanceTimersByTimeAsync(160); expect(host.textContent).toContain('Catalog changed'); host.querySelector('input')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); expect(select).not.toHaveBeenCalled(); } finally { dispose(); }
	});
});

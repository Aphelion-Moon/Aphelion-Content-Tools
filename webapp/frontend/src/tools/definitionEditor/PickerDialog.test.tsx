import axe from 'axe-core';
import { createSignal, Show } from 'solid-js';
import { render } from 'solid-js/web';
import { afterEach, describe, expect, it } from 'vitest';
import PickerDialog from './PickerDialog';

afterEach(() => document.body.replaceChildren());

describe('definition picker dialog', () => {
	it('traps keyboard focus, closes with Escape, restores its opener, and has accessible dialog semantics', async () => {
		const host = document.createElement('div'); document.body.append(host);
		const [open, setOpen] = createSignal(false);
		const dispose = render(() => <><button onClick={() => setOpen(true)}>Choose item</button><Show when={open()}><PickerDialog label="Choose an item" close={() => setOpen(false)}><label>Find item<input /></label><button>Last item</button></PickerDialog></Show></>, host);
		try {
			const opener = host.querySelector('button')!; opener.focus(); opener.click(); await Promise.resolve();
			const dialog = host.querySelector<HTMLElement>('[role="dialog"]')!;
			expect(dialog.parentElement).not.toBe(host);
			const first = dialog.querySelector('button')!, last = [...dialog.querySelectorAll('button')].at(-1)!;
			last.focus(); last.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true })); expect(document.activeElement).toBe(first);
			first.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true })); expect(document.activeElement).toBe(last);
			const results = await axe.run(dialog, { rules: { 'color-contrast': { enabled: false } } }); expect(results.violations).toEqual([]);
			last.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); expect(host.querySelector('[role="dialog"]')).toBeNull(); expect(document.activeElement).toBe(opener);
		} finally { dispose(); }
	});
});

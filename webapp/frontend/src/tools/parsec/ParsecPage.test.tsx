import { render } from 'solid-js/web';
import { afterEach, describe, expect, it } from 'vitest';
import ParsecPage from './ParsecPage';

afterEach(() => {
	window.localStorage.clear();
	document.body.replaceChildren();
});

describe('Parsec page', () => {
	it('exposes and persists the reduced-motion preference', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecPage />, host);

		const select = host.querySelector<HTMLSelectElement>('select[aria-label="Parsec motion"]');
		expect(select).not.toBeNull();
		select!.value = 'reduce';
		select!.dispatchEvent(new Event('change', { bubbles: true }));

		expect(window.localStorage.getItem('aphelion-parsec-reduced-motion-override')).toBe('reduce');
		dispose();
	});
});

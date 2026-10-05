import { render } from 'solid-js/web';
import { afterEach, describe, expect, it } from 'vitest';
import ParsecHabitat from './ParsecHabitat';

afterEach(() => document.body.replaceChildren());

describe('Parsec habitat', () => {
	it('expands as an overlay and keeps the same persistent child instance', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const marker = document.createElement('span');
		marker.dataset.instanceId = 'one';
		const dispose = render(() => <ParsecHabitat>{marker}</ParsecHabitat>, host);
		const habitat = host.querySelector<HTMLElement>('[data-parsec-habitat]')!;
		const surface = host.querySelector<HTMLElement>('[data-parsec-habitat-surface]')!;
		const compactClass = surface.className;
		const before = host.querySelector('[data-instance-id="one"]');
		host.querySelector<HTMLButtonElement>('button[aria-label="Expand Parsec habitat"]')!.click();
		expect(habitat.dataset.expanded).toBe('true');
		expect(host.querySelector('[data-instance-id="one"]')).toBe(before);
		expect(surface.className).not.toBe(compactClass);
		dispose();
	});

	it('closes the expanded surface with Escape and restores the expand control', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecHabitat><span>Parsec</span></ParsecHabitat>, host);
		host.querySelector<HTMLButtonElement>('button[aria-label="Expand Parsec habitat"]')!.click();
		const surface = host.querySelector<HTMLElement>('[data-parsec-habitat-surface]')!;
		surface.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
		expect(host.querySelector('[data-parsec-habitat]')?.getAttribute('data-expanded')).toBe('false');
		expect(host.querySelector('button[aria-label="Expand Parsec habitat"]')).not.toBeNull();
		dispose();
	});

	it('stays expanded when a direct interaction moves focus outside the habitat', () => {
		const host = document.createElement('div');
		const outside = document.createElement('button');
		document.body.append(host, outside);
		const dispose = render(() => <ParsecHabitat><button type="button">Move furnishing</button></ParsecHabitat>, host);
		host.querySelector<HTMLButtonElement>('button[aria-label="Expand Parsec habitat"]')!.click();
		const interaction = host.querySelector<HTMLButtonElement>('button:not([aria-label])')!;
		interaction.focus();
		outside.focus();

		expect(host.querySelector('[data-parsec-habitat]')?.getAttribute('data-expanded')).toBe('true');
		dispose();
	});
});

import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DEFAULT_FURNITURE } from '~/lib/parsec/furniture';
import ParsecRoamingLayer from './ParsecRoamingLayer';

const EDGE_FURNITURE = {
	bed: { ...DEFAULT_FURNITURE.bed, anchor: 'app-edge' as const },
	cage: { ...DEFAULT_FURNITURE.cage, anchor: 'app-edge' as const },
};

function pointerEvent(type: string, values: Record<string, number>): Event {
	const event = new Event(type, { bubbles: true });
	for (const [key, value] of Object.entries(values)) Object.defineProperty(event, key, { value });
	return event;
}

afterEach(() => document.body.replaceChildren());

describe('Parsec roaming furniture layer', () => {
	it('keeps the full layer click-through and makes the visible furniture the control', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecRoamingLayer furniture={EDGE_FURNITURE} onFurnitureChange={vi.fn()} />
		), host);
		const layer = host.querySelector<HTMLElement>('[data-parsec-roaming-layer]')!;
		expect(layer.style.pointerEvents).toBe('none');
		const controls = layer.querySelectorAll<HTMLElement>('[data-furniture-control]');
		expect(controls).toHaveLength(2);
		for (const control of controls) {
			expect(control.style.pointerEvents).toBe('auto');
			expect(control.querySelector('[data-frame-id]')).not.toBeNull();
		}
		expect(layer.querySelector('[data-furniture-handle]')).toBeNull();
		dispose();
	});

	it('renders real SS13 bed and cage frames as accessible direct controls', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecRoamingLayer furniture={EDGE_FURNITURE} onFurnitureChange={vi.fn()} />
		), host);
		expect(host.querySelectorAll('[data-furniture-id="bed"]')).toHaveLength(1);
		expect(host.querySelectorAll('[data-furniture-id="cage"]')).toHaveLength(1);
		expect(host.querySelector('[data-furniture-id="bed"] [data-frame-id]')?.getAttribute('data-frame-id'))
			.toBe('ss13-objects/dogbed/d0/f0');
		expect(host.querySelector('[data-furniture-id="cage"] [data-frame-id]')?.getAttribute('data-frame-id'))
			.toBe('ss13-objects/cage-open/d0/f0');
		expect(host.querySelector('[data-fallback-art]')).toBeNull();
		expect(host.querySelector('[aria-label="Move Parsec bed"]')).not.toBeNull();
		expect(host.querySelector('[aria-label="Move Parsec cage"]')).not.toBeNull();
		expect(host.textContent).not.toContain('MoveMove');
		dispose();
	});

	it('uses the latched and occupied SS13 cage states', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecRoamingLayer
				furniture={{
					...EDGE_FURNITURE,
					cage: { ...EDGE_FURNITURE.cage, status: 'latched-empty' },
				}}
				onFurnitureChange={vi.fn()}
			/>
		), host);
		expect(host.querySelector('[data-furniture-id="cage"] [data-frame-id]')?.getAttribute('data-frame-id'))
			.toBe('ss13-objects/cage-locked/d0/f0');
		dispose();

		const occupiedHost = document.createElement('div');
		document.body.append(occupiedHost);
		const disposeOccupied = render(() => (
			<ParsecRoamingLayer
				furniture={{
					...EDGE_FURNITURE,
					cage: { ...EDGE_FURNITURE.cage, status: 'latched-occupied' },
				}}
				onFurnitureChange={vi.fn()}
			/>
		), occupiedHost);
		expect(occupiedHost.querySelector('[data-furniture-id="cage"] [data-frame-id]')?.getAttribute('data-frame-id'))
			.toBe('ss13-objects/cage-occupied/d0/f0');
		disposeOccupied();
	});

	it('moves furniture by dragging the artwork and reanchors it inside the habitat', () => {
		const habitat = document.createElement('div');
		habitat.dataset.parsecStage = '';
		habitat.getBoundingClientRect = () => ({
			x: 100, y: 200, left: 100, top: 200, right: 500, bottom: 500, width: 400, height: 300, toJSON: () => ({}),
		});
		document.body.append(habitat);
		const onFurnitureChange = vi.fn();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecRoamingLayer furniture={EDGE_FURNITURE} onFurnitureChange={onFurnitureChange} />
		), host);
		const bed = host.querySelector<HTMLElement>('[data-furniture-id="bed"]')!;
		bed.setPointerCapture = () => undefined;
		bed.releasePointerCapture = () => undefined;

		bed.dispatchEvent(pointerEvent('pointerdown', { pointerId: 7, clientX: 0, clientY: 0 }));
		window.dispatchEvent(pointerEvent('pointermove', { pointerId: 7, clientX: 300, clientY: 350 }));
		window.dispatchEvent(pointerEvent('pointerup', { pointerId: 7, clientX: 300, clientY: 350 }));

		expect(onFurnitureChange).toHaveBeenLastCalledWith(expect.objectContaining({
			bed: expect.objectContaining({ anchor: 'habitat', position: { x: 0.5, y: 0.5 } }),
		}));
		dispose();
	});

	it('reanchors furniture to the viewport as soon as the pointer leaves the habitat', () => {
		const habitat = document.createElement('div');
		habitat.dataset.parsecStage = '';
		habitat.getBoundingClientRect = () => ({
			x: 100, y: 200, left: 100, top: 200, right: 500, bottom: 500, width: 400, height: 300, toJSON: () => ({}),
		});
		document.body.append(habitat);
		const onFurnitureChange = vi.fn();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecRoamingLayer furniture={DEFAULT_FURNITURE} onFurnitureChange={onFurnitureChange} space="habitat" />
		), host);
		const bed = host.querySelector<HTMLElement>('[data-furniture-id="bed"]')!;
		bed.setPointerCapture = () => undefined;
		bed.releasePointerCapture = () => undefined;

		bed.dispatchEvent(pointerEvent('pointerdown', { pointerId: 8, clientX: 0, clientY: 0 }));
		window.dispatchEvent(pointerEvent('pointermove', { pointerId: 8, clientX: 600, clientY: 350 }));

		expect(onFurnitureChange).toHaveBeenLastCalledWith(expect.objectContaining({
			bed: expect.objectContaining({ anchor: 'app-edge' }),
		}));
		window.dispatchEvent(pointerEvent('pointercancel', { pointerId: 8, clientX: 600, clientY: 350 }));
		dispose();
	});

	it('keeps the persistent actor mounted but marks excursions unavailable before consent', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecRoamingLayer
				furniture={DEFAULT_FURNITURE}
				onFurnitureChange={vi.fn()}
				consent="unconfigured"
				companion={<div data-testid="parsec-roaming-sprite" />}
			/>
		), host);
		expect(host.querySelector('[data-testid="parsec-roaming-sprite"]')).not.toBeNull();
		expect(host.querySelector('[data-parsec-roaming-layer]')?.getAttribute('data-excursions-allowed')).toBe('false');
		dispose();
	});

	it('mounts the roaming actor only after excursions are allowed', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecRoamingLayer
				furniture={DEFAULT_FURNITURE}
				onFurnitureChange={vi.fn()}
				consent="allowed"
				companion={<div data-testid="parsec-roaming-sprite" style={{ 'pointer-events': 'auto' }} />}
			/>
		), host);
		expect(host.querySelector('[data-testid="parsec-roaming-sprite"]')).not.toBeNull();
		dispose();
	});
});

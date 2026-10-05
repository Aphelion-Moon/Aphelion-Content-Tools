import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { initialCompanionState } from '~/lib/parsec/companionReducer';
import { DEFAULT_COMPANION_SETTINGS, type CompanionIntent } from '~/lib/parsec/companionTypes';
import ParsecInteractionSurface from './ParsecInteractionSurface';

afterEach(() => document.body.replaceChildren());

const state = initialCompanionState({
	consent: 'allowed',
	familiarity: 1,
	settings: DEFAULT_COMPANION_SETTINGS,
});

describe('Parsec interaction surface', () => {
	it('consumes Escape so putting away a toy does not close its containing menu', () => {
		const onClose = vi.fn();
		const parentKeyDown = vi.fn();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <div onKeyDown={parentKeyDown}><ParsecInteractionSurface tool="ball" state={state} onIntent={vi.fn()} onClose={onClose} /></div>, host);
		host.querySelector('[data-parsec-active-tool]')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
		expect(onClose).toHaveBeenCalledOnce();
		expect(parentKeyDown).not.toHaveBeenCalled();
		dispose();
	});
	it('releases capture on Escape and finishes a pointer gesture only once', () => {
		const onIntent = vi.fn();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecInteractionSurface tool="brush" state={state} onIntent={onIntent} onClose={() => undefined} />, host);
		const toy = host.querySelector<HTMLButtonElement>('[data-parsec-active-tool]')!;
		toy.setPointerCapture = vi.fn();
		toy.releasePointerCapture = vi.fn();
		const pointer = (type: string) => {
			const event = new Event(type, { bubbles: true });
			Object.defineProperties(event, { pointerId: { value: 9 }, clientX: { value: 50 }, clientY: { value: 40 } });
			return event;
		};
		toy.dispatchEvent(pointer('pointerdown'));
		toy.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
		expect(toy.releasePointerCapture).toHaveBeenCalledWith(9);
		toy.dispatchEvent(pointer('pointerup'));
		expect(onIntent.mock.calls.filter(([intent]) => intent.type === 'brush-finished')).toHaveLength(1);
		dispose();
	});
	it('provides a keyboard-equivalent begin, move, and finish sequence for draggable toys', () => {
		const intents: CompanionIntent[] = [];
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecInteractionSurface
				tool="ball"
				state={state}
				onIntent={(intent) => intents.push(intent)}
				onClose={vi.fn()}
			/>
		), host);
		const toy = host.querySelector<HTMLButtonElement>('[data-parsec-active-tool="ball"]')!;
		expect(toy.querySelector('[data-parsec-object-icon]')?.getAttribute('data-parsec-object-icon')).toBe('tennis-ball');
		toy.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
		toy.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
		toy.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
		expect(intents.map((intent) => intent.type)).toEqual([
			'direct-interaction',
			'ball-placed',
			'ball-moved',
			'ball-thrown',
		]);
		dispose();
	});

	it('does not begin a physical toy interaction while the cage is latched', () => {
		const onIntent = vi.fn();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecInteractionSurface
				tool="tug"
				state={{ ...state, location: { kind: 'cage', closed: true } }}
				onIntent={onIntent}
				onClose={vi.fn()}
			/>
		), host);
		const toy = host.querySelector<HTMLButtonElement>('[data-parsec-active-tool="tug"]')!;
		expect(toy.disabled).toBe(true);
		toy.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
		expect(onIntent).not.toHaveBeenCalled();
		dispose();
	});
});

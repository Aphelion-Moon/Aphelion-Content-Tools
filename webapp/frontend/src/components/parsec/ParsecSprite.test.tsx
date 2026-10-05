import { createSignal } from 'solid-js';
import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { CompanionIntent } from '~/lib/parsec/companionTypes';
import ParsecSprite from './ParsecSprite';

afterEach(() => {
	vi.useRealTimers();
	document.body.replaceChildren();
});

function pointerEvent(type: string, values: Record<string, number>): Event {
	const event = new Event(type, { bubbles: true });
	for (const [key, value] of Object.entries(values)) Object.defineProperty(event, key, { value });
	return event;
}

describe('Parsec sprite direct handling', () => {
	it('restarts a repeated one-shot and completes only the new playback instance', () => {
		vi.useFakeTimers();
		const dispatch = vi.fn();
		const [instance, setInstance] = createSignal(1);
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecSprite clipId="feedback-success-wag" clipInstance={instance()} point={{ x: 0, y: 0 }} handlingPhysics="carry-only" reducedMotion confined={false} dispatch={dispatch} />
		), host);
		vi.advanceTimersByTime(500);
		setInstance(2);
		vi.advanceTimersByTime(240);
		expect(dispatch).not.toHaveBeenCalled();
		vi.advanceTimersByTime(500);
		expect(dispatch).toHaveBeenCalledExactlyOnceWith({ type: 'clip-finished', clipId: 'feedback-success-wag', instance: 2 });
		dispose();
	});

	it('finishes a reduced-motion one-shot while holding its representative frame', () => {
		vi.useFakeTimers();
		const dispatch = vi.fn();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecSprite clipId="feedback-success-wag" point={{ x: 0, y: 0 }} handlingPhysics="carry-only" reducedMotion confined={false} dispatch={dispatch} />
		), host);
		const frameId = host.querySelector('[data-frame-id]')!.getAttribute('data-frame-id');
		vi.advanceTimersByTime(739);
		expect(dispatch).not.toHaveBeenCalled();
		expect(host.querySelector('[data-frame-id]')!.getAttribute('data-frame-id')).toBe(frameId);
		vi.advanceTimersByTime(1);
		expect(dispatch).toHaveBeenCalledExactlyOnceWith({ type: 'clip-finished', clipId: 'feedback-success-wag' });
		vi.advanceTimersByTime(2000);
		expect(dispatch).toHaveBeenCalledTimes(1);
		dispose();
	});

	it('releases a cancelled pointer at its last position without throwing Parsec', () => {
		const onRelease = vi.fn();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecSprite clipId="core-idle-seated" point={{ x: 20, y: 20 }} onRelease={onRelease} handlingPhysics="full-tossing" reducedMotion={false} confined={false} dispatch={() => undefined} />
		), host);
		const scruff = host.querySelector<HTMLElement>('[data-parsec-scruff]')!;
		scruff.setPointerCapture = () => undefined;
		scruff.releasePointerCapture = () => undefined;
		scruff.dispatchEvent(pointerEvent('pointerdown', { pointerId: 2, clientX: 30, clientY: 30, timeStamp: 0 }));
		window.dispatchEvent(pointerEvent('pointermove', { pointerId: 2, clientX: 90, clientY: 60, timeStamp: 50 }));
		window.dispatchEvent(pointerEvent('pointercancel', { pointerId: 2, clientX: 0, clientY: 0, timeStamp: 60 }));
		expect(onRelease).toHaveBeenCalledExactlyOnceWith({ point: { x: 80, y: 50 }, velocity: { x: 0, y: 0 } });
		dispose();
	});

	it('Escape ends pointer capture so later pointerup cannot release twice', () => {
		const onRelease = vi.fn();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecSprite clipId="core-idle-seated" point={{ x: 20, y: 20 }} onRelease={onRelease} handlingPhysics="full-tossing" reducedMotion={false} confined={false} dispatch={() => undefined} />
		), host);
		const scruff = host.querySelector<HTMLElement>('[data-parsec-scruff]')!;
		scruff.setPointerCapture = () => undefined;
		scruff.releasePointerCapture = vi.fn();
		scruff.dispatchEvent(pointerEvent('pointerdown', { pointerId: 2, clientX: 30, clientY: 30, timeStamp: 0 }));
		scruff.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
		window.dispatchEvent(pointerEvent('pointerup', { pointerId: 2, clientX: 90, clientY: 60, timeStamp: 50 }));
		expect(scruff.releasePointerCapture).toHaveBeenCalledWith(2);
		expect(onRelease).toHaveBeenCalledExactlyOnceWith({ point: { x: 20, y: 20 }, velocity: { x: 0, y: 0 } });
		dispose();
	});

	it('keeps a generous scruff target over the neck and shoulders', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecSprite clipId="seated-idle" point={{ x: 20, y: 20 }} handlingPhysics="carry-only" reducedMotion={false} confined={false} dispatch={() => undefined} />
		), host);
		const scruff = host.querySelector<HTMLElement>('[data-parsec-scruff]')!;
		expect(parseFloat(scruff.style.width)).toBeGreaterThanOrEqual(40);
		expect(parseFloat(scruff.style.height)).toBeGreaterThanOrEqual(36);
		dispose();
	});

	it('renders controlled viewport coordinates instead of retaining its mount point', () => {
		const [point, setPoint] = createSignal({ x: 20, y: 30 });
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecSprite
				clipId="seated-idle"
				point={point()}
				onPointChange={setPoint}
				handlingPhysics="carry-only"
				reducedMotion={false}
				confined={false}
				dispatch={() => undefined}
			/>
		), host);

		expect(host.querySelector<HTMLElement>('[data-frame-id]')?.style.transform).toBe('translate(20px, 30px)');
		setPoint({ x: 140, y: 90 });
		expect(host.querySelector<HTMLElement>('[data-frame-id]')?.style.transform).toBe('translate(140px, 90px)');
		dispose();
	});

	it('captures the scruff pointer, dispatches movement, and releases with configured motion', () => {
		const dispatch = vi.fn();
		const onRelease = vi.fn();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecSprite clipId="seated-idle" point={{ x: 20, y: 20 }} onRelease={onRelease} handlingPhysics="gentle-momentum" reducedMotion={false} confined={false} dispatch={dispatch} />
		), host);
		const scruff = host.querySelector<HTMLElement>('[data-parsec-scruff]')!;
		const captured: number[] = [];
		scruff.setPointerCapture = (id) => { captured.push(id); };
		scruff.releasePointerCapture = () => undefined;
		scruff.dispatchEvent(pointerEvent('pointerdown', { pointerId: 7, clientX: 20, clientY: 20, timeStamp: 0 }));
		scruff.dispatchEvent(pointerEvent('pointermove', { pointerId: 7, clientX: 80, clientY: 30, timeStamp: 100 }));
		scruff.dispatchEvent(pointerEvent('pointerup', { pointerId: 7, clientX: 90, clientY: 35, timeStamp: 150 }));
		expect(captured).toEqual([7]);
		expect(dispatch).toHaveBeenCalledWith(expect.objectContaining({ type: 'grabbed' }));
		expect(dispatch).toHaveBeenCalledWith(expect.objectContaining({ type: 'held-moved' }));
		expect(dispatch).toHaveBeenLastCalledWith(expect.objectContaining({ type: 'released' }));
		expect(onRelease).toHaveBeenCalledWith({ point: { x: 90, y: 35 }, velocity: { x: 466.6666666666667, y: 100 } });
		dispose();
	});

	it('uses the reduced-motion frame and zero release velocity when motion is reduced', () => {
		const dispatch = vi.fn();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecSprite clipId="working-patrol" point={{ x: 0, y: 0 }} handlingPhysics="full-tossing" reducedMotion confined={false} dispatch={dispatch} />
		), host);
		const scruff = host.querySelector<HTMLElement>('[data-parsec-scruff]')!;
		scruff.setPointerCapture = () => undefined;
		scruff.releasePointerCapture = () => undefined;
		scruff.dispatchEvent(pointerEvent('pointerdown', { pointerId: 2, clientX: 0, clientY: 0, timeStamp: 0 }));
		scruff.dispatchEvent(pointerEvent('pointerup', { pointerId: 2, clientX: 100, clientY: 100, timeStamp: 10 }));
		expect(dispatch).toHaveBeenLastCalledWith(expect.objectContaining({ velocity: { x: 0, y: 0 } }));
		expect(host.querySelector('[data-frame-id]')?.getAttribute('data-frame-id')).toBe('working-0');
		dispose();
	});

	it('renders a pointer-inert reduced-motion effect overlay from the accepted effect sheet', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecSprite
				clipId="touch-pat-delighted"
				effectClipId="effect-hearts"
				point={{ x: 0, y: 0 }}
				handlingPhysics="carry-only"
				reducedMotion
				confined={false}
				dispatch={() => undefined}
			/>
		), host);

		const effect = host.querySelector<HTMLElement>('[data-parsec-effect-frame]')!;
		expect(effect.dataset.parsecEffectFrame).toBe('parsec-effects/effect-hearts/d0/f2');
		expect(getComputedStyle(effect).pointerEvents).toBe('none');
		dispose();
	});

	it('plays one coherent directional walk variant instead of rotating through the atlas', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecSprite clipId="core-walk-cardinal" direction="west" point={{ x: 0, y: 0 }} handlingPhysics="carry-only" reducedMotion confined={false} dispatch={() => undefined} />
		), host);

		expect(host.querySelector('[data-frame-id]')?.getAttribute('data-frame-id')).toBe('parsec-core/core-walk-cardinal/d3/f0');
		dispose();
	});

	it('supports keyboard pickup, movement, release, and blocks handling while confined', () => {
		const dispatch = vi.fn();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecSprite clipId="seated-idle" point={{ x: 10, y: 10 }} handlingPhysics="carry-only" reducedMotion={false} confined dispatch={dispatch} />
		), host);
		const scruff = host.querySelector<HTMLElement>('[data-parsec-scruff]')!;
		scruff.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
		expect(dispatch).not.toHaveBeenCalled();
		dispose();
	});

	it('reports completion after an accepted one-shot clip reaches its authored final dwell', () => {
		vi.useFakeTimers();
		const [clipId, setClipId] = createSignal('feedback-success-wag');
		const dispatch = vi.fn((intent: CompanionIntent) => {
			if (intent.type === 'clip-finished') setClipId('core-idle-seated');
		});
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ParsecSprite clipId={clipId()} point={{ x: 0, y: 0 }} handlingPhysics="carry-only" reducedMotion={false} confined={false} dispatch={dispatch} />
		), host);

		vi.advanceTimersByTime(740);

		expect(dispatch).toHaveBeenLastCalledWith({ type: 'clip-finished', clipId: 'feedback-success-wag' });
		expect(host.querySelector('[data-frame-id]')?.getAttribute('data-frame-id')).toBe('parsec-core/core-idle-seated/d0/f0');
		vi.advanceTimersByTime(2_599);
		expect(host.querySelector('[data-frame-id]')?.getAttribute('data-frame-id')).toBe('parsec-core/core-idle-seated/d0/f0');
		vi.advanceTimersByTime(1);
		expect(host.querySelector('[data-frame-id]')?.getAttribute('data-frame-id')).toBe('parsec-core/core-idle-seated/d0/f1');
		dispose();
	});
});

import { describe, expect, it } from 'vitest';
import type { IdleChatterPreference, ParsecEvent } from './types';
import { createParsecIdleScheduler, nextIdleDelayMs, type IdleSchedulerEnvironment } from './idle';

function createHarness() {
	let nextTimerId = 1;
	let contextListener: (() => void) | undefined;
	const timers = new Map<number, { readonly callback: () => void; readonly delayMs: number }>();
	const events: ParsecEvent[] = [];
	const state = {
		preference: 'rare' as IdleChatterPreference,
		route: '/lore-editor',
		contextKey: 'entry:radio',
		documentVisible: true,
		editableFocused: false,
		activeRunCount: 0,
		hasFeedback: false,
		connectionNeedsAttention: false,
	};
	const environment: IdleSchedulerEnvironment<number> = {
		readPreference: () => state.preference,
		readSnapshot: () => state,
		random: () => 0,
		setTimer: (callback, delayMs) => {
			const id = nextTimerId++;
			timers.set(id, { callback, delayMs });
			return id;
		},
		clearTimer: (id) => timers.delete(id),
		report: (event) => events.push(event),
		subscribeContext: (listener) => {
			contextListener = listener;
			return () => { contextListener = undefined; };
		},
	};

	return {
		environment,
		events,
		state,
		timers,
		fireNext: () => {
			const next = timers.entries().next().value as [number, { readonly callback: () => void }] | undefined;
			if (!next) throw new Error('No scheduled idle timer.');
			timers.delete(next[0]);
			next[1].callback();
		},
		changeContext: () => contextListener?.(),
	};
}

describe('Parsec idle scheduler', () => {
	it('uses the approved inclusive interval ranges', () => {
		expect(nextIdleDelayMs('off', 0)).toBeNull();
		expect(nextIdleDelayMs('rare', 0)).toBe(480_000);
		expect(nextIdleDelayMs('rare', 1)).toBe(720_000);
		expect(nextIdleDelayMs('occasional', 0)).toBe(240_000);
		expect(nextIdleDelayMs('occasional', 1)).toBe(420_000);
		expect(nextIdleDelayMs('frequent', 0)).toBe(120_000);
		expect(nextIdleDelayMs('frequent', 1)).toBe(240_000);
	});

	it('suppresses chatter while hidden, typing, working, speaking, or disconnected', () => {
		const harness = createHarness();
		const stop = createParsecIdleScheduler(harness.environment);
		for (const key of ['documentVisible', 'editableFocused', 'activeRunCount', 'hasFeedback', 'connectionNeedsAttention'] as const) {
			Object.assign(harness.state, {
				documentVisible: true,
				editableFocused: false,
				activeRunCount: 0,
				hasFeedback: false,
				connectionNeedsAttention: false,
			});
			Object.assign(harness.state, { [key]: key === 'documentVisible' ? false : key === 'activeRunCount' ? 1 : true });
			harness.fireNext();
		}

		expect(harness.events).toEqual([]);
		stop();
	});

	it('cycles contextual lines and resets its timer when route or selection context changes', () => {
		const harness = createHarness();
		const stop = createParsecIdleScheduler(harness.environment);
		expect([...harness.timers.values()][0]?.delayMs).toBe(480_000);

		harness.fireNext();
		harness.fireNext();
		expect(harness.events).toEqual([
			{ type: 'idle', phase: 'contextual', tool: 'parsec', route: '/lore-editor', lineIndex: 0 },
			{ type: 'idle', phase: 'contextual', tool: 'parsec', route: '/lore-editor', lineIndex: 1 },
		]);

		const timerBeforeReset = [...harness.timers.keys()][0];
		harness.state.contextKey = 'entry:company';
		harness.changeContext();
		expect(harness.timers.has(timerBeforeReset!)).toBe(false);
		expect(harness.timers).toHaveLength(1);

		stop();
		expect(harness.timers).toHaveLength(0);
	});
});

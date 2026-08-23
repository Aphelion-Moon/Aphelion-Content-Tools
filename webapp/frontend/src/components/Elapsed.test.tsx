import { afterEach, describe, expect, it, vi } from 'vitest';
import { startElapsedTicker } from './Elapsed';

afterEach(() => {
	vi.useRealTimers();
	document.body.replaceChildren();
});

describe('Elapsed', () => {
	it('keeps elapsed text moving even when no backend state changes', () => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date('2026-08-22T12:00:00Z'));
		let tick: (() => void) | undefined;
		let cancelled = false;
		const output: string[] = [];
		const stop = startElapsedTicker(
			Date.now() / 1000 - 5,
			(text) => output.push(text),
			((callback: () => void) => {
				tick = callback;
				return 1;
			}) as typeof setInterval,
			(() => {
				cancelled = true;
			}) as typeof clearInterval,
		);
		expect(output).toEqual(['5s']);
		tick!();
		tick!();
		expect(output).toEqual(['5s', '6s', '7s']);
		stop();
		expect(cancelled).toBe(true);
	});
});

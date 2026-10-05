import { describe, expect, it } from 'vitest';
import { estimateReleaseVelocity, stepRelease, type ReleaseState } from './physics';

function simulate(initial: ReleaseState, stepSeconds: number, totalSeconds: number): ReleaseState {
	let state = initial;
	for (let elapsed = 0; elapsed < totalSeconds - 0.000001; elapsed += stepSeconds) {
		state = stepRelease(state, stepSeconds, { x: 0, y: 0, width: 500, height: 500 }, 'gentle');
	}
	return state;
}

describe('Parsec release physics', () => {
	it('produces the same gentle release after equal elapsed time at different frame rates', () => {
		const initial: ReleaseState = { point: { x: 40, y: 40 }, velocity: { x: 180, y: 60 } };
		const fast = simulate(initial, 1 / 60, 0.5);
		const slow = simulate(initial, 1 / 20, 0.5);
		expect(fast.point.x).toBeCloseTo(slow.point.x, 5);
		expect(fast.point.y).toBeCloseTo(slow.point.y, 5);
		expect(fast.velocity.x).toBeCloseTo(slow.velocity.x, 5);
	});

	it('clamps sampled release velocity and makes carry-only release stationary', () => {
		const samples = [
			{ point: { x: 0, y: 0 }, at: 0 },
			{ point: { x: 1000, y: -1000 }, at: 100 },
		];
		expect(estimateReleaseVelocity(samples, 'gentle')).toEqual({ x: 650, y: -650 });
		expect(estimateReleaseVelocity(samples, 'carry-only')).toEqual({ x: 0, y: 0 });
	});

	it('bounds a full release inside the viewport with bounce', () => {
		const next = stepRelease(
			{ point: { x: 95, y: 95 }, velocity: { x: 500, y: 500 } },
			0.1,
			{ x: 0, y: 0, width: 100, height: 100 },
			'full',
		);
		expect(next.point.x).toBeLessThanOrEqual(100);
		expect(next.point.y).toBeLessThanOrEqual(100);
		expect(next.velocity.x).toBeLessThan(0);
		expect(next.velocity.y).toBeLessThan(0);
	});
});

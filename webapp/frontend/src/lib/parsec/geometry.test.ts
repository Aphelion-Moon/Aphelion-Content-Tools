import { describe, expect, it } from 'vitest';
import { clampPoint, denormalizePoint, normalizePoint, pointInRect } from './geometry';

describe('Parsec geometry', () => {
	it('clamps and round-trips a normalized furniture or companion position', () => {
		const viewport = { x: 0, y: 0, width: 100, height: 80 };
		expect(clampPoint({ x: 140, y: -10 }, viewport)).toEqual({ x: 100, y: 0 });
		expect(denormalizePoint(normalizePoint({ x: 50, y: 40 }, viewport), viewport)).toEqual({ x: 50, y: 40 });
	});

	it('handles zero-area bounds without producing NaN and includes rectangle edges', () => {
		const flat = { x: 4, y: 7, width: 0, height: 0 };
		expect(normalizePoint({ x: 99, y: -5 }, flat)).toEqual({ x: 0, y: 0 });
		expect(pointInRect({ x: 4, y: 7 }, flat)).toBe(true);
	});
});

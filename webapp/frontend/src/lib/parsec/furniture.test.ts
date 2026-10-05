import { describe, expect, it } from 'vitest';
import {
	DEFAULT_FURNITURE,
	canLeaveFurniture,
	clampFurniture,
	dropOnFurniture,
	moveFurniture,
	moveFurnitureByKeyboard,
	resetFurnitureHome,
	toggleCageLatch,
} from './furniture';

describe('Parsec furniture rules', () => {
	it('keeps an open cage open after drop and prevents autonomous exit once latched', () => {
		const dropped = dropOnFurniture(DEFAULT_FURNITURE, 'cage');
		expect(dropped.cage.status).toBe('open-occupied');
		const latched = toggleCageLatch(dropped);
		expect(latched.cage.status).toBe('latched-occupied');
		expect(canLeaveFurniture(latched, { source: 'autonomous' })).toBe(false);
		expect(canLeaveFurniture(latched, { source: 'release-command' })).toBe(true);
	});

	it('models bed timeout without making the bed a hard lock', () => {
		const resting = dropOnFurniture(DEFAULT_FURNITURE, 'bed', 'timeout');
		expect(resting.bed.mode).toBe('timeout');
		expect(canLeaveFurniture(resting, { source: 'pickup' })).toBe(true);
		expect(canLeaveFurniture(resting, { source: 'whistle' })).toBe(true);
	});

	it('moves globally, clamps after viewport shrink, and returns both objects home', () => {
		const moved = moveFurniture(
			moveFurniture(DEFAULT_FURNITURE, 'bed', { x: -2, y: 4 }, 'app-edge'),
			'cage',
			{ x: 3, y: -1 },
			'app-edge',
		);
		const clamped = clampFurniture(moved);
		expect(clamped.bed.position).toEqual({ x: 0, y: 1 });
		expect(clamped.cage.position).toEqual({ x: 1, y: 0 });
		expect(resetFurnitureHome(clamped)).toEqual(DEFAULT_FURNITURE);
	});

	it('moves furniture by a literal normalized keyboard step without changing its anchor', () => {
		const moved = moveFurnitureByKeyboard(DEFAULT_FURNITURE, 'bed', { x: 1, y: -1 });
		expect(moved.bed.position).toEqual({ x: 0.22, y: 0.72 });
		expect(moved.bed.anchor).toBe('habitat');
		expect(moved.cage).toEqual(DEFAULT_FURNITURE.cage);
	});
});

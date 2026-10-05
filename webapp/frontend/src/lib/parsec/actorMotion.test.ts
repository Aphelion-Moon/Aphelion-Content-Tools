import { describe, expect, it } from 'vitest';
import {
	actorPointFromLocation,
	directionForMovement,
	createReleaseSimulation,
	shouldChooseActorDestination,
} from './actorMotion';

describe('Parsec actor destination stability', () => {
	it('chooses authored directions from movement without mirroring eye laterality', () => {
		const origin = { x: 10, y: 10 };
		expect(directionForMovement(origin, { x: 0, y: 10 })).toBe('west');
		expect(directionForMovement(origin, { x: 10, y: 0 })).toBe('north');
		expect(directionForMovement(origin, { x: 20, y: 10 })).toBe('east');
		expect(directionForMovement(origin, { x: 10, y: 20 })).toBe('south');
		expect(directionForMovement(origin, { x: 0, y: 0 }, true)).toBe('north-west');
		expect(directionForMovement(origin, { x: 20, y: 0 }, true)).toBe('north-east');
		expect(directionForMovement(origin, { x: 0, y: 20 }, true)).toBe('south-west');
		expect(directionForMovement(origin, { x: 20, y: 20 }, true)).toBe('south-east');
		expect(directionForMovement(origin, origin)).toBeNull();
	});
	it('keeps direct manipulation points under gesture ownership', () => {
		expect(shouldChooseActorDestination(
			{ kind: 'transition', point: { x: 40, y: 50 } },
			{ kind: 'transition', point: { x: 80, y: 90 } },
		)).toBe(false);
		expect(actorPointFromLocation({ kind: 'transition', point: { x: 80, y: 90 } }))
			.toEqual({ x: 80, y: 90 });
	});

	it('does not choose another perch for an unchanged semantic destination', () => {
		expect(shouldChooseActorDestination(
			{ kind: 'perch', anchorId: 'shell-edge' },
			{ kind: 'perch', anchorId: 'shell-edge' },
		)).toBe(false);
	});

	it('chooses a destination when entering a different semantic location', () => {
		expect(shouldChooseActorDestination(
			{ kind: 'habitat' },
			{ kind: 'perch', anchorId: 'shell-edge' },
		)).toBe(true);
		expect(actorPointFromLocation({ kind: 'habitat' })).toBeNull();
	});
});

describe('Parsec release simulation', () => {
	it('advances full-tossing coordinates inside viewport bounds', () => {
		const simulation = createReleaseSimulation(
			{ point: { x: 100, y: 100 }, velocity: { x: 800, y: -500 } },
			{ x: 0, y: 0, width: 500, height: 400 },
			'full',
		);

		const moved = simulation.advance(0.016);

		expect(moved.point.x).toBeGreaterThan(100);
		expect(moved.point.y).toBeLessThan(100);
		expect(moved.settled).toBe(false);
	});

	it('preserves release velocity on the zero-duration first animation frame', () => {
		const simulation = createReleaseSimulation(
			{ point: { x: 100, y: 100 }, velocity: { x: 800, y: -500 } },
			{ x: 0, y: 0, width: 500, height: 400 },
			'full',
		);

		expect(simulation.advance(0)).toEqual({
			point: { x: 100, y: 100 },
			velocity: { x: 800, y: -500 },
			elapsedSeconds: 0,
			settled: false,
		});
	});

	it('settles carry-only releases immediately at a clamped point', () => {
		const simulation = createReleaseSimulation(
			{ point: { x: 600, y: -20 }, velocity: { x: 900, y: -700 } },
			{ x: 0, y: 0, width: 500, height: 400 },
			'carry-only',
		);

		expect(simulation.advance(0.016)).toEqual({
			point: { x: 500, y: 0 },
			velocity: { x: 0, y: 0 },
			elapsedSeconds: 0.016,
			settled: true,
		});
	});

	it('keeps a high-energy full toss active beyond 2.5 seconds but still settles by 4.5 seconds', () => {
		const simulation = createReleaseSimulation(
			{ point: { x: 1000, y: 2000 }, velocity: { x: 1200, y: -1200 } },
			{ x: 0, y: 0, width: 5000, height: 5000 },
			'full',
		);

		let snapshot = simulation.advance(0);
		for (let index = 0; index < 157; index += 1) snapshot = simulation.advance(0.016);

		expect(snapshot.elapsedSeconds).toBeCloseTo(2.512, 3);
		expect(snapshot.settled).toBe(false);

		for (let index = 0; index < 125; index += 1) snapshot = simulation.advance(0.016);

		expect(snapshot.elapsedSeconds).toBeCloseTo(4.512, 3);
		expect(snapshot.settled).toBe(true);
		expect(snapshot.point.x).toBeGreaterThanOrEqual(0);
		expect(snapshot.point.x).toBeLessThanOrEqual(5000);
		expect(snapshot.point.y).toBeGreaterThanOrEqual(0);
		expect(snapshot.point.y).toBeLessThanOrEqual(5000);
	});
});

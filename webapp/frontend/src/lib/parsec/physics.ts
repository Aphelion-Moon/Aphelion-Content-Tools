import { clampPoint, type Point, type Rect } from './geometry';

export type GrabPhysics = 'carry-only' | 'gentle' | 'full';

export interface PointerSample {
	point: Point;
	at: number;
}

export interface ReleaseState {
	point: Point;
	velocity: Point;
}

const GENTLE_MAX_SPEED = 650;
const FULL_MAX_SPEED = 1200;
const GENTLE_DAMPING_PER_SECOND = 8;
const GRAVITY_PIXELS_PER_SECOND_SQUARED = 900;
const BOUNCE_RESTITUTION = 0.55;

function clampVelocity(value: number, maximum: number): number {
	return Math.min(maximum, Math.max(-maximum, value));
}

export function estimateReleaseVelocity(samples: readonly PointerSample[], mode: GrabPhysics): Point {
	if (mode === 'carry-only' || samples.length < 2) return { x: 0, y: 0 };
	const first = samples[0]!;
	const last = samples[samples.length - 1]!;
	const elapsedSeconds = (last.at - first.at) / 1000;
	if (elapsedSeconds <= 0) return { x: 0, y: 0 };
	const maximum = mode === 'gentle' ? GENTLE_MAX_SPEED : FULL_MAX_SPEED;
	return {
		x: clampVelocity((last.point.x - first.point.x) / elapsedSeconds, maximum),
		y: clampVelocity((last.point.y - first.point.y) / elapsedSeconds, maximum),
	};
}

export function stepRelease(
	state: ReleaseState,
	seconds: number,
	bounds: Rect,
	mode: GrabPhysics,
): ReleaseState {
	if (mode === 'carry-only' || seconds <= 0) return { point: clampPoint(state.point, bounds), velocity: { x: 0, y: 0 } };
	if (mode === 'gentle') {
		const decay = Math.exp(-GENTLE_DAMPING_PER_SECOND * seconds);
		const travelFactor = (1 - decay) / GENTLE_DAMPING_PER_SECOND;
		const unclamped = {
			x: state.point.x + state.velocity.x * travelFactor,
			y: state.point.y + state.velocity.y * travelFactor,
		};
		const point = clampPoint(unclamped, bounds);
		return {
			point,
			velocity: {
				x: point.x === unclamped.x ? state.velocity.x * decay : 0,
				y: point.y === unclamped.y ? state.velocity.y * decay : 0,
			},
		};
	}

	let velocity = {
		x: state.velocity.x,
		y: state.velocity.y + GRAVITY_PIXELS_PER_SECOND_SQUARED * seconds,
	};
	const unclamped = {
		x: state.point.x + state.velocity.x * seconds,
		y: state.point.y + state.velocity.y * seconds + 0.5 * GRAVITY_PIXELS_PER_SECOND_SQUARED * seconds * seconds,
	};
	const point = clampPoint(unclamped, bounds);
	if (point.x !== unclamped.x) velocity = { ...velocity, x: -velocity.x * BOUNCE_RESTITUTION };
	if (point.y !== unclamped.y) velocity = { ...velocity, y: -velocity.y * BOUNCE_RESTITUTION };
	return { point, velocity };
}

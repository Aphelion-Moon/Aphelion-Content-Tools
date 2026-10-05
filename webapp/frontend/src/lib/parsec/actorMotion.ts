import type { CompanionLocation } from './companionTypes';
import type { Point, Rect } from './geometry';
import { stepRelease, type GrabPhysics, type ReleaseState } from './physics';

const MAX_INTEGRATION_STEP_SECONDS = 0.016;
const SETTLED_SPEED_PIXELS_PER_SECOND = 24;
const MAX_RELEASE_SECONDS = 4.5;

/** Select an authored view; never mirror asymmetric character artwork. */
export function directionForMovement(from: Point, to: Point, diagonal = false): string | null {
	const dx = to.x - from.x;
	const dy = to.y - from.y;
	if (!Number.isFinite(dx) || !Number.isFinite(dy) || (dx === 0 && dy === 0)) return null;
	if (diagonal) return `${dy < 0 ? 'north' : 'south'}-${dx < 0 ? 'west' : 'east'}`;
	return Math.abs(dx) >= Math.abs(dy) ? (dx < 0 ? 'west' : 'east') : (dy < 0 ? 'north' : 'south');
}

export interface ReleaseSimulationSnapshot extends ReleaseState {
	elapsedSeconds: number;
	settled: boolean;
}

export interface ReleaseSimulation {
	advance(elapsedSeconds: number): ReleaseSimulationSnapshot;
}

export function actorPointFromLocation(location: CompanionLocation): Point | null {
	if (location.kind === 'transition' || location.kind === 'roaming') return { ...location.point };
	return null;
}

export function shouldChooseActorDestination(
	previous: CompanionLocation,
	next: CompanionLocation,
): boolean {
	if (next.kind === 'transition' || next.kind === 'roaming') return false;
	if (next.kind === 'perch' && previous.kind === 'perch' && previous.anchorId === next.anchorId) return false;
	if (previous.kind !== next.kind) return true;
	if (next.kind === 'bed' && previous.kind === 'bed') return previous.mode !== next.mode;
	if (next.kind === 'cage' && previous.kind === 'cage') return previous.closed !== next.closed;
	return false;
}

export function createReleaseSimulation(
	initial: ReleaseState,
	bounds: Rect,
	mode: GrabPhysics,
): ReleaseSimulation {
	let state = { point: { ...initial.point }, velocity: { ...initial.velocity } };
	let elapsedSeconds = 0;
	let settled = false;

	return {
		advance(deltaSeconds): ReleaseSimulationSnapshot {
			let remaining = Math.max(0, deltaSeconds);
			if (remaining === 0) {
				if (mode === 'carry-only') state = stepRelease(state, 0, bounds, mode);
			} else {
				do {
					const stepSeconds = Math.min(MAX_INTEGRATION_STEP_SECONDS, remaining);
					state = stepRelease(state, stepSeconds, bounds, mode);
					remaining -= stepSeconds;
				} while (remaining > 0 && !settled);
			}
			elapsedSeconds += Math.max(0, deltaSeconds);
			const speed = Math.hypot(state.velocity.x, state.velocity.y);
			settled = mode === 'carry-only'
				|| speed <= SETTLED_SPEED_PIXELS_PER_SECOND
				|| elapsedSeconds >= MAX_RELEASE_SECONDS;
			return {
				point: { ...state.point },
				velocity: settled ? { x: 0, y: 0 } : { ...state.velocity },
				elapsedSeconds,
				settled,
			};
		},
	};
}

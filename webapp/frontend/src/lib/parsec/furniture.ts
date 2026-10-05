import type { Point } from './geometry';

export type FurnitureId = 'bed' | 'cage';
export type FurnitureAnchor = 'habitat' | 'app-edge';
export type CageStatus = 'open-empty' | 'open-occupied' | 'latched-empty' | 'latched-occupied';

export interface FurnitureState {
	bed: {
		position: Point;
		anchor: FurnitureAnchor;
		mode: 'empty' | 'voluntary' | 'timeout';
	};
	cage: {
		position: Point;
		anchor: FurnitureAnchor;
		status: CageStatus;
	};
}

export const DEFAULT_FURNITURE: FurnitureState = {
	bed: { position: { x: 0.18, y: 0.76 }, anchor: 'habitat', mode: 'empty' },
	cage: { position: { x: 0.72, y: 0.72 }, anchor: 'habitat', status: 'open-empty' },
};

function clampNormalized(point: Point): Point {
	return {
		x: Math.min(1, Math.max(0, point.x)),
		y: Math.min(1, Math.max(0, point.y)),
	};
}

export function moveFurniture(
	state: FurnitureState,
	id: FurnitureId,
	position: Point,
	anchor: FurnitureAnchor,
): FurnitureState {
	return id === 'bed'
		? { ...state, bed: { ...state.bed, position: { ...position }, anchor } }
		: { ...state, cage: { ...state.cage, position: { ...position }, anchor } };
}

export function moveFurnitureByKeyboard(
	state: FurnitureState,
	id: FurnitureId,
	direction: Point,
): FurnitureState {
	const current = state[id];
	return moveFurniture(
		state,
		id,
		{
			x: Math.min(1, Math.max(0, current.position.x + direction.x * 0.04)),
			y: Math.min(1, Math.max(0, current.position.y + direction.y * 0.04)),
		},
		current.anchor,
	);
}

export function dropOnFurniture(
	state: FurnitureState,
	id: FurnitureId,
	bedMode: 'voluntary' | 'timeout' = 'voluntary',
): FurnitureState {
	if (id === 'bed') return { ...state, bed: { ...state.bed, mode: bedMode } };
	const status: CageStatus = state.cage.status.startsWith('latched') ? 'latched-occupied' : 'open-occupied';
	return { ...state, cage: { ...state.cage, status } };
}

export function toggleCageLatch(state: FurnitureState): FurnitureState {
	const occupied = state.cage.status.endsWith('occupied');
	const latched = state.cage.status.startsWith('latched');
	const status: CageStatus = latched
		? occupied ? 'open-occupied' : 'open-empty'
		: occupied ? 'latched-occupied' : 'latched-empty';
	return { ...state, cage: { ...state.cage, status } };
}

export function canLeaveFurniture(
	state: FurnitureState,
	request: { source: 'autonomous' | 'pickup' | 'whistle' | 'release-command' },
): boolean {
	if (state.cage.status !== 'latched-occupied') return true;
	return request.source === 'release-command';
}

export function clampFurniture(state: FurnitureState): FurnitureState {
	return {
		bed: { ...state.bed, position: clampNormalized(state.bed.position) },
		cage: { ...state.cage, position: clampNormalized(state.cage.position) },
	};
}

export function resetFurnitureHome(_state: FurnitureState): FurnitureState {
	return {
		bed: { ...DEFAULT_FURNITURE.bed, position: { ...DEFAULT_FURNITURE.bed.position } },
		cage: { ...DEFAULT_FURNITURE.cage, position: { ...DEFAULT_FURNITURE.cage.position } },
	};
}

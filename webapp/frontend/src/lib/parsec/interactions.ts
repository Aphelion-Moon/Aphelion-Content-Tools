import type {
	CompanionInteractionIntent,
	CompanionState,
} from './companionTypes';
import type { Point } from './geometry';

export type InteractiveToolId = 'pat' | 'ball' | 'tug' | 'brush' | 'treat' | 'whistle';

export interface InteractionSample {
	point: Point;
	at: number;
}

export interface ToolInteractionSession {
	tool: Exclude<InteractiveToolId, 'pat' | 'whistle'>;
	started: InteractionSample;
	latest: InteractionSample;
}

export interface ToolInteractionStart {
	session: ToolInteractionSession | null;
	intents: CompanionInteractionIntent[];
}

function physicalInteractionBlocked(state: CompanionState): boolean {
	return state.location.kind === 'cage' && state.location.closed;
}

export function beginToolInteraction(
	tool: InteractiveToolId,
	state: CompanionState,
	sample: InteractionSample,
): ToolInteractionStart {
	if (tool === 'pat') return { session: null, intents: [{ type: 'pat-started', point: sample.point }] };
	if (tool === 'whistle') return { session: null, intents: [{ type: 'recall-requested' }] };
	if (physicalInteractionBlocked(state)) return { session: null, intents: [] };
	const session: ToolInteractionSession = { tool, started: sample, latest: sample };
	if (tool === 'ball') return { session, intents: [{ type: 'ball-placed', point: sample.point }] };
	if (tool === 'tug') return { session, intents: [{ type: 'tug-offered', point: sample.point }] };
	if (tool === 'brush') return { session, intents: [{ type: 'brush-started', point: sample.point }] };
	return { session, intents: [{ type: 'treat-offered', point: sample.point }] };
}

export function updateToolInteraction(
	session: ToolInteractionSession,
	sample: InteractionSample,
): CompanionInteractionIntent[] {
	const delta = {
		x: sample.point.x - session.latest.point.x,
		y: sample.point.y - session.latest.point.y,
	};
	session.latest = sample;
	if (session.tool === 'ball') return [{ type: 'ball-moved', point: sample.point }];
	if (session.tool === 'treat') return [{ type: 'treat-moved', point: sample.point }];
	if (session.tool === 'tug') {
		const total = Math.hypot(
			sample.point.x - session.started.point.x,
			sample.point.y - session.started.point.y,
		);
		return [{ type: 'tug-tension', tension: Math.min(1, Math.max(0, total / 120)) }];
	}
	const distance = Math.hypot(delta.x, delta.y);
	return distance === 0 ? [] : [{ type: 'brush-stroke', direction: { x: delta.x / distance, y: delta.y / distance } }];
}

export function finishToolInteraction(
	session: ToolInteractionSession,
	sample: InteractionSample,
): CompanionInteractionIntent[] {
	if (session.tool === 'tug') return [{ type: 'tug-released', point: sample.point }];
	if (session.tool === 'brush') return [{ type: 'brush-finished', point: sample.point }];
	if (session.tool === 'treat') return [{ type: 'treat-placed', point: sample.point }];
	const elapsedSeconds = Math.max(0.016, (sample.at - session.started.at) / 1000);
	return [{
		type: 'ball-thrown',
		point: sample.point,
		velocity: {
			x: Math.min(1000, Math.max(-1000, (sample.point.x - session.started.point.x) / elapsedSeconds)),
			y: Math.min(1000, Math.max(-1000, (sample.point.y - session.started.point.y) / elapsedSeconds)),
		},
	}];
}

import type {
	AutonomousBehavior,
	CompanionSettings,
	CompanionState,
	FamiliarityBand,
} from './companionTypes';

export type { AutonomousBehavior } from './companionTypes';

export interface RandomSource {
	next(): number;
}

export interface SchedulerContext {
	state: CompanionState;
	visible: boolean;
	typing: boolean;
	playInitiated: boolean;
	now: number;
	cooldowns: Partial<Record<'ambient' | 'cursor' | 'roam', number>>;
	recentBehaviors: AutonomousBehavior[];
}

export interface FamiliarityProfile {
	band: FamiliarityBand;
	preferences: string[];
	discoveredReactionIds: string[];
	interactionSignals: number;
}

export type FamiliarityInteraction =
	| { kind: 'pat'; at: number }
	| { kind: 'ball-returned'; at: number }
	| { kind: 'brush'; at: number }
	| { kind: 'tug-finished'; at: number }
	| { kind: 'treat'; at: number };

const BEHAVIORS: ReadonlyArray<{
	id: AutonomousBehavior;
	weight: number;
	family: 'ambient' | 'cursor' | 'roam';
	cooldownMs: number;
}> = [
	{ id: 'habitat-sniff', weight: 4, family: 'ambient', cooldownMs: 60_000 },
	{ id: 'perch-watch', weight: 3, family: 'ambient', cooldownMs: 60_000 },
	{ id: 'tail-wag', weight: 2, family: 'ambient', cooldownMs: 60_000 },
	{ id: 'cursor-chase', weight: 2, family: 'cursor', cooldownMs: 90_000 },
	{ id: 'edge-roam', weight: 3, family: 'roam', cooldownMs: 120_000 },
];

export function cooldownForBehavior(behavior: AutonomousBehavior) {
	return BEHAVIORS.find((entry) => entry.id === behavior)!;
}

function blocksAutonomy(context: SchedulerContext): boolean {
	const { state } = context;
	return !context.visible
		|| context.typing
		|| !['allowed', 'ask-each-time'].includes(state.consent)
		|| state.pendingExcursion !== null
		|| state.settings.presence === 'habitat-only'
		|| state.settings.reducedDistraction
		|| state.feedbackDuty === 'warning'
		|| state.feedbackDuty === 'error'
		|| state.feedbackDuty === 'working'
		|| ['held', 'playing', 'landing', 'returning'].includes(state.activity)
		|| state.location.kind === 'bed'
		|| (state.location.kind === 'cage' && state.location.closed);
}

export function eligibleBehaviors(context: SchedulerContext): AutonomousBehavior[] {
	if (blocksAutonomy(context)) return [];
	return BEHAVIORS
		.filter((behavior) => (context.cooldowns[behavior.family] ?? 0) <= context.now)
		.filter((behavior) => !context.recentBehaviors.includes(behavior.id))
		.filter((behavior) => (
			behavior.id !== 'cursor-chase'
			|| context.playInitiated
			|| context.state.settings.presence === 'intrusive'
		))
		.map((behavior) => behavior.id);
}

export function chooseBehavior(context: SchedulerContext, random: RandomSource): AutonomousBehavior | null {
	const eligible = new Set(eligibleBehaviors(context));
	const candidates = BEHAVIORS.filter((behavior) => eligible.has(behavior.id));
	if (candidates.length === 0) return null;
	const totalWeight = candidates.reduce((total, candidate) => total + candidate.weight, 0);
	let selection = Math.min(0.999999999, Math.max(0, random.next())) * totalWeight;
	for (const candidate of candidates) {
		selection -= candidate.weight;
		if (selection < 0) return candidate.id;
	}
	return candidates[candidates.length - 1]!.id;
}

const DELAY_RANGES: Record<CompanionSettings['idleChatter'], readonly [number, number]> = {
	off: [Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY],
	rare: [90_000, 180_000],
	occasional: [45_000, 90_000],
	frequent: [15_000, 30_000],
};

export function nextBehaviorDelay(settings: CompanionSettings, random: RandomSource): number {
	const [minimum, maximum] = DELAY_RANGES[settings.idleChatter];
	if (!Number.isFinite(minimum)) return minimum;
	const ratio = Math.min(1, Math.max(0, random.next()));
	return Math.round(minimum + (maximum - minimum) * ratio);
}

function familiarityBand(signals: number): FamiliarityBand {
	if (signals >= 40) return 3;
	if (signals >= 16) return 2;
	if (signals >= 4) return 1;
	return 0;
}

function interactionUnlock(interaction: FamiliarityInteraction): string | null {
	if (interaction.kind === 'ball-returned') return 'ball.proud-return';
	if (interaction.kind === 'tug-finished') return 'tug.victory-tumble';
	if (interaction.kind === 'brush') return 'brush.contented';
	return null;
}

/** Advance familiarity monotonically; timestamps are accepted for event ordering but never decay it. */
export function familiarityAfterInteraction(
	profile: FamiliarityProfile,
	interaction: FamiliarityInteraction,
): FamiliarityProfile {
	const interactionSignals = Math.min(255, profile.interactionSignals + 1);
	const discoveredReactionIds = [...profile.discoveredReactionIds];
	const unlock = interactionUnlock(interaction);
	if (unlock && !discoveredReactionIds.includes(unlock)) discoveredReactionIds.push(unlock);
	const preferences = [...profile.preferences];
	if (!preferences.includes(interaction.kind)) preferences.push(interaction.kind);
	return {
		band: Math.max(profile.band, familiarityBand(interactionSignals)) as FamiliarityBand,
		preferences,
		discoveredReactionIds,
		interactionSignals,
	};
}

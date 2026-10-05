import { describe, expect, it } from 'vitest';
import { initialCompanionState } from './companionReducer';
import {
	chooseBehavior,
	eligibleBehaviors,
	familiarityAfterInteraction,
	nextBehaviorDelay,
	type SchedulerContext,
} from './companionScheduler';
import {
	DEFAULT_COMPANION_SETTINGS,
	type CompanionProfileSeed,
} from './companionTypes';

const profile: CompanionProfileSeed = {
	consent: 'allowed',
	familiarity: 0,
	settings: DEFAULT_COMPANION_SETTINGS,
};

function context(overrides: Partial<SchedulerContext> = {}): SchedulerContext {
	return {
		state: initialCompanionState(profile),
		visible: true,
		typing: false,
		playInitiated: false,
		now: 10_000,
		cooldowns: {},
		recentBehaviors: [],
		...overrides,
	};
}

describe('autonomous behavior eligibility', () => {
	it('suppresses autonomous behavior while typing, hidden, caged, or handling an error', () => {
		const base = context();
		const blocked: SchedulerContext[] = [
			{ ...base, visible: false },
			{ ...base, typing: true },
			{ ...base, state: { ...base.state, location: { kind: 'cage', closed: true } } },
			{ ...base, state: { ...base.state, feedbackDuty: 'error' } },
			{ ...base, state: { ...base.state, feedbackDuty: 'working' } },
			{ ...base, state: { ...base.state, activity: 'playing' } },
			{ ...base, state: { ...base.state, activity: 'landing' } },
		];
		for (const blockedContext of blocked) expect(eligibleBehaviors(blockedContext)).toEqual([]);
	});

	it('keeps cursor chasing ineligible until play starts', () => {
		const edgeBiased = context();
		expect(eligibleBehaviors(edgeBiased)).not.toContain('cursor-chase');
		expect(eligibleBehaviors({ ...edgeBiased, playInitiated: true })).toContain('cursor-chase');
	});

	it('lets intrusive mode initiate cursor play when its other safety gates permit it', () => {
		const base = context();
		expect(eligibleBehaviors({
			...base,
			state: { ...base.state, settings: { ...base.state.settings, presence: 'intrusive' } },
		})).toContain('cursor-chase');
	});

	it('honors family cooldowns and recent-behavior repetition avoidance', () => {
		const base = context({
			cooldowns: { roam: 20_000 },
			recentBehaviors: ['tail-wag'],
		});
		const eligible = eligibleBehaviors(base);
		expect(eligible).not.toContain('edge-roam');
		expect(eligible).not.toContain('tail-wag');
	});
});

describe('deterministic scheduling', () => {
	it('selects from weighted eligible behavior using the injected random source', () => {
		const low = chooseBehavior(context(), { next: () => 0 });
		const high = chooseBehavior(context(), { next: () => 0.999 });
		expect(low).toBe('habitat-sniff');
		expect(high).toBe('edge-roam');
	});

	it('uses bounded deterministic delay ranges for rare chatter', () => {
		const settings = DEFAULT_COMPANION_SETTINGS;
		expect(nextBehaviorDelay(settings, { next: () => 0 })).toBe(90_000);
		expect(nextBehaviorDelay(settings, { next: () => 1 })).toBe(180_000);
	});
});

describe('soft familiarity', () => {
	it('unlocks variants without exposing points, hunger, or decay', () => {
		const next = familiarityAfterInteraction({
			band: 0,
			preferences: [],
			discoveredReactionIds: [],
			interactionSignals: 3,
		}, { kind: 'ball-returned', at: 100 });
		expect(next.band).toBe(1);
		expect(next.discoveredReactionIds).toContain('ball.proud-return');
		expect(next).not.toHaveProperty('xp');
		expect(next).not.toHaveProperty('hunger');
		expect(next).not.toHaveProperty('lastDecayAt');
	});

	it('bounds internal interaction signals and never reduces familiarity', () => {
		const next = familiarityAfterInteraction({
			band: 3,
			preferences: ['brush'],
			discoveredReactionIds: [],
			interactionSignals: 255,
		}, { kind: 'pat', at: 500 });
		expect(next.band).toBe(3);
		expect(next.interactionSignals).toBe(255);
	});
});

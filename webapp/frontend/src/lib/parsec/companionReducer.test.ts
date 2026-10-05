import { describe, expect, it } from 'vitest';
import {
	initialCompanionState,
	reduceCompanion,
} from './companionReducer';
import {
	DEFAULT_COMPANION_SETTINGS,
	REVIEWED_COMPANION_LINE_IDS,
	type CompanionProfileSeed,
	type CompanionState,
} from './companionTypes';

const zero = { x: 0, y: 0 };

function profile(overrides: Partial<CompanionProfileSeed> = {}): CompanionProfileSeed {
	return {
		consent: 'unconfigured',
		familiarity: 0,
		settings: DEFAULT_COMPANION_SETTINGS,
		...overrides,
	};
}

function stateAt(location: CompanionState['location']): CompanionState {
	return { ...initialCompanionState(profile({ consent: 'allowed' })), location };
}

describe('companion reducer priority and consent', () => {
	it('settles after brushing and cancels pending excursions when the user chooses another action', () => {
		const initial = initialCompanionState(profile({ consent: 'ask-each-time' }));
		const requested = reduceCompanion(initial, { type: 'autonomous-tick', now: 100 }).state;
		for (const intent of [
			{ type: 'whistle' }, { type: 'go-to-bed', mode: 'voluntary' }, { type: 'go-to-cage' },
			{ type: 'direct-interaction', action: 'ball' },
		] as const) {
			expect(reduceCompanion(requested, intent).state.pendingExcursion).toBeNull();
		}
		const brushing = reduceCompanion(initial, { type: 'brush-started', point: zero }).state;
		const finished = reduceCompanion(brushing, { type: 'brush-finished', point: zero }).state;
		expect(finished.activity).toBe('resting');
		expect(finished.clip).toBe('core-idle-seated');
	});
	it('asks for each excursion and preserves that preference after a single approval', () => {
		const initial = initialCompanionState(profile({ consent: 'ask-each-time' }));
		const request = reduceCompanion(initial, { type: 'autonomous-tick', now: 100, behavior: 'edge-roam' });
		expect(request.state.location.kind).toBe('habitat');
		expect(request.effects).toContainEqual({ type: 'request-invitation' });
		expect(reduceCompanion(request.state, { type: 'autonomous-tick', now: 101 }).effects).toEqual([]);
		const approved = reduceCompanion(request.state, { type: 'excursion-response', allow: true });
		expect(approved.state.location.kind).toBe('perch');
		expect(approved.state.consent).toBe('ask-each-time');
		expect(approved.state.pendingExcursion).toBeNull();
		const denied = reduceCompanion(request.state, { type: 'excursion-response', allow: false });
		expect(denied.state.location.kind).toBe('habitat');
		expect(denied.state.pendingExcursion).toBeNull();
	});

	it('maps intrusive autonomous families onto every accepted intrusive clip', () => {
		const initial = initialCompanionState(profile({
			consent: 'allowed',
			settings: { ...DEFAULT_COMPANION_SETTINGS, presence: 'intrusive' },
		}));
		const expected = {
			'habitat-sniff': 'intrusive-cursor-stalk',
			'cursor-chase': 'intrusive-cursor-pounce',
			'perch-watch': 'intrusive-loiter',
			'tail-wag': 'intrusive-demand-attention',
			'edge-roam': 'intrusive-zoomies',
		} as const;
		for (const [behavior, clipId] of Object.entries(expected)) {
			const transition = reduceCompanion(initial, { type: 'autonomous-tick', now: 10, behavior: behavior as keyof typeof expected });
			expect(transition.state.clip).toBe(clipId);
			expect(transition.effects).toContainEqual({ type: 'play-clip', clipId });
		}
	});

	it('starts and settles on the accepted core idle clip', () => {
		const initial = initialCompanionState(profile({ consent: 'allowed' }));
		expect(initial.clip).toBe('core-idle-seated');
		const settled = reduceCompanion({ ...initial, clip: 'feedback-success-wag' }, {
			type: 'clip-finished',
			clipId: 'feedback-success-wag',
		});
		expect(settled.state.clip).toBe('core-idle-seated');
	});

	it('queues a critical reaction while held and performs it after release', () => {
		const initial = initialCompanionState(profile({ consent: 'allowed' }));
		const held = reduceCompanion(initial, { type: 'grabbed', point: zero }).state;
		const warned = reduceCompanion(held, { type: 'feedback', duty: 'error', eventId: 'e1' });

		expect(warned.state.activity).toBe('held');
		expect(warned.state.queuedReaction?.type).toBe('feedback');
		expect(warned.effects).toContainEqual(expect.objectContaining({
			type: 'append-companion-line',
			eventId: 'e1',
		}));

		const released = reduceCompanion(warned.state, { type: 'released', point: zero, velocity: zero });
		expect(released.state.feedbackDuty).toBe('error');
		expect(released.state.queuedReaction).toBeNull();
		expect(released.effects).toContainEqual({ type: 'play-clip', clipId: 'error-anxious' });
	});

	it('does not roam before excursion consent and requests the invitation after direct contact', () => {
		const unconfigured = initialCompanionState(profile());
		expect(reduceCompanion(unconfigured, { type: 'autonomous-tick', now: 10 }).effects)
			.not.toContainEqual(expect.objectContaining({ type: 'move-to' }));

		expect(reduceCompanion(unconfigured, { type: 'direct-interaction', action: 'pat' }).effects)
			.toContainEqual({ type: 'request-invitation' });
	});

	it('keeps feedback delivery independent from consent', () => {
		const transition = reduceCompanion(initialCompanionState(profile()), {
			type: 'feedback',
			duty: 'working',
			eventId: 'fetch-1',
		});
		expect(transition.state.feedbackDuty).toBe('working');
		expect(transition.effects).toContainEqual(expect.objectContaining({
			type: 'append-companion-line',
			eventId: 'fetch-1',
		}));
	});
});

describe('companion reducer furniture rules', () => {
	it('never self-releases from a closed cage', () => {
		const caged = stateAt({ kind: 'cage', closed: true });
		const next = reduceCompanion(caged, { type: 'autonomous-tick', now: 10 });
		expect(next.state.location).toEqual(caged.location);
		expect(next.effects).not.toContainEqual(expect.objectContaining({ type: 'move-to' }));
	});

	it('only leaves a closed cage through an explicit release', () => {
		const caged = stateAt({ kind: 'cage', closed: true });
		expect(reduceCompanion(caged, { type: 'whistle' }).state.location).toEqual(caged.location);
		const released = reduceCompanion(caged, { type: 'release-cage' });
		expect(released.state.location).toEqual({ kind: 'habitat' });
		expect(released.effects).toContainEqual({ type: 'move-to', destination: { kind: 'habitat' } });
	});

	it('represents voluntary bed rest and timeout without a care penalty', () => {
		const initial = initialCompanionState(profile({ consent: 'allowed' }));
		const resting = reduceCompanion(initial, { type: 'go-to-bed', mode: 'timeout' });
		expect(resting.state.location).toEqual({ kind: 'bed', mode: 'timeout' });
		expect(resting.state.activity).toBe('sleeping');
		expect(resting.effects).not.toContainEqual(expect.objectContaining({ type: 'update-profile', penalty: expect.anything() }));
	});

	it('sequences bed approach and settling into the configured accepted rest clip', () => {
		const initial = initialCompanionState(profile({ consent: 'allowed' }));
		const approaching = reduceCompanion(initial, { type: 'go-to-bed', mode: 'voluntary' });
		expect(approaching.state.clip).toBe('habitat-bed-approach');
		expect(approaching.effects).toContainEqual({ type: 'play-clip', clipId: 'habitat-bed-approach' });
		const settling = reduceCompanion(approaching.state, { type: 'clip-finished', clipId: 'habitat-bed-approach' });
		expect(settling.state.clip).toBe('habitat-bed-lie-down');
		const sleeping = reduceCompanion(settling.state, { type: 'clip-finished', clipId: 'habitat-bed-lie-down' });
		expect(sleeping.state.clip).toBe('habitat-bed-sleep');

		const timeout = reduceCompanion(initial, { type: 'go-to-bed', mode: 'timeout' });
		const timeoutSettling = reduceCompanion(timeout.state, { type: 'clip-finished', clipId: 'habitat-bed-approach' });
		const pouting = reduceCompanion(timeoutSettling.state, { type: 'clip-finished', clipId: 'habitat-bed-lie-down' });
		expect(pouting.state.clip).toBe('habitat-bed-timeout-pout');
	});

	it('sequences cage entry, latch, and explicit release through accepted habitat clips', () => {
		const initial = initialCompanionState(profile({ consent: 'allowed' }));
		const entering = reduceCompanion(initial, { type: 'go-to-cage' });
		expect(entering.state.clip).toBe('habitat-cage-enter');
		const open = reduceCompanion(entering.state, { type: 'clip-finished', clipId: 'habitat-cage-enter' });
		expect(open.state.clip).toBe('habitat-cage-open-idle');
		const latched = reduceCompanion(open.state, { type: 'set-cage-latch', closed: true });
		expect(latched.state.clip).toBe('habitat-cage-latched-pout');
		expect(latched.effects).toContainEqual({ type: 'play-clip', clipId: 'habitat-cage-latched-pout' });
		const released = reduceCompanion(latched.state, { type: 'release-cage' });
		expect(released.state.clip).toBe('habitat-cage-release');
		expect(released.effects).toContainEqual({ type: 'play-clip', clipId: 'habitat-cage-release' });
	});
});

describe('companion reducer reviewed personality reactions', () => {
	it('uses the accepted soft and delighted pat clips as familiarity grows', () => {
		const newCompanion = initialCompanionState(profile({ consent: 'allowed' }));
		expect(reduceCompanion(newCompanion, { type: 'pat-started', point: zero }).effects)
			.toContainEqual({ type: 'play-clip', clipId: 'touch-pat-soft' });

		const familiar = initialCompanionState(profile({ consent: 'allowed', familiarity: 2 }));
		expect(reduceCompanion(familiar, { type: 'pat-started', point: zero }).effects)
			.toContainEqual({ type: 'play-clip', clipId: 'touch-pat-delighted' });
	});

	it('selects scruff motion from the configured personality and handling reaction', () => {
		const playful = initialCompanionState(profile({ consent: 'allowed' }));
		expect(reduceCompanion(playful, { type: 'grabbed', point: zero }).effects)
			.toContainEqual({ type: 'play-clip', clipId: 'touch-scruff-playful' });

		const subdued = initialCompanionState(profile({
			consent: 'allowed',
			settings: {
				...DEFAULT_COMPANION_SETTINGS,
				personalityTone: 'warm',
				handlingReactions: 'subdued',
			},
		}));
		expect(reduceCompanion(subdued, { type: 'grabbed', point: zero }).effects)
			.toContainEqual({ type: 'play-clip', clipId: 'touch-scruff-calm' });

		const huffy = initialCompanionState(profile({
			consent: 'allowed',
			settings: {
				...DEFAULT_COMPANION_SETTINGS,
				personalityTone: 'impish',
				handlingReactions: 'dramatic',
			},
		}));
		expect(reduceCompanion(huffy, { type: 'grabbed', point: zero }).effects)
			.toContainEqual({ type: 'play-clip', clipId: 'touch-scruff-pout' });
	});

	it('sequences configured releases through accepted landing clips', () => {
		const gentle = {
			...initialCompanionState(profile({ consent: 'allowed' })),
			activity: 'held' as const,
		};
		const dropped = reduceCompanion(gentle, { type: 'released', point: zero, velocity: { x: 300, y: 0 } });
		expect(dropped.effects).toContainEqual({ type: 'play-clip', clipId: 'touch-release-drop' });
		const dropLanding = reduceCompanion(dropped.state, { type: 'clip-finished', clipId: 'touch-release-drop' });
		expect(dropLanding.effects).toContainEqual({ type: 'play-clip', clipId: 'touch-landing-recover' });

		const fullToss = {
			...gentle,
			settings: { ...gentle.settings, handlingPhysics: 'full-tossing' as const },
		};
		const tossed = reduceCompanion(fullToss, { type: 'released', point: zero, velocity: { x: 900, y: 0 } });
		expect(tossed.effects).toContainEqual({ type: 'play-clip', clipId: 'touch-release-toss' });
		const bounced = reduceCompanion(tossed.state, { type: 'clip-finished', clipId: 'touch-release-toss' });
		expect(bounced.effects).toContainEqual({ type: 'play-clip', clipId: 'touch-landing-bounce' });
		const recovered = reduceCompanion(bounced.state, { type: 'clip-finished', clipId: 'touch-landing-bounce' });
		expect(recovered.effects).toContainEqual({ type: 'play-clip', clipId: 'touch-landing-recover' });
	});

	it('records a settled motion point without replacing the landing reaction', () => {
		const landing = {
			...initialCompanionState(profile({ consent: 'allowed' })),
			activity: 'landing' as const,
			location: { kind: 'roaming' as const, point: { x: 20, y: 30 } },
			clip: 'touch-release-toss',
		};

		const settled = reduceCompanion(landing, {
			type: 'motion-settled',
			point: { x: 240, y: 180 },
		});

		expect(settled.state.location).toEqual({ kind: 'roaming', point: { x: 240, y: 180 } });
		expect(settled.state.activity).toBe('landing');
		expect(settled.state.clip).toBe('touch-release-toss');
		expect(settled.effects).toEqual([]);
	});

	it('selects handling copy only from the reviewed line registry', () => {
		const initial = initialCompanionState(profile({
			consent: 'allowed',
			familiarity: 2,
			settings: {
				...DEFAULT_COMPANION_SETTINGS,
				handlingReactions: 'dramatic',
				personalityTone: 'playful-flirtatious',
			},
		}));
		const grabbed = reduceCompanion(initial, {
			type: 'grabbed',
			point: zero,
			movementSpeed: 18,
			repeatCount: 3,
			initiatedPlay: true,
		});
		const lineEffect = grabbed.effects.find((effect) => effect.type === 'append-companion-line');
		expect(lineEffect?.type).toBe('append-companion-line');
		if (lineEffect?.type === 'append-companion-line') {
			expect(REVIEWED_COMPANION_LINE_IDS).toContain(lineEffect.lineId);
			expect(lineEffect.lineId).toBe('handling.playful.dramatic.fast.familiar');
		}
	});

	it('routes the toy interaction lifecycle through the accepted toy clips', () => {
		const initial = initialCompanionState(profile({ consent: 'allowed', familiarity: 2 }));
		expect(reduceCompanion(initial, { type: 'ball-placed', point: zero }).state.clip).toBe('toy-ball-ready');
		expect(reduceCompanion(initial, { type: 'ball-moved', point: zero }).state.clip).toBe('toy-ball-chase');
		expect(reduceCompanion(initial, { type: 'ball-thrown', point: zero, velocity: zero }).state.clip).toBe('toy-ball-retrieve');
		expect(reduceCompanion(initial, { type: 'tug-offered', point: zero }).state.clip).toBe('toy-tug-grip');
		expect(reduceCompanion(initial, { type: 'tug-tension', tension: 0.75 }).state.clip).toBe('toy-tug-pull');
		expect(reduceCompanion(initial, { type: 'tug-released', point: zero }).state.clip).toBe('toy-tug-win');
		expect(reduceCompanion(initial, { type: 'brush-started', point: zero }).state.clip).toBe('toy-brush-content');
		expect(reduceCompanion(initial, { type: 'treat-placed', point: zero }).state.clip).toBe('toy-treat-accept');
		const recalled = reduceCompanion(initial, { type: 'recall-requested' });
		expect(recalled.state.clip).toBe('toy-whistle-recall');
		expect(recalled.effects).toContainEqual({ type: 'play-clip', clipId: 'toy-whistle-recall' });
	});

	it('uses impish dramatic toy reactions when configured', () => {
		const impish = initialCompanionState(profile({
			consent: 'allowed',
			settings: {
				...DEFAULT_COMPANION_SETTINGS,
				personalityTone: 'impish',
				handlingPhysics: 'full-tossing',
				handlingReactions: 'dramatic',
			},
		}));
		expect(reduceCompanion(impish, { type: 'ball-placed', point: zero }).state.clip).toBe('toy-ball-refuse');
		expect(reduceCompanion(impish, { type: 'tug-released', point: zero }).state.clip).toBe('toy-tug-tumble');
		expect(reduceCompanion(impish, { type: 'brush-stroke', direction: { x: 1, y: 0 } }).state.clip)
			.toBe('toy-brush-impatient');
	});
});

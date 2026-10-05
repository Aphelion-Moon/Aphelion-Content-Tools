import type {
	CompanionEffect,
	CompanionIntent,
	CompanionLocation,
	CompanionPoint,
	CompanionProfileSeed,
	CompanionState,
	CompanionTransition,
	FeedbackDuty,
	ReviewedCompanionLineId,
} from './companionTypes';
import type { ParsecAnimation } from './types';

const CORE_IDLE_CLIP = 'core-idle-seated';
const FULL_TOSS_THRESHOLD = 700;

const ORDINARY_AUTONOMOUS_CLIPS = {
	'habitat-sniff': 'core-idle-sniff',
	'perch-watch': 'core-look-cursor',
	'tail-wag': 'feedback-success-wag',
	'cursor-chase': 'core-walk-cardinal',
	'edge-roam': 'core-walk-cardinal',
} as const;

const INTRUSIVE_AUTONOMOUS_CLIPS = {
	'habitat-sniff': 'intrusive-cursor-stalk',
	'cursor-chase': 'intrusive-cursor-pounce',
	'perch-watch': 'intrusive-loiter',
	'tail-wag': 'intrusive-demand-attention',
	'edge-roam': 'intrusive-zoomies',
} as const;

const FEEDBACK_CLIPS: Record<FeedbackDuty, string> = {
	idle: CORE_IDLE_CLIP,
	working: 'feedback-working-focus',
	success: 'feedback-success-wag',
	warning: 'feedback-warning-alert',
	error: 'error-anxious',
};

const ANIMATION_CLIPS: Record<ParsecAnimation, string> = {
	idle: 'core-idle-seated',
	working: 'feedback-working-focus',
	happy: 'feedback-success-wag',
	twerking: 'twerking-reaction',
	search: 'search-sniff',
	fetch: 'fetch-dig',
	anxious: 'error-anxious',
	confused: 'empty-confused',
	growl: 'tool-growl',
	pant: 'reconnect-pant',
};

const FEEDBACK_LINES: Record<FeedbackDuty, ReviewedCompanionLineId> = {
	idle: 'feedback.idle',
	working: 'feedback.working',
	success: 'feedback.success',
	warning: 'feedback.warning',
	error: 'feedback.error',
};

export function initialCompanionState(profile: CompanionProfileSeed): CompanionState {
	return {
		activity: 'resting',
		mood: 'calm',
		attention: { kind: 'none', id: null },
		feedbackDuty: 'idle',
		location: { kind: 'habitat' },
		familiarity: profile.familiarity,
		clip: CORE_IDLE_CLIP,
		clipInstance: 0,
		queuedReaction: null,
		pendingExcursion: null,
		consent: profile.consent,
		settings: profile.settings,
	};
}

function feedbackMood(duty: FeedbackDuty): CompanionState['mood'] {
	if (duty === 'error') return 'anxious';
	if (duty === 'warning') return 'curious';
	if (duty === 'success') return 'proud';
	return 'calm';
}

function applyFeedback(
	state: CompanionState,
	intent: Extract<CompanionIntent, { type: 'feedback' }>,
	announce: boolean,
): CompanionTransition {
	const effects: CompanionEffect[] = [];
	if (announce) effects.push({ type: 'append-companion-line', lineId: FEEDBACK_LINES[intent.duty], eventId: intent.eventId });

	if (state.activity === 'held' && (intent.duty === 'warning' || intent.duty === 'error')) {
		return {
			state: {
				...state,
				feedbackDuty: intent.duty,
				attention: { kind: 'feedback', id: intent.eventId },
				queuedReaction: intent,
			},
			effects,
		};
	}

	const clip = intent.duty === 'warning'
		? FEEDBACK_CLIPS.warning
		: intent.animation ? ANIMATION_CLIPS[intent.animation] : FEEDBACK_CLIPS[intent.duty];
	effects.push({ type: 'play-clip', clipId: clip });
	return {
		state: {
			...state,
			activity: intent.duty === 'idle' ? 'resting' : 'responding',
			mood: feedbackMood(intent.duty),
			attention: intent.duty === 'idle'
				? { kind: 'none', id: null }
				: { kind: 'feedback', id: intent.eventId },
			feedbackDuty: intent.duty,
			clip,
			queuedReaction: null,
		},
		effects,
	};
}

function handlingLine(state: CompanionState, intent: Extract<CompanionIntent, { type: 'grabbed' }>): ReviewedCompanionLineId {
	const fast = (intent.movementSpeed ?? 0) >= 12 || (intent.repeatCount ?? 0) >= 3;
	const familiar = state.familiarity >= 2 || intent.initiatedPlay === true;
	if (
		state.settings.personalityTone === 'playful-flirtatious'
		&& state.settings.handlingReactions === 'dramatic'
		&& fast
		&& familiar
	) return 'handling.playful.dramatic.fast.familiar';
	if (
		state.settings.personalityTone === 'impish'
		&& state.settings.handlingReactions === 'dramatic'
		&& fast
		&& familiar
	) return 'handling.impish.dramatic.fast.familiar';
	if (state.settings.personalityTone === 'playful-flirtatious' && fast && familiar) {
		return 'handling.playful.expressive.fast.familiar';
	}
	if (state.settings.personalityTone === 'playful-flirtatious') return 'handling.playful.expressive.slow.new';
	return 'handling.warm.subdued.slow.new';
}

function patClip(state: CompanionState): string {
	if (state.familiarity >= 2 && state.settings.personalityTone !== 'warm') return 'touch-pat-delighted';
	return 'touch-pat-soft';
}

function handlingClip(state: CompanionState): string {
	if (state.settings.handlingReactions === 'subdued' || state.settings.personalityTone === 'warm') {
		return 'touch-scruff-calm';
	}
	if (state.settings.handlingReactions === 'dramatic' && state.settings.personalityTone === 'impish') {
		return 'touch-scruff-pout';
	}
	return 'touch-scruff-playful';
}

function releaseClip(state: CompanionState, velocity: CompanionPoint): string {
	const speed = Math.hypot(velocity.x, velocity.y);
	return state.settings.handlingPhysics === 'full-tossing' && speed >= FULL_TOSS_THRESHOLD
		? 'touch-release-toss'
		: 'touch-release-drop';
}

function isClosedCage(location: CompanionLocation): boolean {
	return location.kind === 'cage' && location.closed;
}

function toyTransition(
	state: CompanionState,
	clip: string,
	mood: CompanionState['mood'],
	attention: CompanionState['attention'],
): CompanionTransition {
	return {
		state: { ...state, activity: 'playing', mood, attention, clip },
		effects: [{ type: 'play-clip', clipId: clip }],
	};
}

function ballReadyClip(state: CompanionState): string {
	return state.settings.personalityTone === 'impish' && state.familiarity === 0
		? 'toy-ball-refuse'
		: 'toy-ball-ready';
}

function tugReleaseClip(state: CompanionState): string {
	return state.settings.handlingPhysics === 'full-tossing' && state.settings.handlingReactions === 'dramatic'
		? 'toy-tug-tumble'
		: 'toy-tug-win';
}

function brushClip(state: CompanionState): string {
	return state.settings.personalityTone === 'impish' && state.settings.handlingReactions === 'dramatic'
		? 'toy-brush-impatient'
		: 'toy-brush-content';
}

function recallTransition(state: CompanionState): CompanionTransition {
	const destination: CompanionLocation = { kind: 'habitat' };
	const clip = 'toy-whistle-recall';
	return {
		state: { ...state, activity: 'returning', attention: { kind: 'none', id: null }, location: destination, clip },
		effects: [
			{ type: 'cancel-schedule', scheduleId: 'autonomous' },
			{ type: 'move-to', destination },
			{ type: 'play-clip', clipId: clip },
		],
	};
}

export function reduceCompanion(state: CompanionState, intent: CompanionIntent): CompanionTransition {
	if (intent.type === 'feedback-cleared') {
		const wasResponding = state.activity === 'responding';
		const clip = state.location.kind === 'bed'
			? state.location.mode === 'timeout' ? 'habitat-bed-timeout-pout' : 'habitat-bed-sleep'
			: state.location.kind === 'cage'
				? state.location.closed ? 'habitat-cage-latched-pout' : 'habitat-cage-open-idle'
				: intent.working ? FEEDBACK_CLIPS.working : CORE_IDLE_CLIP;
		return {
			state: {
				...state,
				feedbackDuty: intent.working ? 'working' : 'idle',
				attention: state.attention.kind === 'feedback' ? { kind: 'none', id: null } : state.attention,
				queuedReaction: state.queuedReaction?.type === 'feedback' ? null : state.queuedReaction,
				...(wasResponding ? {
					activity: state.location.kind === 'bed' ? 'sleeping' : intent.working ? 'responding' : 'resting',
					clip,
				} : {}),
			},
			effects: wasResponding ? [{ type: 'play-clip', clipId: clip }] : [],
		};
	}
	if (state.pendingExcursion && !['autonomous-tick', 'excursion-response', 'clip-finished', 'motion-settled'].includes(intent.type)) {
		state = { ...state, pendingExcursion: null };
	}
	if (intent.type === 'excursion-response') {
		const pending = state.pendingExcursion;
		const cleared = { ...state, pendingExcursion: null };
		if (!intent.allow || !pending || state.consent !== 'ask-each-time') return { state: cleared, effects: [] };
		const approved = reduceCompanion({ ...cleared, consent: 'allowed' }, pending);
		return { ...approved, state: { ...approved.state, consent: state.consent } };
	}
	if (intent.type === 'feedback') return applyFeedback(state, intent, true);

	if (intent.type === 'release-cage' && isClosedCage(state.location)) {
		const destination: CompanionLocation = { kind: 'habitat' };
		const clip = 'habitat-cage-release';
		return {
			state: { ...state, activity: 'returning', mood: 'curious', location: destination, clip },
			effects: [
				{ type: 'append-companion-line', lineId: 'furniture.cage.released' },
				{ type: 'move-to', destination },
				{ type: 'play-clip', clipId: clip },
			],
		};
	}

	if (isClosedCage(state.location)) {
		if (intent.type === 'set-cage-latch' && !intent.closed) {
			const clip = 'habitat-cage-open-idle';
			return {
				state: { ...state, location: { kind: 'cage', closed: false }, mood: 'curious', clip },
				effects: [{ type: 'play-clip', clipId: clip }],
			};
		}
		if (intent.type === 'direct-interaction' && state.consent === 'unconfigured') {
			return { state, effects: [{ type: 'request-invitation' }] };
		}
		return { state, effects: [] };
	}

	switch (intent.type) {
		case 'autonomous-tick': {
			if (state.pendingExcursion || !['allowed', 'ask-each-time'].includes(state.consent) || state.settings.presence === 'habitat-only' || state.settings.reducedDistraction) {
				return { state, effects: [] };
			}
			if (['held', 'playing', 'landing', 'returning'].includes(state.activity) || ['working', 'warning', 'error'].includes(state.feedbackDuty) || state.location.kind === 'bed') {
				return { state, effects: [] };
			}
			if (state.consent === 'ask-each-time') {
				return { state: { ...state, pendingExcursion: intent }, effects: [{ type: 'request-invitation' }] };
			}
			const behavior = intent.behavior ?? 'edge-roam';
			const clip = state.settings.presence === 'intrusive'
				? INTRUSIVE_AUTONOMOUS_CLIPS[behavior]
				: ORDINARY_AUTONOMOUS_CLIPS[behavior];
			const destination: CompanionLocation = behavior === 'habitat-sniff' && state.settings.presence !== 'intrusive'
				? { kind: 'habitat' }
				: { kind: 'perch', anchorId: 'shell-edge' };
			return {
				state: { ...state, activity: 'roaming', mood: 'curious', location: destination, clip },
				effects: [{ type: 'move-to', destination }, { type: 'play-clip', clipId: clip }],
			};
		}
		case 'direct-interaction': {
			const effects: CompanionEffect[] = [];
			if (state.consent === 'unconfigured') effects.push({ type: 'request-invitation' });
			if (intent.action === 'pat') effects.push({ type: 'append-companion-line', lineId: 'interaction.pat' });
			const clip = intent.action === 'pat' ? patClip(state) : 'happy-reaction';
			return {
				state: { ...state, activity: 'playing', mood: 'affectionate', clip },
				effects: [...effects, { type: 'play-clip', clipId: clip }],
			};
		}
		case 'grabbed': {
			const clip = handlingClip(state);
			return {
				state: {
					...state,
					activity: 'held',
					mood: intent.initiatedPlay ? 'excited' : 'pouty',
					attention: { kind: 'cursor', id: 'scruff' },
					location: { kind: 'transition', point: intent.point },
					clip,
				},
				effects: [
					{ type: 'cancel-schedule', scheduleId: 'autonomous' },
					{ type: 'append-companion-line', lineId: handlingLine(state, intent) },
					{ type: 'play-clip', clipId: clip },
				],
			};
		}
		case 'held-moved':
			if (state.activity !== 'held') return { state, effects: [] };
			return {
				state: {
					...state,
					mood: intent.movementSpeed >= 12 ? 'excited' : state.mood,
					location: { kind: 'transition', point: intent.point },
				},
				effects: [],
			};
		case 'released': {
			const clip = releaseClip(state, intent.velocity);
			const releasedState: CompanionState = {
				...state,
				activity: 'landing',
				location: { kind: 'roaming', point: intent.point },
				attention: { kind: 'none', id: null },
				clip,
			};
			if (state.queuedReaction?.type === 'feedback') return applyFeedback(releasedState, state.queuedReaction, false);
			return { state: releasedState, effects: [{ type: 'play-clip', clipId: clip }] };
		}
		case 'motion-settled':
			return {
				state: { ...state, location: { kind: 'roaming', point: intent.point } },
				effects: [],
			};
		case 'go-to-bed': {
			const location: CompanionLocation = { kind: 'bed', mode: intent.mode };
			const clip = 'habitat-bed-approach';
			return {
				state: { ...state, activity: 'sleeping', mood: intent.mode === 'timeout' ? 'pouty' : 'calm', location, clip },
				effects: [
					{ type: 'append-companion-line', lineId: intent.mode === 'timeout' ? 'furniture.bed.timeout' : 'furniture.bed.voluntary' },
					{ type: 'move-to', destination: location },
					{ type: 'play-clip', clipId: clip },
				],
			};
		}
		case 'go-to-cage': {
			const location: CompanionLocation = { kind: 'cage', closed: false };
			const clip = 'habitat-cage-enter';
			return {
				state: { ...state, activity: 'resting', mood: 'curious', location, clip },
				effects: [
					{ type: 'append-companion-line', lineId: 'furniture.cage.enter' },
					{ type: 'move-to', destination: location },
					{ type: 'play-clip', clipId: clip },
				],
			};
		}
		case 'set-cage-latch':
			if (state.location.kind !== 'cage') return { state, effects: [] };
			{
				const clip = intent.closed ? 'habitat-cage-latched-pout' : 'habitat-cage-open-idle';
			return {
				state: { ...state, mood: intent.closed ? 'pouty' : 'curious', location: { kind: 'cage', closed: intent.closed }, clip },
				effects: [
					...(intent.closed ? [{ type: 'append-companion-line' as const, lineId: 'furniture.cage.closed' as const }] : []),
					{ type: 'play-clip', clipId: clip },
				],
			};
			}
		case 'release-cage':
			return { state, effects: [] };
		case 'whistle':
			return recallTransition(state);
		case 'invitation-response':
			return {
				state: { ...state, consent: intent.consent },
				effects: [{ type: 'update-profile', patch: { consent: intent.consent } }],
			};
		case 'clip-finished': {
			if (intent.clipId !== state.clip) return { state, effects: [] };
			const furnitureFollowup = intent.clipId === 'habitat-bed-approach'
				? 'habitat-bed-lie-down'
				: intent.clipId === 'habitat-bed-lie-down' && state.location.kind === 'bed'
					? state.location.mode === 'timeout' ? 'habitat-bed-timeout-pout' : 'habitat-bed-sleep'
					: intent.clipId === 'habitat-cage-enter' ? 'habitat-cage-open-idle' : null;
			if (furnitureFollowup) {
				return {
					state: { ...state, activity: state.location.kind === 'bed' ? 'sleeping' : 'resting', clip: furnitureFollowup },
					effects: [{ type: 'play-clip', clipId: furnitureFollowup }],
				};
			}
			const landingFollowup = {
				'touch-release-drop': 'touch-landing-recover',
				'touch-release-toss': 'touch-landing-bounce',
				'touch-landing-bounce': 'touch-landing-recover',
			}[intent.clipId];
			if (landingFollowup) {
				return {
					state: { ...state, activity: 'landing', clip: landingFollowup },
					effects: [{ type: 'play-clip', clipId: landingFollowup }],
				};
			}
			return { state: { ...state, activity: 'resting', clip: CORE_IDLE_CLIP }, effects: [] };
		}
		case 'pat-started': {
			const clip = patClip(state);
			return {
				state: { ...state, activity: 'playing', mood: 'affectionate', attention: { kind: 'cursor', id: 'pat' }, clip },
				effects: [{ type: 'play-clip', clipId: clip }],
			};
		}
		case 'ball-placed':
			return toyTransition(state, ballReadyClip(state), 'excited', { kind: 'toy', id: 'ball' });
		case 'ball-moved':
			return toyTransition(state, 'toy-ball-chase', 'excited', { kind: 'toy', id: 'ball' });
		case 'ball-thrown':
			return toyTransition(state, 'toy-ball-retrieve', 'excited', { kind: 'toy', id: 'ball' });
		case 'tug-offered':
			return toyTransition(state, 'toy-tug-grip', 'excited', { kind: 'toy', id: 'tug' });
		case 'tug-tension':
			return toyTransition(
				state,
				intent.tension >= 0.15 ? 'toy-tug-pull' : 'toy-tug-grip',
				'excited',
				{ kind: 'toy', id: 'tug' },
			);
		case 'tug-released':
			return toyTransition(state, tugReleaseClip(state), 'proud', { kind: 'toy', id: 'tug' });
		case 'brush-started':
		case 'brush-stroke':
			return toyTransition(state, brushClip(state), 'calm', { kind: 'cursor', id: 'brush' });
		case 'brush-finished':
			// The impatient one-shot may have settled before pointer release; attention owns the session.
			if (!['playing', 'resting'].includes(state.activity) || state.attention.kind !== 'cursor' || state.attention.id !== 'brush') return { state, effects: [] };
			return {
				state: { ...state, activity: 'resting', attention: { kind: 'none', id: null }, clip: CORE_IDLE_CLIP },
				effects: [{ type: 'play-clip', clipId: CORE_IDLE_CLIP }],
			};
		case 'treat-offered':
		case 'treat-moved':
		case 'treat-placed':
			return toyTransition(state, 'toy-treat-accept', 'affectionate', { kind: 'toy', id: 'treat' });
		case 'recall-requested':
			return recallTransition(state);
	}
}

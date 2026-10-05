import type { ParsecAnimation } from './types';

export type CompanionActivity =
	| 'resting'
	| 'observing'
	| 'responding'
	| 'playing'
	| 'roaming'
	| 'held'
	| 'landing'
	| 'returning'
	| 'sleeping';

export type CompanionMood =
	| 'calm'
	| 'curious'
	| 'excited'
	| 'pouty'
	| 'anxious'
	| 'frustrated'
	| 'proud'
	| 'affectionate';

export type FeedbackDuty = 'idle' | 'working' | 'success' | 'warning' | 'error';
export type ExcursionConsent = 'unconfigured' | 'allowed' | 'ask-each-time' | 'habitat-only';
export type FamiliarityBand = 0 | 1 | 2 | 3;
export type AutonomousBehavior = 'habitat-sniff' | 'perch-watch' | 'tail-wag' | 'cursor-chase' | 'edge-roam';

export interface CompanionPoint {
	x: number;
	y: number;
}

export type CompanionLocation =
	| { kind: 'habitat' }
	| { kind: 'perch'; anchorId: string }
	| { kind: 'roaming'; point: CompanionPoint }
	| { kind: 'bed'; mode: 'voluntary' | 'timeout' }
	| { kind: 'cage'; closed: boolean }
	| { kind: 'transition'; point: CompanionPoint };

export interface CompanionAudioSettings {
	enabled: boolean;
	master: number;
	voice: number;
	effects: number;
	alerts: number;
	rareIdle: number;
}

export interface CompanionSettings {
	presence: 'habitat-only' | 'edge-biased' | 'intrusive';
	idleChatter: 'off' | 'rare' | 'occasional' | 'frequent';
	motion: 'animate' | 'reduce';
	logMode: 'compact' | 'collapsed' | 'expanded';
	activityRetention: 7 | 30 | 90 | 365 | 'manual';
	personalityTone: 'warm' | 'playful-flirtatious' | 'impish';
	handlingPhysics: 'carry-only' | 'gentle-momentum' | 'full-tossing';
	handlingReactions: 'subdued' | 'expressive' | 'dramatic';
	feedbackPersonality: boolean;
	reducedDistraction: boolean;
	audio: CompanionAudioSettings;
}

export const DEFAULT_COMPANION_SETTINGS: CompanionSettings = {
	presence: 'edge-biased',
	idleChatter: 'rare',
	motion: 'animate',
	logMode: 'compact',
	activityRetention: 90,
	personalityTone: 'playful-flirtatious',
	handlingPhysics: 'gentle-momentum',
	handlingReactions: 'expressive',
	feedbackPersonality: true,
	reducedDistraction: false,
	audio: {
		enabled: true,
		master: 0.3,
		voice: 1,
		effects: 1,
		alerts: 1,
		rareIdle: 0.2,
	},
};

export interface CompanionProfileSeed {
	consent: ExcursionConsent;
	familiarity: FamiliarityBand;
	settings: CompanionSettings;
}

export type CompanionIntent =
	| { type: 'autonomous-tick'; now: number; behavior?: AutonomousBehavior }
	| { type: 'excursion-response'; allow: boolean }
	| { type: 'direct-interaction'; action: 'pat' | 'ball' | 'tug' | 'brush' | 'treat' | 'whistle' | 'bed' | 'cage' }
	| { type: 'feedback'; duty: FeedbackDuty; eventId: string; animation?: ParsecAnimation }
	| { type: 'feedback-cleared'; working: boolean }
	| { type: 'grabbed'; point: CompanionPoint; movementSpeed?: number; repeatCount?: number; initiatedPlay?: boolean }
	| { type: 'held-moved'; point: CompanionPoint; movementSpeed: number }
	| { type: 'released'; point: CompanionPoint; velocity: CompanionPoint }
	| { type: 'motion-settled'; point: CompanionPoint }
	| { type: 'go-to-bed'; mode: 'voluntary' | 'timeout' }
	| { type: 'go-to-cage' }
	| { type: 'set-cage-latch'; closed: boolean }
	| { type: 'release-cage' }
	| { type: 'whistle' }
	| { type: 'invitation-response'; consent: Exclude<ExcursionConsent, 'unconfigured'> }
	| { type: 'clip-finished'; clipId: string; instance?: number }
	| CompanionInteractionIntent;

export type CompanionInteractionIntent =
	| { type: 'pat-started'; point: CompanionPoint }
	| { type: 'ball-placed'; point: CompanionPoint }
	| { type: 'ball-moved'; point: CompanionPoint }
	| { type: 'ball-thrown'; point: CompanionPoint; velocity: CompanionPoint }
	| { type: 'tug-offered'; point: CompanionPoint }
	| { type: 'tug-tension'; tension: number }
	| { type: 'tug-released'; point: CompanionPoint }
	| { type: 'brush-started'; point: CompanionPoint }
	| { type: 'brush-stroke'; direction: CompanionPoint }
	| { type: 'brush-finished'; point: CompanionPoint }
	| { type: 'treat-offered'; point: CompanionPoint }
	| { type: 'treat-moved'; point: CompanionPoint }
	| { type: 'treat-placed'; point: CompanionPoint }
	| { type: 'recall-requested' };

export interface CompanionState {
	activity: CompanionActivity;
	mood: CompanionMood;
	attention: { kind: 'none' | 'cursor' | 'toy' | 'furniture' | 'feedback'; id: string | null };
	feedbackDuty: FeedbackDuty;
	location: CompanionLocation;
	familiarity: FamiliarityBand;
	clip: string;
	clipInstance: number;
	queuedReaction: CompanionIntent | null;
	pendingExcursion: Extract<CompanionIntent, { type: 'autonomous-tick' }> | null;
	consent: ExcursionConsent;
	settings: CompanionSettings;
}

export const REVIEWED_COMPANION_LINE_IDS = [
	'feedback.working',
	'feedback.success',
	'feedback.warning',
	'feedback.error',
	'feedback.idle',
	'interaction.pat',
	'handling.warm.subdued.slow.new',
	'handling.playful.expressive.slow.new',
	'handling.playful.expressive.fast.familiar',
	'handling.playful.dramatic.fast.familiar',
	'handling.impish.dramatic.fast.familiar',
	'furniture.bed.timeout',
	'furniture.bed.voluntary',
	'furniture.cage.enter',
	'furniture.cage.closed',
	'furniture.cage.released',
] as const;

export type ReviewedCompanionLineId = typeof REVIEWED_COMPANION_LINE_IDS[number];
export type CompanionDialogueLineId = Extract<ReviewedCompanionLineId, `handling.${string}` | `furniture.${string}`>;

export function isCompanionDialogueLine(lineId: ReviewedCompanionLineId): lineId is CompanionDialogueLineId {
	return lineId.startsWith('handling.') || lineId.startsWith('furniture.');
}

export type CompanionEffect =
	| { type: 'play-clip'; clipId: string }
	| { type: 'play-sound'; soundId: string }
	| { type: 'schedule-intent'; intent: CompanionIntent; delayMs: number; scheduleId: string }
	| { type: 'cancel-schedule'; scheduleId: string }
	| { type: 'move-to'; destination: CompanionLocation }
	| { type: 'append-companion-line'; lineId: ReviewedCompanionLineId; eventId?: string }
	| { type: 'update-profile'; patch: Partial<CompanionProfileSeed> }
	| { type: 'request-invitation' };

export interface CompanionTransition {
	state: CompanionState;
	effects: CompanionEffect[];
}

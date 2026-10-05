export type ParsecAnimation =
	| 'idle'
	| 'working'
	| 'happy'
	| 'twerking'
	| 'search'
	| 'fetch'
	| 'anxious'
	| 'confused'
	| 'growl'
	| 'pant';

export type ParsecPriority = 10 | 40 | 60 | 80 | 100;
export type ParsecFeedbackKind = 'info' | 'success' | 'warning' | 'error';
export type IdleChatterPreference = 'off' | 'rare' | 'occasional' | 'frequent';
export type ParsecLogMode = 'compact' | 'collapsed' | 'expanded';

export interface EventBase {
	readonly tool: string | null;
	readonly technicalDetail?: string;
	readonly dedupeKey?: string;
	readonly replacesKey?: string;
}

export type ParsecEvent =
	| ({ readonly type: 'search'; readonly phase: 'started' | 'completed' | 'empty' | 'failed' | 'superseded'; readonly query: string; readonly resultCount?: number } & EventBase)
	| ({ readonly type: 'fetch'; readonly phase: 'started' | 'delayed' | 'completed' | 'failed' | 'cancelled'; readonly summary: string } & EventBase)
	| ({ readonly type: 'mutation'; readonly phase: 'completed' | 'failed'; readonly summary: string } & EventBase)
	| ({ readonly type: 'job'; readonly phase: 'started' | 'progress' | 'completed' | 'failed'; readonly summary: string } & EventBase)
	| ({ readonly type: 'connection'; readonly phase: 'connected' | 'disconnected' | 'polling' | 'recovered' } & EventBase)
	| ({ readonly type: 'validation'; readonly phase: 'warning' | 'blocked' | 'failed'; readonly summary: string } & EventBase)
	| ({ readonly type: 'navigation'; readonly phase: 'context-changed'; readonly route: string } & EventBase)
	| ({ readonly type: 'interaction'; readonly phase: 'pat' | 'repeated-pat' } & EventBase)
	| ({ readonly type: 'interaction'; readonly phase: 'companion'; readonly lineId: CompanionDialogueLineId } & EventBase)
	| ({ readonly type: 'idle'; readonly phase: 'contextual'; readonly route: string; readonly lineIndex?: number } & EventBase)
	| ({ readonly type: 'notice'; readonly phase: 'info' | 'success' | 'error'; readonly summary: string } & EventBase);

export interface ParsecFeedbackDraft {
	readonly text: string;
	readonly kind: ParsecFeedbackKind;
	readonly animation: ParsecAnimation;
	readonly tool: string | null;
	readonly technicalDetail: string | null;
	readonly dedupeKey: string | null;
}

export interface ParsecFeedback extends ParsecFeedbackDraft {
	readonly id: number;
	readonly priority: ParsecPriority;
	readonly at: number;
}
import type { CompanionDialogueLineId } from './companionTypes';


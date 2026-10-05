import type { ParsecAnimation, ParsecEvent, ParsecFeedback } from './types';
import { redactTechnicalDetail } from './redaction';

const MAX_PARSEC_TEXT_LENGTH = 1_000;

export type ActivityRetentionDays = 7 | 30 | 90 | 365 | 'manual';
export type ActivityOutcome = 'started' | 'completed' | 'cancelled' | 'warning' | 'failed' | 'notice';

export interface ActivityRecord {
	readonly schemaVersion: 1;
	readonly id: string;
	readonly at: number;
	readonly eventType: ParsecEvent['type'];
	readonly phase: string;
	readonly tool: string | null;
	readonly route: string | null;
	readonly contextId: string | null;
	readonly durationMs: number | null;
	readonly resultCount: number | null;
	readonly outcome: ActivityOutcome;
	readonly technicalDetail: string | null;
	readonly parsecText: string | null;
	readonly reaction: ParsecAnimation | null;
}

export interface ActivityQuery {
	readonly limit: number;
	readonly cursor?: ActivityCursor | undefined;
	readonly before?: number;
	readonly after?: number;
	readonly eventType?: ParsecEvent['type'];
	readonly tool?: string;
	readonly outcome?: ActivityOutcome;
	readonly text?: string;
}

export interface ActivityCursor {
	readonly at: number;
	readonly id: string;
}

export interface ActivityPage {
	readonly records: readonly ActivityRecord[];
	readonly nextCursor: ActivityCursor | null;
}

export interface ActivityRecordContext {
	readonly route?: string | null;
	readonly contextId?: string | null;
	readonly durationMs?: number | null;
}

export interface ActivityJournal {
	append(record: ActivityRecord): Promise<void>;
	query(query: ActivityQuery): Promise<readonly ActivityRecord[]>;
	queryPage(query: ActivityQuery): Promise<ActivityPage>;
	prune(retention: ActivityRetentionDays, now: number): Promise<number>;
	clear(): Promise<number>;
	close(): void;
}

function outcomeForEvent(event: ParsecEvent): ActivityOutcome {
	switch (event.phase) {
		case 'started':
		case 'delayed':
		case 'progress':
		case 'polling':
			return 'started';
		case 'completed':
		case 'connected':
		case 'recovered':
		case 'success':
		case 'context-changed':
			return 'completed';
		case 'cancelled':
		case 'superseded':
			return 'cancelled';
		case 'warning':
		case 'blocked':
		case 'empty':
			return 'warning';
		case 'failed':
		case 'disconnected':
		case 'error':
			return 'failed';
		default:
			return 'notice';
	}
}

export function recordForFeedback(
	event: ParsecEvent,
	feedback: ParsecFeedback,
	context: ActivityRecordContext,
): ActivityRecord {
	return {
		schemaVersion: 1,
		id: `parsec:${crypto.randomUUID()}`,
		at: feedback.at,
		eventType: event.type,
		phase: event.phase,
		tool: feedback.tool,
		route: context.route ?? null,
		contextId: context.contextId ?? null,
		durationMs: context.durationMs ?? null,
		resultCount: event.type === 'search' ? event.resultCount ?? null : null,
		outcome: outcomeForEvent(event),
		technicalDetail: redactTechnicalDetail(feedback.technicalDetail ?? event.technicalDetail),
		parsecText: feedback.text.slice(0, MAX_PARSEC_TEXT_LENGTH),
		reaction: feedback.animation,
	};
}

import type { ParsecEvent, ParsecPriority } from './types';

export interface FeedbackTimingInput {
	readonly kind: 'info' | 'success' | 'warning' | 'error';
	readonly text: string;
}

export interface IdleEligibilityContext {
	readonly documentVisible: boolean;
	readonly editableFocused: boolean;
	readonly activeRunCount: number;
	readonly hasFeedback: boolean;
	readonly connectionNeedsAttention: boolean;
}

export function priorityForEvent(_event: ParsecEvent): ParsecPriority {
	const event = _event;
	if (
		(event.type === 'search' && event.phase === 'failed')
		|| (event.type === 'fetch' && event.phase === 'failed')
		|| (event.type === 'mutation' && event.phase === 'failed')
		|| (event.type === 'job' && event.phase === 'failed')
		|| (event.type === 'validation' && event.phase === 'failed')
		|| (event.type === 'notice' && event.phase === 'error')
	) return 100;
	if (event.type === 'validation' && (event.phase === 'blocked' || event.phase === 'warning')) return 80;
	if (
		(event.type === 'search' && event.phase === 'completed')
		|| (event.type === 'fetch' && event.phase === 'completed')
		|| (event.type === 'mutation' && event.phase === 'completed')
		|| (event.type === 'job' && event.phase === 'completed')
		|| (event.type === 'connection' && (event.phase === 'connected' || event.phase === 'recovered'))
		|| (event.type === 'notice' && event.phase === 'success')
	) return 60;
	if (event.type === 'idle' || event.type === 'navigation' || (event.type === 'interaction' && event.phase === 'companion')) return 10;
	return 40;
}

export function shouldDelayFeedback(event: ParsecEvent): boolean {
	return (
		(event.type === 'search' && event.phase === 'started')
		|| (event.type === 'fetch' && event.phase === 'started')
	);
}

export function dwellMsForFeedback(feedback: FeedbackTimingInput): number {
	if (feedback.kind === 'error') return 8000;
	if (feedback.kind === 'warning') return 6000;
	return feedback.text.length > 120 ? 6000 : 4000;
}

export function canEmitIdle(context: IdleEligibilityContext): boolean {
	return (
		context.documentVisible
		&& !context.editableFocused
		&& context.activeRunCount === 0
		&& !context.hasFeedback
		&& !context.connectionNeedsAttention
	);
}

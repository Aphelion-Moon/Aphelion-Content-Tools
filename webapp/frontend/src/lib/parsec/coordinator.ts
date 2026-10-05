import type { ParsecEvent, ParsecFeedback } from './types';
import { getBrowserActivityJournal } from './indexedDbJournal';
import { recordForFeedback, type ActivityRecord, type ActivityRecordContext } from './journalTypes';
import { dwellMsForFeedback, priorityForEvent, shouldDelayFeedback } from './policy';
import { voiceForEvent } from './voice';
import { isCompanionDialogueLine, type ReviewedCompanionLineId } from './companionTypes';
import {
	appendParsecLog,
	appState,
	isJobRunning,
	setParsecFeedback,
	setParsecJournalDiagnostic,
	setParsecState,
} from '~/store/appStore';

const DELAYED_FEEDBACK_MS = 350;
const MAX_PENDING = 5;
export type ParsecFeedbackListener = (feedback: ParsecFeedback | null, event?: ParsecEvent) => void;
const acceptedFeedbackListeners = new Set<ParsecFeedbackListener>();

export interface ParsecCoordinatorEnvironment<TimerHandle = ReturnType<typeof setTimeout>> {
	readonly now: () => number;
	readonly setTimer: (callback: () => void, delayMs: number) => TimerHandle;
	readonly clearTimer: (handle: TimerHandle) => void;
	readonly publish: ParsecFeedbackListener;
	readonly context: () => ActivityRecordContext;
	readonly record: (feedback: ParsecFeedback, activityId: string) => void;
	readonly recordActivity: (record: ActivityRecord) => void | Promise<void>;
	readonly activityFailure: (error: unknown) => void;
}

export interface ParsecCoordinator {
	report(event: ParsecEvent): number;
	dismiss(id?: number): void;
	pendingCount(): number;
	snapshot(): readonly ParsecFeedback[];
	flushActivity(): Promise<void>;
}

export function createParsecCoordinator<TimerHandle>(
	environment: ParsecCoordinatorEnvironment<TimerHandle>,
): ParsecCoordinator {
	let nextId = 1;
	let current: ParsecFeedback | null = null;
	let currentTimer: TimerHandle | null = null;
	let queue: ParsecFeedback[] = [];
	const delayedByKey = new Map<string, TimerHandle>();
	const eventsById = new Map<number, ParsecEvent>();
	let activityChain = Promise.resolve();
	let lastConnectionPhase: Extract<ParsecEvent, { type: 'connection' }>['phase'] | null = null;

	function clearCurrentTimer(): void {
		if (currentTimer === null) return;
		environment.clearTimer(currentTimer);
		currentTimer = null;
	}

	function scheduleExpiry(feedback: ParsecFeedback): void {
		clearCurrentTimer();
		currentTimer = environment.setTimer(() => {
			if (current?.id !== feedback.id) return;
			current = null;
			currentTimer = null;
			environment.publish(null);
			const next = queue.shift();
			if (next) publish(next);
		}, dwellMsForFeedback(feedback));
	}

	function publish(feedback: ParsecFeedback): void {
		current = feedback;
		const event = eventsById.get(feedback.id);
		environment.publish(feedback, event);
		if (event) {
			const activity = recordForFeedback(event, feedback, environment.context());
			environment.record(feedback, activity.id);
			activityChain = activityChain
				.then(() => environment.recordActivity(activity))
				.catch((error: unknown) => environment.activityFailure(error));
			eventsById.delete(feedback.id);
		}
		scheduleExpiry(feedback);
	}

	function removeMatchingKey(key: string): boolean {
		let removedDelayed = false;
		const delayed = delayedByKey.get(key);
		if (delayed !== undefined) {
			environment.clearTimer(delayed);
			delayedByKey.delete(key);
			removedDelayed = true;
		}
		queue = queue.filter((feedback) => {
			if (feedback.dedupeKey !== key) return true;
			eventsById.delete(feedback.id);
			return false;
		});
		return removedDelayed;
	}

	function enqueue(feedback: ParsecFeedback): void {
		queue.push(feedback);
		queue.sort((left, right) => right.priority - left.priority || left.id - right.id);
		if (queue.length > MAX_PENDING) {
			for (const dropped of queue.slice(MAX_PENDING)) eventsById.delete(dropped.id);
			queue = queue.slice(0, MAX_PENDING);
		}
	}

	function accept(event: ParsecEvent, id: number): void {
		const spoken = voiceForEvent(event);
		const feedback: ParsecFeedback = {
			...spoken,
			id,
			priority: priorityForEvent(event),
			at: environment.now(),
		};
		eventsById.set(id, event);

		if (feedback.dedupeKey) removeMatchingKey(feedback.dedupeKey);
		if (!current) {
			publish(feedback);
			return;
		}
		if (feedback.priority > current.priority) {
			clearCurrentTimer();
			current = null;
			publish(feedback);
			return;
		}
		enqueue(feedback);
	}

	function delayedEvent(event: ParsecEvent): ParsecEvent {
		if (event.type === 'fetch' && event.phase === 'started') return { ...event, phase: 'delayed' };
		return event;
	}

	return {
		report: (event) => {
			const id = nextId++;
			if (event.type === 'navigation') return id;
			if (event.type === 'connection') {
				if (event.phase === lastConnectionPhase) return id;
				lastConnectionPhase = event.phase;
			}
			const key = event.dedupeKey ?? `event:${id}`;
			const replacedDelayed = event.dedupeKey ? removeMatchingKey(event.dedupeKey) : false;
			if (
				replacedDelayed
				&& ((event.type === 'fetch' && event.phase === 'completed')
					|| (event.type === 'search' && event.phase === 'completed'))
			) return id;
			if (!shouldDelayFeedback(event)) {
				accept(event, id);
				return id;
			}
			const timer = environment.setTimer(() => {
				delayedByKey.delete(key);
				accept(delayedEvent(event), id);
			}, DELAYED_FEEDBACK_MS);
			delayedByKey.set(key, timer);
			return id;
		},
		dismiss: (id) => {
			if (id !== undefined && current?.id !== id) {
				queue = queue.filter((feedback) => {
					if (feedback.id !== id) return true;
					eventsById.delete(feedback.id);
					return false;
				});
				return;
			}
			clearCurrentTimer();
			current = null;
			environment.publish(null);
			const next = queue.shift();
			if (next) publish(next);
		},
		pendingCount: () => queue.length,
		snapshot: () => current ? [current, ...queue] : [...queue],
		flushActivity: () => activityChain,
	};
}

async function appendBrowserActivity(record: ActivityRecord): Promise<void> {
	const opened = await getBrowserActivityJournal();
	setParsecJournalDiagnostic(opened.diagnostic);
	await opened.journal.append(record);
}

const browserCoordinator = createParsecCoordinator({
	now: () => Date.now() / 1000,
	setTimer: (callback, delayMs) => setTimeout(callback, delayMs),
	clearTimer: (handle) => clearTimeout(handle),
	publish: (feedback, event) => {
		setParsecFeedback(feedback);
		if (!(event?.type === 'interaction' && event.phase === 'companion')) setParsecState(feedback?.animation ?? (isJobRunning() ? 'working' : 'idle'));
		for (const listener of acceptedFeedbackListeners) listener(feedback, event);
	},
	context: () => ({
		route: appState.activeRoute,
		contextId: appState.selectedContext?.record_id ?? null,
	}),
	record: (feedback, activityId) => appendParsecLog(feedback, activityId),
	recordActivity: appendBrowserActivity,
	activityFailure: () => setParsecJournalDiagnostic('append-failed'),
});

let reactionTimer: ReturnType<typeof setTimeout> | undefined;

export function reportParsec(event: ParsecEvent): number {
	return browserCoordinator.report(event);
}

export function reportCompanionLine(lineId: ReviewedCompanionLineId): void {
	// Application feedback and pats already have a coordinator event and one history owner.
	if (isCompanionDialogueLine(lineId)) reportParsec({ type: 'interaction', phase: 'companion', lineId, tool: 'parsec' });
}

export function dismissParsec(id?: number): void {
	browserCoordinator.dismiss(id);
}

export function flushParsecActivity(): Promise<void> {
	return browserCoordinator.flushActivity();
}

/** Accepted presentation changes, including expiry/dismissal; event identifies companion-owned dialogue. */
export function subscribeParsecFeedback(listener: ParsecFeedbackListener): () => void {
	acceptedFeedbackListeners.add(listener);
	return () => acceptedFeedbackListeners.delete(listener);
}

export function reactParsec(animation: 'happy' | 'twerking', durationMs = 900): void {
	setParsecState(animation);
	if (reactionTimer !== undefined) clearTimeout(reactionTimer);
	reactionTimer = setTimeout(() => {
		setParsecState(isJobRunning() ? 'working' : 'idle');
		reactionTimer = undefined;
	}, durationMs);
}

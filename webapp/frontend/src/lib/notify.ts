import { recordAnnouncement, setParsecState, isJobRunning, type AnnouncementKind } from '~/store/appStore';

// Parsec remains the app's standard feedback surface (see references/maintainer-guide.md). This module is
// the single entry point: it records the announcement into the shared store, drives her reaction, and lets
// the AppShell render the bubble. Pre-rewrite, `announceError`/`announceSuccess` were redeclared in three
// page scripts; they are now imported from here.

const REACTION_MS = 900;

let reactionTimer: number | undefined;

/** Play a one-shot reaction, reverting to whatever the job status implies once it elapses. */
export function react(state: 'happy' | 'twerking', durationMs = REACTION_MS): void {
	setParsecState(state);
	if (reactionTimer !== undefined) clearTimeout(reactionTimer);
	reactionTimer = setTimeout(() => {
		setParsecState(isJobRunning() ? 'working' : 'idle');
		reactionTimer = undefined;
	}, durationMs) as unknown as number;
}

export function announce(message: string, kind: AnnouncementKind = 'info', tool: string | null = null): void {
	if (!message) return;
	recordAnnouncement(message, kind, tool);
	if (kind === 'success') react('happy');
}

export function announceSuccess(message: string, tool: string | null = null): void {
	announce(message, 'success', tool);
}

export function announceError(error: unknown, tool: string | null = null): void {
	const message = error instanceof Error ? error.message : String(error);
	announce(message, 'error', tool);
}

import type { AnnouncementKind } from '~/store/appStore';
import { reactParsec, reportParsec } from '~/lib/parsec/coordinator';

// Parsec remains the app's standard feedback surface (see references/maintainer-guide.md). This module is
// the single entry point: it records the announcement into the shared store, drives her reaction, and lets
// the AppShell render the bubble. Pre-rewrite, `announceError`/`announceSuccess` were redeclared in three
// page scripts; they are now imported from here.

/** Play a one-shot reaction, reverting to whatever the job status implies once it elapses. */
export function react(state: 'happy' | 'twerking', durationMs = REACTION_MS): void {
	reactParsec(state, durationMs);
}

const REACTION_MS = 900;

export function announce(message: string, kind: AnnouncementKind = 'info', tool: string | null = null): void {
	if (!message) return;
	reportParsec({
		type: 'notice',
		phase: kind === 'warning' ? 'info' : kind,
		tool,
		summary: message,
	});
}

export function announceSuccess(message: string, tool: string | null = null): void {
	announce(message, 'success', tool);
}

export function announceError(error: unknown, tool: string | null = null): void {
	const message = error instanceof Error ? error.message : String(error);
	reportParsec({
		type: 'notice',
		phase: 'error',
		tool,
		summary: message,
		technicalDetail: message,
	});
}

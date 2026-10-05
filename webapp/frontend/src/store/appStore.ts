import { createStore, produce } from 'solid-js/store';
import type { components } from '~/lib/api-schema';
import type { ParsecAnimation, ParsecFeedback } from '~/lib/parsec/types';

// The one source of truth for cross-tool state. This replaces three separate ad hoc mechanisms from the
// pre-rewrite frontend: `window.__aphelionParsecShared` (a global object that existed only because every
// script re-executed its IIFE on each SPA navigation), `store-status-widget.js`'s module-level cache
// variables, and the several independent 5-second setInterval polls that each widget ran on its own.
// One WebSocket connection now feeds this store and every component reads from it reactively.

export type AnnouncementKind = 'info' | 'success' | 'warning' | 'error';

export interface Announcement {
	readonly id: number;
	readonly message: string;
	readonly kind: AnnouncementKind;
	readonly tool: string | null;
	readonly technicalDetail: string | null;
	readonly at: number;
}

export interface ParsecLogLine {
	readonly id: string;
	readonly activityId: string;
	readonly feedbackId: number;
	readonly message: string;
	readonly kind: AnnouncementKind;
	readonly tool: string | null;
	readonly technicalDetail: string | null;
	readonly reaction: ParsecAnimation;
	readonly at: number;
	readonly unread: boolean;
}

export type ParsecJournalDiagnostic =
	| 'indexeddb-unavailable'
	| 'open-failed'
	| 'unsupported-schema'
	| 'append-failed';

// Sourced from the backend's OpenAPI schema (`npm run gen:api`), not hand-written. A renamed Pydantic
// field now fails `tsc` here instead of arriving in the UI as `undefined`.
export type ActiveRun = components['schemas']['ActiveRun'];
export type DefinitionRun = components['schemas']['EditorRun'];
export type StoreHealth = components['schemas']['StoreHealth'];
export type SearchResult = components['schemas']['SearchResult'];
export type SelectedContext = components['schemas']['SelectedSearchContext'];

export type WorkspaceRevision = components['schemas']['WorkspaceRevisionResponse'];

export type ParsecState = ParsecAnimation;

export interface AppState {
	health: StoreHealth | null;
	activeRuns: readonly ActiveRun[];
	definitionRuns: readonly DefinitionRun[];
	announcements: readonly Announcement[];
	parsecLog: readonly ParsecLogLine[];
	parsecJournalDiagnostic: ParsecJournalDiagnostic | null;
	connected: boolean;
	parsecState: ParsecState;
	parsecFeedback: ParsecFeedback | null;
	activeRoute: string;
	selectedContext: SelectedContext | null;
	workspaceRevision: WorkspaceRevision | null;
}

export const ANNOUNCEMENT_LIMIT = 20;
export const PARSEC_LIVE_LOG_LIMIT = 50;

const [state, setState] = createStore<AppState>({
	health: null,
	activeRuns: [],
	definitionRuns: [],
	announcements: [],
	parsecLog: [],
	parsecJournalDiagnostic: null,
	connected: false,
	parsecState: 'idle',
	parsecFeedback: null,
	activeRoute: '/',
	selectedContext: null,
	workspaceRevision: null,
});

export { state as appState };

let nextAnnouncementId = 1;
let workspaceRevisionKey = '';

function revisionKey(revision: WorkspaceRevision | null): string {
	return revision === null ? '' : JSON.stringify(revision);
}

export function recordAnnouncement(
	message: string,
	kind: AnnouncementKind,
	tool: string | null,
	technicalDetail: string | null = null,
): Announcement {
	const announcement: Announcement = {
		id: nextAnnouncementId++,
		message,
		kind,
		tool,
		technicalDetail,
		at: Date.now() / 1000,
	};
	setState(
		produce((draft) => {
			const next = [announcement, ...draft.announcements];
			draft.announcements = next.slice(0, ANNOUNCEMENT_LIMIT);
		}),
	);
	return announcement;
}

export function appendParsecLog(feedback: ParsecFeedback, activityId: string): ParsecLogLine {
	const line: ParsecLogLine = {
		id: activityId,
		activityId,
		feedbackId: feedback.id,
		message: feedback.text,
		kind: feedback.kind,
		tool: feedback.tool,
		technicalDetail: feedback.technicalDetail,
		reaction: feedback.animation,
		at: feedback.at,
		unread: true,
	};
	setState(
		produce((draft) => {
			draft.parsecLog = [line, ...draft.parsecLog].slice(0, PARSEC_LIVE_LOG_LIMIT);
		}),
	);
	recordAnnouncement(feedback.text, feedback.kind, feedback.tool, feedback.technicalDetail);
	return line;
}

export function clearParsecLiveLog(): void {
	setState('parsecLog', []);
}

export function setParsecJournalDiagnostic(diagnostic: ParsecJournalDiagnostic | null): void {
	setState('parsecJournalDiagnostic', diagnostic);
}

export function setHealth(health: StoreHealth | null): void {
	setState('health', health);
}

export function setActiveRuns(runs: readonly ActiveRun[]): void {
	setState('activeRuns', runs);
	// Parsec's resting state follows whether real work is happening; a one-shot reaction (happy/twerking)
	// is set separately and reverts to whatever this last wrote.
	setState('parsecState', isJobRunning() ? 'working' : 'idle');
}

export function setConnected(connected: boolean): void {
	setState('connected', connected);
}

export function setParsecState(next: ParsecState): void {
	setState('parsecState', next);
}

export function setParsecFeedback(feedback: ParsecFeedback | null): void {
	setState('parsecFeedback', feedback);
}

export function setActiveRoute(route: string): void {
	setState('activeRoute', route);
}

export function setSelectedContext(context: SelectedContext | null): void {
	setState('selectedContext', context);
}

export function setWorkspaceRevision(revision: WorkspaceRevision | null): void {
	const nextKey = revisionKey(revision);
	if (nextKey === workspaceRevisionKey) return;
	const changed = workspaceRevisionKey !== '' && nextKey !== workspaceRevisionKey;
	workspaceRevisionKey = nextKey;
	setState(
		produce((draft) => {
			draft.workspaceRevision = revision;
			if (changed) draft.selectedContext = null;
		}),
	);
}

export function isJobRunning(): boolean {
	return state.activeRuns.length > 0 || state.definitionRuns.some((run) => run.status === 'running' || run.status === 'queued' || run.operation === 'interactive' && run.status === 'ready');
}

export function setDefinitionRuns(runs: readonly DefinitionRun[]): void {
	setState('definitionRuns', [...runs]);
	setState('parsecState', isJobRunning() ? 'working' : 'idle');
}

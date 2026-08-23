import { createStore, produce } from 'solid-js/store';
import type { components } from '~/lib/api-schema';

// The one source of truth for cross-tool state. This replaces three separate ad hoc mechanisms from the
// pre-rewrite frontend: `window.__aphelionParsecShared` (a global object that existed only because every
// script re-executed its IIFE on each SPA navigation), `store-status-widget.js`'s module-level cache
// variables, and the several independent 5-second setInterval polls that each widget ran on its own.
// One WebSocket connection now feeds this store and every component reads from it reactively.

export type AnnouncementKind = 'info' | 'success' | 'error';

export interface Announcement {
	readonly id: number;
	readonly message: string;
	readonly kind: AnnouncementKind;
	readonly tool: string | null;
	readonly at: number;
}

// Sourced from the backend's OpenAPI schema (`npm run gen:api`), not hand-written. A renamed Pydantic
// field now fails `tsc` here instead of arriving in the UI as `undefined`.
export type ActiveRun = components['schemas']['ActiveRun'];
export type StoreHealth = components['schemas']['StoreHealth'];
export type SearchResult = components['schemas']['SearchResult'];
export type SelectedContext = components['schemas']['SelectedSearchContext'];

export type ParsecState = 'idle' | 'working' | 'happy' | 'twerking';

export interface AppState {
	health: StoreHealth | null;
	activeRuns: readonly ActiveRun[];
	announcements: readonly Announcement[];
	connected: boolean;
	parsecState: ParsecState;
	selectedContext: SelectedContext | null;
}

export const ANNOUNCEMENT_LIMIT = 20;

const [state, setState] = createStore<AppState>({
	health: null,
	activeRuns: [],
	announcements: [],
	connected: false,
	parsecState: 'idle',
	selectedContext: null,
});

export { state as appState };

let nextAnnouncementId = 1;

export function recordAnnouncement(message: string, kind: AnnouncementKind, tool: string | null): Announcement {
	const announcement: Announcement = {
		id: nextAnnouncementId++,
		message,
		kind,
		tool,
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

export function setHealth(health: StoreHealth | null): void {
	setState('health', health);
}

export function setActiveRuns(runs: readonly ActiveRun[]): void {
	setState('activeRuns', runs);
	// Parsec's resting state follows whether real work is happening; a one-shot reaction (happy/twerking)
	// is set separately and reverts to whatever this last wrote.
	setState('parsecState', runs.length > 0 ? 'working' : 'idle');
}

export function setConnected(connected: boolean): void {
	setState('connected', connected);
}

export function setParsecState(next: ParsecState): void {
	setState('parsecState', next);
}

export function setSelectedContext(context: SelectedContext | null): void {
	setState('selectedContext', context);
}

export function isJobRunning(): boolean {
	return state.activeRuns.length > 0;
}

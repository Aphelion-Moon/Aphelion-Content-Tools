import { describe, expect, it } from 'vitest';
import {
	ANNOUNCEMENT_LIMIT,
	PARSEC_LIVE_LOG_LIMIT,
	appendParsecLog,
	appState,
	clearParsecLiveLog,
	recordAnnouncement,
	setActiveRuns,
	setDefinitionRuns,
	type DefinitionRun,
	setActiveRoute,
	setParsecFeedback,
	setSelectedContext,
	setWorkspaceRevision,
	type ActiveRun,
} from './appStore';
import type { ParsecFeedback } from '~/lib/parsec/types';

describe('announcement log', () => {
	it('returns most-recent-first and caps at the limit, dropping the oldest', () => {
		const total = ANNOUNCEMENT_LIMIT + 5;
		for (let i = 0; i < total; i += 1) {
			recordAnnouncement(`message ${i}`, 'info', 'test');
		}
		expect(appState.announcements).toHaveLength(ANNOUNCEMENT_LIMIT);
		expect(appState.announcements[0]?.message).toBe(`message ${total - 1}`);
		expect(appState.announcements.at(-1)?.message).toBe(`message ${total - ANNOUNCEMENT_LIMIT}`);
	});

	it('retains exact technical detail separately from the spoken message', () => {
		recordAnnouncement('*growls in frustration.* Save failed.', 'error', 'lore-editor', 'HTTP 500: write failed');

		expect(appState.announcements[0]?.message).toBe('*growls in frustration.* Save failed.');
		expect(appState.announcements[0]?.technicalDetail).toBe('HTTP 500: write failed');
	});
});

describe('active runs drive Parsec resting state', () => {
	const run: ActiveRun = { run_id: 'r1', tool_id: 'refresh', status: 'running', queued_at: 0 };

	it('switches to working while a job is active and back to idle when none are', () => {
		setActiveRuns([run]);
		expect(appState.parsecState).toBe('working');

		setActiveRuns([]);
		expect(appState.parsecState).toBe('idle');
	});
});

describe('definition runs drive Parsec resting state', () => {
	it('keeps working during interactive previews and across independent run updates', () => {
		const preview = { id: 'preview', operation: 'interactive', status: 'ready' } as DefinitionRun;
		setDefinitionRuns([preview]);
		expect(appState.parsecState).toBe('working');
		setActiveRuns([]);
		expect(appState.parsecState).toBe('working');
		setDefinitionRuns([{ ...preview, status: 'cancelled' }]);
		expect(appState.parsecState).toBe('idle');
		setDefinitionRuns([]);
	});
});

describe('shared selected context', () => {
	it('clears selection after dataset activation even when content and Git revisions match', () => {
		const revision = { worktree_id: 'worktree', branch: 'main', head: 'head', content_revision: 'content', projection_revision: null, projection_generation_id: 'first', game_source: null };
		setWorkspaceRevision(revision);
		setSelectedContext({ tool: 'content-graph', record_kind: 'module', record_id: 'module:example', groups: [] });
		setWorkspaceRevision({ ...revision, projection_generation_id: 'second' });
		expect(appState.selectedContext).toBeNull();
		setWorkspaceRevision(null);
	});

	it('clears selection when the selected game revision changes', () => {
		const revision = { worktree_id: 'worktree', branch: 'main', head: 'head', content_revision: 'content', projection_revision: null, projection_generation_id: null, game_source: { worktree_id: 'game', head: 'first' } };
		setWorkspaceRevision(revision);
		setSelectedContext({ tool: 'content-graph', record_kind: 'module', record_id: 'module:example', groups: [] });
		setWorkspaceRevision({ ...revision, game_source: { worktree_id: 'game', head: 'second' } });
		expect(appState.selectedContext).toBeNull();
		setWorkspaceRevision(null);
	});

	it('persists the selected record for cross-tool contextual search', () => {
		setSelectedContext({
			tool: 'lore-editor',
			record_kind: 'catalog_target',
			record_id: '/obj/item/radio',
			type_path: '/obj/item/radio',
			groups: ['items'],
		});

		expect(appState.selectedContext?.record_id).toBe('/obj/item/radio');
		expect(appState.selectedContext?.groups).toEqual(['items']);
	});

	it('clears revision-bound context when the workspace changes', () => {
		setWorkspaceRevision(null);
		setWorkspaceRevision({ worktree_id: 'worktree', branch: 'main', head: 'head-1', content_revision: 'content-1', projection_revision: null, projection_generation_id: null, game_source: null });
		setSelectedContext({
			tool: 'lore-editor',
			record_kind: 'catalog_target',
			record_id: '/obj/item/radio',
			type_path: '/obj/item/radio',
			groups: ['items'],
		});

		setWorkspaceRevision({ worktree_id: 'worktree', branch: 'main', head: 'head-2', content_revision: 'content-2', projection_revision: null, projection_generation_id: null, game_source: null });

		expect(appState.workspaceRevision?.head).toBe('head-2');
		expect(appState.selectedContext).toBeNull();
		setWorkspaceRevision(null);
	});
});

describe('Parsec presentation state', () => {
	it('publishes feedback and active route through the one shared store', () => {
		const feedback: ParsecFeedback = {
			id: 42,
			text: '*wuffs softly.* Loading.',
			kind: 'info',
			animation: 'fetch',
			priority: 40,
			tool: 'lore-editor',
			technicalDetail: null,
			dedupeKey: 'entry:radio',
			at: 123,
		};

		setParsecFeedback(feedback);
		setActiveRoute('/lore-editor');

		expect(appState.parsecFeedback).toEqual(feedback);
		expect(appState.activeRoute).toBe('/lore-editor');
		setParsecFeedback(null);
	});

	it('keeps a bounded newest-first live log linked to durable activity IDs', () => {
		clearParsecLiveLog();
		for (let index = 0; index < PARSEC_LIVE_LOG_LIMIT + 2; index += 1) {
			appendParsecLog({
				id: 100 + index,
				text: `line ${index}`,
				kind: 'info',
				animation: 'idle',
				priority: 10,
				tool: 'parsec',
				technicalDetail: null,
				dedupeKey: null,
				at: 200 + index,
			}, `activity-${index}`);
		}

		expect(appState.parsecLog).toHaveLength(PARSEC_LIVE_LOG_LIMIT);
		expect(appState.parsecLog[0]?.message).toBe(`line ${PARSEC_LIVE_LOG_LIMIT + 1}`);
		expect(appState.parsecLog[0]?.activityId).toBe(`activity-${PARSEC_LIVE_LOG_LIMIT + 1}`);
		expect(appState.announcements[0]?.message).toBe(`line ${PARSEC_LIVE_LOG_LIMIT + 1}`);
	});

	it('clears the live projection without changing other shared application state', () => {
		setActiveRoute('/content-graph');
		clearParsecLiveLog();

		expect(appState.parsecLog).toEqual([]);
		expect(appState.activeRoute).toBe('/content-graph');
	});
});

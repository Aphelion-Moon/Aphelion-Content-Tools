import { describe, expect, it } from 'vitest';
import {
	ANNOUNCEMENT_LIMIT,
	appState,
	recordAnnouncement,
	setActiveRuns,
	setSelectedContext,
	type ActiveRun,
} from './appStore';

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

describe('shared selected context', () => {
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
});

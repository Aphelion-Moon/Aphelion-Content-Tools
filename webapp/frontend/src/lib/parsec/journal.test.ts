import { describe, expect, it } from 'vitest';
import {
	createActivityJournal,
	createMemoryJournalBackend,
	recordsToCsv,
	recordsToJson,
} from './journal';
import type { ActivityCursor, ActivityRecord } from './journalTypes';

const DAY_SECONDS = 24 * 60 * 60;

function recordAt(
	day: number,
	eventType: ActivityRecord['eventType'],
	overrides: Partial<ActivityRecord> = {},
): ActivityRecord {
	return {
		schemaVersion: 1,
		id: `event-${day}-${eventType}`,
		at: day * DAY_SECONDS,
		eventType,
		phase: 'completed',
		tool: 'lore-editor',
		route: '/lore-editor',
		contextId: null,
		durationMs: null,
		resultCount: null,
		outcome: 'completed',
		technicalDetail: null,
		parsecText: `record ${day}`,
		reaction: 'happy',
		...overrides,
	};
}

describe('Parsec activity journal', () => {
	it('returns newest matching records and prunes records older than the retention boundary', async () => {
		const journal = createActivityJournal(createMemoryJournalBackend());
		await journal.append(recordAt(1, 'search'));
		await journal.append(recordAt(10, 'notice'));
		await journal.append(recordAt(100, 'fetch'));

		expect(await journal.prune(90, 100 * DAY_SECONDS)).toBe(1);
		expect((await journal.query({ limit: 50 })).map((entry) => entry.eventType))
			.toEqual(['fetch', 'notice']);
	});

	it('does not prune records when retention is manual', async () => {
		const journal = createActivityJournal(createMemoryJournalBackend());
		await journal.append(recordAt(1, 'search'));

		expect(await journal.prune('manual', 500 * DAY_SECONDS)).toBe(0);
		expect(await journal.query({ limit: 50 })).toHaveLength(1);
	});

	it('filters by allowlisted fields and transcript text before applying the limit', async () => {
		const journal = createActivityJournal(createMemoryJournalBackend());
		await journal.append(recordAt(1, 'search', { parsecText: '*sniffs.* old radio', outcome: 'warning' }));
		await journal.append(recordAt(2, 'fetch', { parsecText: '*wuffs.* radio loaded', outcome: 'completed' }));
		await journal.append(recordAt(3, 'fetch', { tool: 'content-graph', parsecText: 'unrelated graph' }));

		const records = await journal.query({
			limit: 1,
			tool: 'lore-editor',
			eventType: 'fetch',
			outcome: 'completed',
			text: 'RADIO',
		});

		expect(records.map((entry) => entry.id)).toEqual(['event-2-fetch']);
	});

	it('clears activity without requiring backend-specific behavior', async () => {
		const journal = createActivityJournal(createMemoryJournalBackend());
		await journal.append(recordAt(1, 'search'));
		await journal.clear();

		expect(await journal.query({ limit: 50 })).toEqual([]);
	});

	it('pages tied timestamps in stable database key order without gaps or duplicates', async () => {
		const journal = createActivityJournal(createMemoryJournalBackend());
		for (const id of ['z', 'Z', 'a', '-', '_']) await journal.append(recordAt(1, 'search', { id }));
		const ids: string[] = [];
		let cursor: ActivityCursor | undefined;
		do {
			const page = await journal.queryPage({ limit: 2, cursor });
			ids.push(...page.records.map((record) => record.id));
			cursor = page.nextCursor ?? undefined;
		} while (cursor);
		expect(ids).toEqual(['z', 'a', '_', 'Z', '-']);
	});

	it('returns the actual clear count beyond the query page limit', async () => {
		const journal = createActivityJournal(createMemoryJournalBackend());
		for (let id = 0; id < 1_007; id += 1) await journal.append(recordAt(1, 'search', { id: String(id) }));
		expect(await journal.clear()).toBe(1_007);
		expect(await journal.query({ limit: 1 })).toEqual([]);
	});
});

describe('Parsec activity export', () => {
	it('escapes spreadsheet formulas and quotes in CSV cells', () => {
		const csv = recordsToCsv([
			recordAt(1, 'notice', {
				parsecText: '=HYPERLINK("bad")',
				technicalDetail: '+CMD|station',
			}),
		]);

		expect(csv).toContain("'=HYPERLINK(\"\"bad\"\")");
		expect(csv).toContain("'+CMD|station");
	});

	it('exports the versioned records as readable JSON without changing them', () => {
		const record = recordAt(2, 'fetch');
		expect(JSON.parse(recordsToJson([record]))).toEqual([record]);
	});
});

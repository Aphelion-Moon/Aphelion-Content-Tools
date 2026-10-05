import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createActivityJournal, createMemoryJournalBackend } from '~/lib/parsec/journal';
import type { ActivityJournal, ActivityRecord } from '~/lib/parsec/journalTypes';
import ActivityHistory, { type ActivityHistoryDownload } from './ActivityHistory';

function record(id: string, text: string, tool = 'lore-editor'): ActivityRecord {
	const now = Date.now() / 1_000;
	return {
		schemaVersion: 1,
		id,
		at: id === 'new' ? now : now - 100,
		eventType: id === 'new' ? 'fetch' : 'search',
		phase: id === 'new' ? 'failed' : 'completed',
		tool,
		route: '/lore-editor',
		contextId: 'record:/obj/item/radio',
		durationMs: 12,
		resultCount: id === 'new' ? null : 2,
		outcome: id === 'new' ? 'failed' : 'completed',
		technicalDetail: id === 'new' ? 'HTTP 500' : null,
		parsecText: text,
		reaction: id === 'new' ? 'growl' : 'happy',
	};
}

async function waitFor(predicate: () => boolean): Promise<void> {
	for (let attempt = 0; attempt < 20; attempt += 1) {
		if (predicate()) return;
		await Promise.resolve();
	}
	throw new Error('Expected component state did not settle.');
}

afterEach(() => {
	window.localStorage.clear();
	document.body.replaceChildren();
});

	describe('Parsec activity history', () => {
	it('loads newest-first records and filters the real journal by text', async () => {
		const journal = createActivityJournal(createMemoryJournalBackend());
		await journal.append(record('old', '*sniffs.* Found radio records.'));
		await journal.append(record('new', '*growls.* Fetch failed.'));
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ActivityHistory journal={journal} />, host);
		await waitFor(() => host.querySelectorAll('[data-activity-id]').length === 2);

		expect([...host.querySelectorAll('[data-activity-id]')].map((row) => row.getAttribute('data-activity-id')))
			.toEqual(['new', 'old']);
		const search = host.querySelector<HTMLInputElement>('input[aria-label="Activity search"]')!;
		search.value = 'Found radio';
		search.dispatchEvent(new Event('input', { bubbles: true }));
		expect(search.value).toBe('Found radio');
		expect(new FormData(host.querySelector('form')!).get('text')).toBe('Found radio');
		host.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
		expect(host.querySelector('#activity-history')?.getAttribute('aria-busy')).toBe('true');
		await waitFor(() => host.querySelector('#activity-history')?.getAttribute('aria-busy') === 'false');

		expect([...host.querySelectorAll('[data-activity-id]')].map((row) => row.getAttribute('data-activity-id')))
			.toEqual(['old']);
		dispose();
	});

	it('exports activity JSON and CSV through a history-only download boundary', async () => {
		const journal = createActivityJournal(createMemoryJournalBackend());
		await journal.append(record('new', '*growls.* Fetch failed.'));
		const downloads: ActivityHistoryDownload[] = [];
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ActivityHistory journal={journal} download={(item) => downloads.push(item)} />, host);
		await waitFor(() => host.querySelectorAll('[data-activity-id]').length === 1);

		host.querySelector<HTMLButtonElement>('button[aria-label="Export activity history as JSON"]')!.click();
		await waitFor(() => downloads.length === 1);
		host.querySelector<HTMLButtonElement>('button[aria-label="Export activity history as CSV"]')!.click();
		await waitFor(() => downloads.length === 2);

		expect(downloads.map((item) => item.filename)).toEqual(['parsec-activity-history.json', 'parsec-activity-history.csv']);
		expect(JSON.parse(downloads[0]!.content)[0].id).toBe('new');
		expect(downloads[1]!.content).toContain('schemaVersion,id,at,eventType');
		dispose();
	});

	it('pages visible rows and exports all applied matches beyond 1000 records', async () => {
		const journal = createActivityJournal(createMemoryJournalBackend());
		for (let id = 0; id < 1_007; id += 1) await journal.append(record(String(id), `Matching ${id}`));
		await journal.append(record('excluded', 'Other activity', 'content-graph'));
		const downloads: ActivityHistoryDownload[] = [];
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ActivityHistory journal={journal} download={(item) => downloads.push(item)} />, host);
		await waitFor(() => host.querySelector('#activity-history')?.getAttribute('aria-busy') === 'false');
		const tool = host.querySelector<HTMLInputElement>('input[aria-label="Activity tool"]')!;
		tool.value = 'lore-editor';
		host.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
		await waitFor(() => host.querySelector('#activity-history')?.getAttribute('aria-busy') === 'false');
		expect(host.querySelectorAll('[data-activity-id]')).toHaveLength(100);
		const firstIds = [...host.querySelectorAll('[data-activity-id]')].map((row) => row.getAttribute('data-activity-id'));
		host.querySelector<HTMLButtonElement>('button[aria-label="Older activity"]')!.click();
		await waitFor(() => host.querySelector('#activity-history')?.getAttribute('aria-busy') === 'false');
		expect(host.querySelectorAll('[data-activity-id]')).toHaveLength(100);
		expect([...host.querySelectorAll('[data-activity-id]')].every((row) => !firstIds.includes(row.getAttribute('data-activity-id')))).toBe(true);
		host.querySelector<HTMLButtonElement>('button[aria-label="Newer activity"]')!.click();
		await waitFor(() => host.querySelector('#activity-history')?.getAttribute('aria-busy') === 'false');
		expect([...host.querySelectorAll('[data-activity-id]')].map((row) => row.getAttribute('data-activity-id'))).toEqual(firstIds);
		// Unapplied draft edits must not silently change the exported filter.
		tool.value = 'content-graph';
		tool.dispatchEvent(new Event('input', { bubbles: true }));
		host.querySelector<HTMLButtonElement>('button[aria-label="Export activity history as JSON"]')!.click();
		await waitFor(() => downloads.length === 1);
		const exported = JSON.parse(downloads[0]!.content) as ActivityRecord[];
		expect(exported).toHaveLength(1_007);
		expect(new Set(exported.map((row) => row.id)).size).toBe(1_007);
		expect(exported.every((row) => row.tool === 'lore-editor')).toBe(true);
		host.querySelector<HTMLButtonElement>('button[aria-label="Export activity history as CSV"]')!.click();
		await waitFor(() => downloads.length === 2);
		const csvRows = downloads[1]!.content.trimEnd().split('\r\n');
		expect(csvRows).toHaveLength(1_008);
		expect(csvRows.filter((row) => row.startsWith('schemaVersion,id,'))).toHaveLength(1);
		host.querySelector<HTMLButtonElement>('button[aria-label="Clear activity history"]')!.click();
		host.querySelector<HTMLButtonElement>('button[aria-label="Confirm clear activity history"]')!.click();
		await waitFor(() => host.textContent?.includes('Cleared 1008 activity records.') ?? false);
		dispose();
	});

	it('reports export failure without downloading a partial history', async () => {
		const journal = createActivityJournal(createMemoryJournalBackend());
		await journal.append(record('new', 'Loaded history'));
		const download = vi.fn();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ActivityHistory journal={journal} download={download} />, host);
		await waitFor(() => host.querySelectorAll('[data-activity-id]').length === 1);
		vi.spyOn(journal, 'queryPage').mockRejectedValueOnce(new Error('Read failed'));
		host.querySelector<HTMLButtonElement>('button[aria-label="Export activity history as JSON"]')!.click();
		await waitFor(() => Boolean(host.querySelector('[role="alert"]')));
		expect(host.querySelector('[role="alert"]')?.textContent).toContain('Read failed');
		expect(download).not.toHaveBeenCalled();
		dispose();
	});

	it('requires an in-page confirmation before clearing only activity history', async () => {
		const journal = createActivityJournal(createMemoryJournalBackend());
		await journal.append(record('new', '*growls.* Fetch failed.'));
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ActivityHistory journal={journal} />, host);
		await waitFor(() => host.querySelectorAll('[data-activity-id]').length === 1);

		host.querySelector<HTMLButtonElement>('button[aria-label="Clear activity history"]')!.click();
		expect(await journal.query({ limit: 10 })).toHaveLength(1);
		host.querySelector<HTMLButtonElement>('button[aria-label="Confirm clear activity history"]')!.click();
		await waitFor(() => host.textContent?.includes('Cleared 1 activity record') ?? false);

		expect(await journal.query({ limit: 10 })).toEqual([]);
		expect(host.textContent).toContain('Cleared 1 activity record');
		dispose();
	});

	it('shows storage status and defaults retention to 90 days', async () => {
		const journal = createActivityJournal(createMemoryJournalBackend());
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ActivityHistory journal={journal} persistence="memory" />, host);
		await waitFor(() => host.textContent?.includes('No matching activity yet.') ?? false);

		expect(host.querySelector<HTMLSelectElement>('select[aria-label="Activity retention"]')?.value).toBe('90');
		expect(host.textContent).toContain('Session memory fallback');
		dispose();
	});

	it('shows a visible error when activity history pruning is rejected during initialization', async () => {
		const journal: ActivityJournal = {
			append: vi.fn(async () => undefined),
			query: vi.fn(async () => []),
			queryPage: vi.fn(async () => ({ records: [], nextCursor: null })),
			prune: vi.fn(async () => { throw new Error('IndexedDB transaction failed.'); }),
			clear: vi.fn(async () => 0),
			close: vi.fn(),
		};
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ActivityHistory journal={journal} />, host);

		await waitFor(() => Boolean(host.querySelector('[role="alert"]')));
		expect(host.querySelector('[role="alert"]')?.textContent).toMatch(/activity history/i);
		dispose();
	});

	it('shows a visible error when an activity history query is rejected', async () => {
		let queries = 0;
		const journal: ActivityJournal = {
			append: vi.fn(async () => undefined),
			query: vi.fn(async () => []),
			queryPage: vi.fn(async () => {
				queries += 1;
				if (queries > 1) throw new Error('IndexedDB query failed.');
				return { records: [record('new', '*wuffs.* Loaded history.')], nextCursor: null };
			}),
			prune: vi.fn(async () => 0),
			clear: vi.fn(async () => 0),
			close: vi.fn(),
		};
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ActivityHistory journal={journal} />, host);
		await waitFor(() => host.querySelectorAll('[data-activity-id]').length === 1);

		host.querySelector<HTMLInputElement>('input[aria-label="Activity search"]')!.value = 'history';
		host.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
		await waitFor(() => Boolean(host.querySelector('[role="alert"]')));
		expect(host.querySelector('[role="alert"]')?.textContent).toMatch(/activity history/i);
		dispose();
	});

	it('requires confirmation before resetting an incompatible activity database', async () => {
		const journal = createActivityJournal(createMemoryJournalBackend());
		let resets = 0;
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<ActivityHistory
				journal={journal}
				persistence="memory"
				diagnostic="unsupported-schema"
				resetRequired
				resetJournal={async () => { resets += 1; return 'reset'; }}
			/>
		), host);
		await waitFor(() => host.textContent?.includes('newer activity database') ?? false);

		host.querySelector<HTMLButtonElement>('button[aria-label="Reset incompatible activity database"]')!.click();
		expect(resets).toBe(0);
		host.querySelector<HTMLButtonElement>('button[aria-label="Confirm reset incompatible activity database"]')!.click();
		await waitFor(() => resets === 1);

		expect(host.textContent).toContain('Activity database reset. Reload to resume durable history.');
		dispose();
	});
});

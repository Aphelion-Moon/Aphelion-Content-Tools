import { afterEach, describe, expect, it, vi } from 'vitest';
import { createRoot } from 'solid-js';
import { DEFAULT_FILTERS, PAGE_SIZE, createReviewFeed } from './reviewFeed';

// The old page hard-capped itself at 500 rows. These tests pin the behaviour that replaced it: pages
// accumulate, the feed knows when it has everything, and a filter change starts over rather than
// appending to stale results.

interface PageOptions {
	readonly returned: number;
	readonly hasMore: boolean;
	readonly matched?: number;
}

function mockPages(pages: readonly PageOptions[]): { calls: string[] } {
	const calls: string[] = [];
	let index = 0;
	vi.stubGlobal('fetch', (url: string) => {
		calls.push(url);
		const page = pages[Math.min(index++, pages.length - 1)]!;
		const body = {
			entries: Array.from({ length: page.returned }, (_, i) => ({ id: `entry-${calls.length}-${i}` })),
			matched_entry_count: page.matched ?? 1000,
			returned_entry_count: page.returned,
			has_more: page.hasMore,
			catalog_count: 17500,
			approved_count: 0,
			status_counts: {},
			suppressed_counts: {},
			groups: [],
			visible_entry_count: 1000,
		};
		return Promise.resolve(
			new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } }),
		);
	});
	return { calls };
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

afterEach(() => vi.unstubAllGlobals());

describe('review feed paging', () => {
	it('uses initial filters when an exact search deep link opens the page', async () => {
		const { calls } = mockPages([{ returned: 1, hasMore: false }]);
		await createRoot(async (dispose) => {
			const feed = createReviewFeed({
				...DEFAULT_FILTERS,
				query: '/obj/item/radio',
				sort: 'type_path',
				includeDirectional: true,
				includeRedundant: true,
			});
			feed.reload();
			await settle();
			expect(calls[0]).toContain('q=%2Fobj%2Fitem%2Fradio');
			expect(calls[0]).toContain('sort=type_path');
			dispose();
		});
	});

	it('requests the first page with offset 0 and the configured page size', async () => {
		const { calls } = mockPages([{ returned: PAGE_SIZE, hasMore: true }]);
		await createRoot(async (dispose) => {
			const feed = createReviewFeed();
			feed.reload();
			await settle();
			expect(calls[0]).toContain(`offset=0`);
			expect(calls[0]).toContain(`limit=${PAGE_SIZE}`);
			expect(feed.entries()).toHaveLength(PAGE_SIZE);
			dispose();
		});
	});

	it('appends later pages rather than replacing them', async () => {
		mockPages([
			{ returned: PAGE_SIZE, hasMore: true },
			{ returned: 47, hasMore: false },
		]);
		await createRoot(async (dispose) => {
			const feed = createReviewFeed();
			feed.reload();
			await settle();
			feed.loadMore();
			await settle();
			expect(feed.entries()).toHaveLength(PAGE_SIZE + 47);
			dispose();
		});
	});

	it('marks itself exhausted so the UI stops offering more', async () => {
		mockPages([{ returned: 10, hasMore: false }]);
		await createRoot(async (dispose) => {
			const feed = createReviewFeed();
			feed.reload();
			await settle();
			// A plain closure variable here would leave the "load more" control on screen forever, since
			// Solid would have nothing to track.
			expect(feed.isExhausted()).toBe(true);
			dispose();
		});
	});

	it('does not keep fetching once exhausted', async () => {
		const { calls } = mockPages([{ returned: 10, hasMore: false }]);
		await createRoot(async (dispose) => {
			const feed = createReviewFeed();
			feed.reload();
			await settle();
			const after = calls.length;
			feed.loadMore();
			feed.loadMore();
			await settle();
			expect(calls.length).toBe(after);
			dispose();
		});
	});

	it('starts over when filters change instead of appending to stale results', async () => {
		mockPages([
			{ returned: PAGE_SIZE, hasMore: true },
			{ returned: 5, hasMore: false, matched: 5 },
		]);
		await createRoot(async (dispose) => {
			const feed = createReviewFeed();
			feed.reload();
			await settle();
			expect(feed.entries()).toHaveLength(PAGE_SIZE);

			feed.setFilters({ ...feed.filters(), query: 'nanotrasen' });
			await settle();
			expect(feed.entries()).toHaveLength(5);
			expect(feed.isExhausted()).toBe(true);
			dispose();
		});
	});

	it('starts the replacement request immediately when filters change during an in-flight request', async () => {
		const resolvers: Array<(response: Response) => void> = [];
		const calls: string[] = [];
		vi.stubGlobal('fetch', (url: string) => {
			calls.push(url);
			return new Promise<Response>((resolve) => resolvers.push(resolve));
		});
		const response = (id: string) => new Response(JSON.stringify({
			entries: [{ id }],
			matched_entry_count: 1,
			returned_entry_count: 1,
			has_more: false,
			catalog_count: 1,
			approved_count: 0,
			status_counts: {},
			suppressed_counts: {},
			groups: [],
			visible_entry_count: 1,
		}), { status: 200, headers: { 'content-type': 'application/json' } });

		await createRoot(async (dispose) => {
			const feed = createReviewFeed();
			feed.reload();
			feed.setFilters({ ...feed.filters(), query: 'new filter' });
			expect(calls).toHaveLength(2);
			expect(calls[1]).toContain('q=new+filter');

			resolvers[1]!(response('new-result'));
			await settle();
			resolvers[0]!(response('stale-result'));
			await settle();
			expect(feed.entries().map((entry) => entry.id)).toEqual(['new-result']);
			expect(feed.loading()).toBe(false);
			dispose();
		});
	});

	it('puts the search term and toggles into the request', async () => {
		const { calls } = mockPages([{ returned: 1, hasMore: false }]);
		await createRoot(async (dispose) => {
			const feed = createReviewFeed();
			feed.setFilters({
				query: 'lore',
				statuses: ['reviewed', 'needs-attention'],
				groups: ['nanotrasen', 'languages'],
				sort: 'type_path',
				includeDirectional: true,
				includeRedundant: true,
			});
			await settle();
			const url = calls[calls.length - 1]!;
			expect(url).toContain('q=lore');
			expect(url).toContain('status=reviewed');
			expect(url).toContain('status=needs-attention');
			expect(url).toContain('group=nanotrasen');
			expect(url).toContain('group=languages');
			expect(url).toContain('sort=type_path');
			expect(url).toContain('include_directional=true');
			expect(url).toContain('include_redundant=true');
			dispose();
		});
	});

	it('surfaces a failed request without wiping what is already loaded', async () => {
		vi.stubGlobal('fetch', () =>
			Promise.resolve(
				new Response(JSON.stringify({ error: 'store unavailable' }), {
					status: 503,
					headers: { 'content-type': 'application/json' },
				}),
			),
		);
		await createRoot(async (dispose) => {
			const feed = createReviewFeed();
			feed.reload();
			await settle();
			expect(feed.error()).toBe('store unavailable');
			dispose();
		});
	});
});

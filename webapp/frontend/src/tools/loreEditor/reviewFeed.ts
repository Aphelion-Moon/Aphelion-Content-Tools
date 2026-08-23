import { createSignal, onCleanup } from 'solid-js';
import { api } from '~/lib/api';
import type { components } from '~/lib/api-schema';

// Paged access to the catalog review feed.
//
// The old page capped itself at 500 rows and treated that as a rule. It was really a rendering limit:
// the server has always supported offset/limit, and the corpus is far larger than 500. Measured against
// the real store: 12,264 entries match the default filters (17,500 catalog targets, less 409 directional
// and 5,210 redundant that stay hidden by default), and a full fetch would be roughly 10.7 MB and take
// over ten seconds.
//
// So neither extreme works: not a hard cap, and not one enormous request. This fetches a page at a time
// and appends, while the list virtualises rendering -- together they let a writer reach every one of the
// 12,264 entries without ever holding more than a few screens of DOM or waiting on a huge payload.

export const PAGE_SIZE = 200;

export type ReviewEntry = components['schemas']['ReviewEntryModel'];
export type ReviewGroup = components['schemas']['ReviewGroupModel'];
type ReviewResponse = components['schemas']['ReviewFeedResponse'];

export interface ReviewFilters {
	readonly query: string;
	readonly statuses: readonly string[];
	readonly groups: readonly string[];
	readonly sort: string;
	readonly includeDirectional: boolean;
	readonly includeRedundant: boolean;
}

export const DEFAULT_FILTERS: ReviewFilters = {
	query: '',
	statuses: [],
	groups: [],
	sort: 'name',
	includeDirectional: false,
	includeRedundant: false,
};

function buildQuery(filters: ReviewFilters, offset: number): string {
	const params = new URLSearchParams({
		offset: String(offset),
		limit: String(PAGE_SIZE),
		sort: filters.sort,
	});
	if (filters.query) params.set('q', filters.query);
	for (const status of filters.statuses) params.append('status', status);
	for (const group of filters.groups) params.append('group', group);
	if (filters.includeDirectional) params.set('include_directional', 'true');
	if (filters.includeRedundant) params.set('include_redundant', 'true');
	return `/api/review?${params.toString()}`;
}

export function createReviewFeed(initialFilters: ReviewFilters = DEFAULT_FILTERS) {
	const [entries, setEntries] = createSignal<readonly ReviewEntry[]>([]);
	const [meta, setMeta] = createSignal<ReviewResponse | null>(null);
	const [loading, setLoading] = createSignal(false);
	const [error, setError] = createSignal<string | null>(null);
	const [filters, setFiltersInternal] = createSignal<ReviewFilters>({ ...initialFilters });

	// `exhausted` must be a signal, not a closure variable: the footer reads it to decide whether to
	// offer "load more", and a plain variable gives Solid nothing to track, so the button would linger
	// after everything had already loaded.
	const [exhausted, setExhausted] = createSignal(false);

	// Guards against a slower earlier request landing after a newer one and corrupting the list.
	let generation = 0;
	let activeController: AbortController | undefined;
	onCleanup(() => activeController?.abort());

	async function fetchPage(offset: number, requestGeneration: number): Promise<void> {
		if ((offset > 0 && loading()) || exhausted()) return;
		const controller = new AbortController();
		activeController = controller;
		const requestFilters = filters();
		setLoading(true);
		try {
			const payload = await api.get<ReviewResponse>(buildQuery(requestFilters, offset), {
				signal: controller.signal,
			});
			if (requestGeneration !== generation) return;
			setMeta(payload);
			setEntries((current) => (offset === 0 ? payload.entries : [...current, ...payload.entries]));
			setExhausted(!payload.has_more);
			setError(null);
		} catch (caught) {
			if (controller.signal.aborted) return;
			if (requestGeneration === generation) {
				setError(caught instanceof Error ? caught.message : String(caught));
			}
		} finally {
			if (requestGeneration === generation && activeController === controller) {
				activeController = undefined;
				setLoading(false);
			}
		}
	}

	function reload(): void {
		generation += 1;
		activeController?.abort();
		activeController = undefined;
		setExhausted(false);
		setEntries([]);
		void fetchPage(0, generation);
	}

	function loadMore(): void {
		if (exhausted() || loading()) return;
		void fetchPage(entries().length, generation);
	}

	function setFilters(next: ReviewFilters): void {
		setFiltersInternal(next);
		reload();
	}

	return {
		entries,
		meta,
		loading,
		error,
		filters,
		setFilters,
		reload,
		loadMore,
		/** Total matching the current filters, which is usually far more than are loaded. */
		matchedCount: () => meta()?.matched_entry_count ?? 0,
		isExhausted: exhausted,
	};
}

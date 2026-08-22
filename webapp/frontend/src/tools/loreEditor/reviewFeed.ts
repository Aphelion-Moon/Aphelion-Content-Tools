import { createSignal } from 'solid-js';
import { api } from '~/lib/api';

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

export interface ReviewEntry {
	readonly id: string;
	readonly type_path: string | null;
	readonly name: string | null;
	readonly label: string | null;
	readonly base_name: string | null;
	readonly description: string | null;
	readonly base_description: string | null;
	readonly category: string;
	readonly status: string;
	readonly approved: boolean;
	readonly has_override: boolean;
	readonly group_labels: readonly string[];
	readonly issues: readonly unknown[];
	readonly directional: boolean;
	readonly redundant: boolean;
}

export interface ReviewGroup {
	readonly id: string;
	readonly label: string;
	readonly color?: string | null;
}

interface ReviewResponse {
	readonly entries: readonly ReviewEntry[];
	readonly matched_entry_count: number;
	readonly returned_entry_count: number;
	readonly has_more: boolean;
	readonly catalog_count: number;
	readonly approved_count: number;
	readonly status_counts: Readonly<Record<string, number>>;
	readonly suppressed_counts: Readonly<Record<string, number>>;
	readonly groups: readonly ReviewGroup[];
	readonly visible_entry_count: number;
}

export interface ReviewFilters {
	readonly query: string;
	readonly status: string;
	readonly group: string;
	readonly sort: string;
	readonly includeDirectional: boolean;
	readonly includeRedundant: boolean;
}

export const DEFAULT_FILTERS: ReviewFilters = {
	query: '',
	status: '',
	group: '',
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
	if (filters.status) params.append('status', filters.status);
	if (filters.group) params.append('group', filters.group);
	if (filters.includeDirectional) params.set('include_directional', 'true');
	if (filters.includeRedundant) params.set('include_redundant', 'true');
	return `/api/review?${params.toString()}`;
}

export function createReviewFeed() {
	const [entries, setEntries] = createSignal<readonly ReviewEntry[]>([]);
	const [meta, setMeta] = createSignal<ReviewResponse | null>(null);
	const [loading, setLoading] = createSignal(false);
	const [error, setError] = createSignal<string | null>(null);
	const [filters, setFiltersInternal] = createSignal<ReviewFilters>(DEFAULT_FILTERS);

	// `exhausted` must be a signal, not a closure variable: the footer reads it to decide whether to
	// offer "load more", and a plain variable gives Solid nothing to track, so the button would linger
	// after everything had already loaded.
	const [exhausted, setExhausted] = createSignal(false);

	// Guards against a slower earlier request landing after a newer one and corrupting the list.
	let generation = 0;

	async function fetchPage(offset: number, requestGeneration: number): Promise<void> {
		if (loading() || exhausted()) return;
		setLoading(true);
		try {
			const payload = await api.get<ReviewResponse>(buildQuery(filters(), offset));
			if (requestGeneration !== generation) return;
			setMeta(payload);
			setEntries((current) => (offset === 0 ? payload.entries : [...current, ...payload.entries]));
			setExhausted(!payload.has_more);
			setError(null);
		} catch (caught) {
			if (requestGeneration === generation) {
				setError(caught instanceof Error ? caught.message : String(caught));
			}
		} finally {
			if (requestGeneration === generation) setLoading(false);
		}
	}

	function reload(): void {
		generation += 1;
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

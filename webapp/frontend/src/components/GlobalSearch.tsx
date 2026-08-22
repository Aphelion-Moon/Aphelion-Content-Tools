import { For, Show, createSignal, createMemo } from 'solid-js';
import { useNavigate } from '@solidjs/router';
import { api } from '~/lib/api';
import { TOOLS } from '~/tools/registry';
import type { SearchResult } from '~/store/appStore';
import styles from './GlobalSearch.module.css';

// Global search, backed by /api/search.
//
// This is the capability the old frontend never connected. The backend has implemented hybrid search --
// BM25 full-text plus vector similarity, merged with reciprocal rank fusion, across all ten store
// tables -- for some time, exposed at /api/search. The previous search box called /api/review instead: a
// plain substring filter over a single table. Pointing it at the real endpoint turns the sidebar box
// into a genuine cross-tool lookup that reaches catalog targets, overrides, groups, reviews,
// assignments, graph nodes and edges, unresolved markers, manifests, and saved references at once.

const DEBOUNCE_MS = 200;
const RESULT_LIMIT = 6;

interface SearchResponse {
	readonly results: readonly SearchResult[];
}

/** Which tool owns a given store table, so a result can route somewhere useful. */
const TABLE_OWNER: Record<string, string> = {
	catalog_targets: '/lore-editor',
	overrides: '/lore-editor',
	groups: '/lore-editor',
	reviews: '/lore-editor',
	assignments: '/lore-editor',
	graph_nodes: '/graph',
	graph_edges: '/graph',
	unresolved_markers: '/graph',
	manifests: '/file-management',
	references: '/file-management',
};

function resultLabel(result: SearchResult): string {
	const record = result.record as Record<string, unknown>;
	for (const key of ['name', 'label', 'type_path', 'path', 'id']) {
		const value = record[key];
		if (typeof value === 'string' && value) return value;
	}
	return result.id;
}

function resultDetail(result: SearchResult): string {
	const record = result.record as Record<string, unknown>;
	for (const key of ['type_path', 'path', 'description']) {
		const value = record[key];
		if (typeof value === 'string' && value && value !== resultLabel(result)) return value;
	}
	return '';
}

export default function GlobalSearch() {
	const navigate = useNavigate();
	const [query, setQuery] = createSignal('');
	const [results, setResults] = createSignal<readonly SearchResult[]>([]);
	const [open, setOpen] = createSignal(false);
	const [searching, setSearching] = createSignal(false);

	let debounceTimer: ReturnType<typeof setTimeout> | undefined;
	// Guards against an earlier, slower request overwriting a later one's results.
	let latestRequest = 0;

	const pageMatches = createMemo(() => {
		const needle = query().trim().toLowerCase();
		if (!needle) return [];
		return TOOLS.filter((tool) => tool.navLabel.toLowerCase().includes(needle));
	});

	async function runSearch(text: string): Promise<void> {
		const trimmed = text.trim();
		if (!trimmed) {
			setResults([]);
			setOpen(false);
			return;
		}
		const requestId = ++latestRequest;
		setSearching(true);
		try {
			const payload = await api.get<SearchResponse>(
				`/api/search?q=${encodeURIComponent(trimmed)}&limit=${RESULT_LIMIT}`,
			);
			if (requestId !== latestRequest) return;
			setResults(payload.results ?? []);
		} catch {
			// Page matches still render even when the store search fails, so the box stays useful.
			if (requestId === latestRequest) setResults([]);
		} finally {
			if (requestId === latestRequest) setSearching(false);
		}
		setOpen(true);
	}

	function onInput(event: InputEvent & { currentTarget: HTMLInputElement }) {
		const value = event.currentTarget.value;
		setQuery(value);
		setOpen(Boolean(value.trim()));
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => void runSearch(value), DEBOUNCE_MS);
	}

	function goTo(route: string) {
		setOpen(false);
		navigate(route);
	}

	const hasAnything = () => pageMatches().length > 0 || results().length > 0;

	return (
		<div class={styles.wrapper}>
			<label class={styles.label} for="global-search">
				Search
			</label>
			<input
				id="global-search"
				type="search"
				placeholder="Search everything…"
				value={query()}
				onInput={onInput}
				onFocus={() => setOpen(Boolean(query().trim()))}
				onKeyDown={(event) => {
					if (event.key === 'Escape') setOpen(false);
				}}
			/>

			<Show when={open()}>
				<div class={styles.results}>
					<Show when={hasAnything()} fallback={<p class={styles.empty}>{searching() ? 'Searching…' : 'No matches.'}</p>}>
						<Show when={pageMatches().length > 0}>
							<p class={styles.sectionHeading}>Pages</p>
							<For each={pageMatches()}>
								{(tool) => (
									<button type="button" class={styles.result} onClick={() => goTo(tool.route)}>
										<strong>{tool.navLabel}</strong>
									</button>
								)}
							</For>
						</Show>

						<Show when={results().length > 0}>
							<p class={styles.sectionHeading}>Catalog &amp; content</p>
							<For each={results()}>
								{(result) => (
									<button
										type="button"
										class={styles.result}
										onClick={() => goTo(TABLE_OWNER[result.table] ?? '/')}
									>
										<span class={styles.tableTag}>{result.table.replace(/_/g, ' ')}</span>
										<strong>{resultLabel(result)}</strong>
										<Show when={resultDetail(result)}>
											{(detail) => <span class={styles.resultMeta}>{detail()}</span>}
										</Show>
									</button>
								)}
							</For>
						</Show>
					</Show>
				</div>
			</Show>
		</div>
	);
}

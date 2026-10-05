import { For, Show, createEffect, createSignal, createMemo, onCleanup } from 'solid-js';
import { useNavigate } from '@solidjs/router';
import { api } from '~/lib/api';
import { createAsyncScope } from '~/lib/asyncScope';
import type { components } from '~/lib/api-schema';
import { TOOLS } from '~/tools/registry';
import { appState, setSelectedContext, type SearchResult } from '~/store/appStore';
import { buildSearchRequest, contextFromResult, navigationRoute } from './globalSearchModel';
import { reportParsec } from '~/lib/parsec/coordinator';
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
const LISTBOX_ID = 'global-search-results';
const SEARCH_SCOPES = {
	everything: [] as readonly string[],
	lore: ['catalog_targets', 'overrides', 'groups', 'reviews', 'assignments'],
	graph: ['graph_nodes', 'graph_edges', 'unresolved_markers'],
	files: ['manifests', 'references'],
	definitions: ['job_definitions', 'outfit_definitions'],
} as const;
type SearchScopeName = keyof typeof SEARCH_SCOPES;

type SearchResponse = components['schemas']['SearchResponse'];
type SemanticSearchHealth = components['schemas']['SemanticSearchHealth'];

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
	const [semanticStatus, setSemanticStatus] = createSignal<SemanticSearchHealth | null>(null);
	const [scope, setScope] = createSignal<SearchScopeName>('everything');
	const [activeIndex, setActiveIndex] = createSignal(-1);
	const [searchError, setSearchError] = createSignal<string | null>(null);
	const [revisionNotice, setRevisionNotice] = createSignal<string | null>(null);

	let debounceTimer: ReturnType<typeof setTimeout> | undefined;
	const requests = createAsyncScope();
	onCleanup(() => { clearTimeout(debounceTimer); requests.dispose(); });
	let observedRevisionKey: string | undefined;
	createEffect(() => {
		const revision = appState.workspaceRevision;
		const nextKey = revision === null ? '' : JSON.stringify(revision);
		if (observedRevisionKey === undefined) {
			observedRevisionKey = nextKey;
			return;
		}
		if (nextKey === observedRevisionKey) return;
		const firstRevision = observedRevisionKey === '';
		observedRevisionKey = nextKey;
		if (firstRevision && !query().trim()) return;
		requests.invalidate();
		clearTimeout(debounceTimer);
		setResults([]);
		setSemanticStatus(null);
		setSearchError(null);
		setSearching(false);
		setOpen(false);
		setActiveIndex(-1);
		setRevisionNotice('Workspace changed. Search results cleared; run the search again.');
	});

	const pageMatches = createMemo(() => {
		const needle = query().trim().toLowerCase();
		if (!needle) return [];
		return TOOLS.filter((tool) => tool.navLabel.toLowerCase().includes(needle));
	});

	async function runSearch(text: string): Promise<void> {
		requests.invalidate();
		const isCurrent = requests.capture();
		const trimmed = text.trim();
		if (!trimmed) {
			setResults([]);
			setOpen(false);
			setActiveIndex(-1);
			setSearchError(null);
			return;
		}
		setSearching(true);
		reportParsec({
			type: 'search',
			phase: 'started',
			tool: 'global-search',
			query: trimmed,
			dedupeKey: 'global-search',
		});
		try {
			const payload = await api.post<SearchResponse>(
				'/api/search',
				buildSearchRequest(trimmed, appState.selectedContext, RESULT_LIMIT, SEARCH_SCOPES[scope()]),
			);
			if (!isCurrent()) return;
			const nextResults = payload.results ?? [];
			setResults(nextResults);
			setSemanticStatus(payload.semantic_search);
			setSearchError(null);
			const resultCount = pageMatches().length + nextResults.length;
			reportParsec({
				type: 'search',
				phase: resultCount === 0 ? 'empty' : 'completed',
				tool: 'global-search',
				query: trimmed,
				resultCount,
				dedupeKey: 'global-search',
			});
		} catch (caught) {
			// Page matches still render even when the store search fails, so the box stays useful.
			if (isCurrent()) {
				setResults([]);
				const message = caught instanceof Error ? caught.message : String(caught);
				setSearchError(message);
				reportParsec({
					type: 'search',
					phase: 'failed',
					tool: 'global-search',
					query: trimmed,
					technicalDetail: message,
					dedupeKey: 'global-search',
				});
			}
		} finally {
			if (isCurrent()) setSearching(false);
		}
	}

	function onInput(event: InputEvent & { currentTarget: HTMLInputElement }) {
		requests.invalidate();
		const value = event.currentTarget.value;
		setResults([]);
		setSemanticStatus(null);
		setSearchError(null);
		setRevisionNotice(null);
		setSearching(Boolean(value.trim()));
		setQuery(value);
		setOpen(Boolean(value.trim()));
		setActiveIndex(-1);
		clearTimeout(debounceTimer);
		if (value.trim()) debounceTimer = setTimeout(() => void runSearch(value), DEBOUNCE_MS);
	}

	function goTo(route: string) {
		setOpen(false);
		setActiveIndex(-1);
		navigate(route);
	}

	function goToResult(result: SearchResult) {
		setSelectedContext(contextFromResult(result));
		goTo(navigationRoute(result));
	}

	const hasAnything = () => pageMatches().length > 0 || results().length > 0;
	const optionCount = () => pageMatches().length + results().length;
	const optionId = (index: number) => `global-search-option-${index}`;
	const statusText = () => {
		if (searching()) return 'Searching.';
		if (searchError()) return `Search failed: ${searchError()}`;
		const count = optionCount();
		return count === 1 ? '1 result available.' : `${count} results available.`;
	};

	function activateOption(index: number): void {
		const page = pageMatches()[index];
		if (page) {
			goTo(page.route);
			return;
		}
		const result = results()[index - pageMatches().length];
		if (result) goToResult(result);
	}

	function onKeyDown(event: KeyboardEvent): void {
		const count = optionCount();
		if (event.key === 'Escape') {
			setOpen(false);
			setActiveIndex(-1);
			return;
		}
		if (event.key === 'ArrowDown') {
			event.preventDefault();
			setOpen(Boolean(query().trim()));
			if (count > 0) setActiveIndex((current) => Math.min(current + 1, count - 1));
			return;
		}
		if (event.key === 'ArrowUp') {
			event.preventDefault();
			setOpen(Boolean(query().trim()));
			if (count > 0) setActiveIndex((current) => current <= 0 ? count - 1 : current - 1);
			return;
		}
		if (event.key === 'Enter' && activeIndex() >= 0) {
			event.preventDefault();
			activateOption(activeIndex());
		}
	}

	return (
		<div
			class={styles.wrapper}
			onFocusOut={(event) => {
				const next = event.relatedTarget;
				if (!(next instanceof Node) || !event.currentTarget.contains(next)) {
					setOpen(false);
					setActiveIndex(-1);
				}
			}}
		>
			<label class={styles.label} for="global-search">
				Search
			</label>
			<input
				id="global-search"
				type="search"
				placeholder="Search everything…"
				value={query()}
				role="combobox"
				aria-autocomplete="list"
				aria-haspopup="listbox"
				aria-expanded={open()}
				aria-controls={open() ? LISTBOX_ID : undefined}
				aria-activedescendant={open() && activeIndex() >= 0 ? optionId(activeIndex()) : undefined}
				onInput={onInput}
				onFocus={() => setOpen(Boolean(query().trim()))}
				onKeyDown={onKeyDown}
			/>
			<label class={styles.scopeLabel}>
				<span>Scope</span>
				<select
					value={scope()}
					onChange={(event) => {
						clearTimeout(debounceTimer);
						setOpen(Boolean(query().trim()));
						setScope(event.currentTarget.value as SearchScopeName);
						if (query().trim()) void runSearch(query());
					}}
				>
					<option value="everything">Everything</option>
					<option value="lore">Lore</option>
					<option value="graph">Content graph</option>
					<option value="files">Files &amp; references</option>
					<option value="definitions">Jobs &amp; outfits</option>
				</select>
			</label>
			<Show when={revisionNotice()}>{(message) => <p class={styles.revisionNotice} role="status">{message()}</p>}</Show>

			<Show when={open()}>
				<div id={LISTBOX_ID} class={styles.results} role="listbox" aria-label="Search suggestions">
					<Show when={appState.selectedContext?.record_id || appState.selectedContext?.type_path}>
						{(selected) => <p class={styles.contextNote}>Related results boosted for {selected()}.</p>}
					</Show>
					<Show when={semanticStatus()?.mode === 'keyword-only'}>
						<p class={styles.statusNote}>Keyword-only search; semantic ranking is currently unavailable.</p>
					</Show>
					<Show when={searchError()}>{(message) => <p class={styles.error} role="alert">{message()}</p>}</Show>
					<Show when={hasAnything()} fallback={<p class={styles.empty}>{searching() ? 'Searching…' : 'No matches.'}</p>}>
						<Show when={pageMatches().length > 0}>
							<p class={styles.sectionHeading}>Pages</p>
							<For each={pageMatches()}>
								{(tool, index) => (
									<button
										id={optionId(index())}
										type="button"
										role="option"
										aria-selected={activeIndex() === index()}
										tabIndex={-1}
										class={activeIndex() === index() ? `${styles.result} ${styles.resultActive}` : styles.result}
										onMouseDown={(event) => event.preventDefault()}
										onMouseEnter={() => setActiveIndex(index())}
										onClick={() => goTo(tool.route)}
									>
										<strong>{tool.navLabel}</strong>
									</button>
								)}
							</For>
						</Show>

						<Show when={results().length > 0}>
							<p class={styles.sectionHeading}>Catalog &amp; content</p>
							<For each={results()}>
								{(result, resultIndex) => {
									const index = () => pageMatches().length + resultIndex();
									return (
									<button
										id={optionId(index())}
										type="button"
										role="option"
										aria-selected={activeIndex() === index()}
										tabIndex={-1}
										class={activeIndex() === index() ? `${styles.result} ${styles.resultActive}` : styles.result}
										onMouseDown={(event) => event.preventDefault()}
										onMouseEnter={() => setActiveIndex(index())}
										onClick={() => goToResult(result)}
									>
										<span class={styles.tableTag}>{result.table.replace(/_/g, ' ')}</span>
										<strong>{resultLabel(result)}</strong>
										<Show when={resultDetail(result)}>
											{(detail) => <span class={styles.resultMeta}>{detail()}</span>}
										</Show>
										<Show when={result.context_reason}>
											{(reason) => <span class={styles.contextReason}>Boosted: {reason()}</span>}
										</Show>
									</button>
									);
								}}
							</For>
						</Show>
					</Show>
				</div>
			</Show>
			<p class={styles.srOnly} role="status" aria-live="polite" aria-atomic="true">
				{statusText()}
			</p>
		</div>
	);
}

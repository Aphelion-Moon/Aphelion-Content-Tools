import { For, Show, createSignal, onCleanup, onMount } from 'solid-js';
import {
	getBrowserActivityJournal,
	resetIndexedDbJournal,
	type ResetIndexedDbJournalResult,
} from '~/lib/parsec/indexedDbJournal';
import { recordsToCsv } from '~/lib/parsec/journal';
import type {
	ActivityCursor,
	ActivityJournal,
	ActivityOutcome,
	ActivityQuery,
	ActivityRecord,
	ActivityRetentionDays,
} from '~/lib/parsec/journalTypes';
import { readActivityRetention, writeActivityRetention } from '~/lib/parsec/settings';
import type { ParsecEvent } from '~/lib/parsec/types';
import { createAsyncScope } from '~/lib/asyncScope';
import styles from './ActivityHistory.module.css';

export interface ActivityHistoryDownload {
	readonly filename: string;
	readonly mediaType: string;
	readonly content: string;
}

export interface ActivityHistoryProps {
	readonly journal?: ActivityJournal;
	readonly persistence?: 'indexeddb' | 'memory';
	readonly diagnostic?: string | null;
	readonly resetRequired?: boolean;
	readonly resetJournal?: () => Promise<ResetIndexedDbJournalResult>;
	readonly download?: (item: ActivityHistoryDownload) => void;
}

function browserDownload(item: ActivityHistoryDownload): void {
	const url = URL.createObjectURL(new Blob([item.content], { type: item.mediaType }));
	const anchor = document.createElement('a');
	anchor.href = url;
	anchor.download = item.filename;
	anchor.click();
	URL.revokeObjectURL(url);
}

function retentionFromValue(value: string): ActivityRetentionDays {
	return value === 'manual' ? 'manual' : Number(value) as ActivityRetentionDays;
}

function activityErrorMessage(error: unknown): string {
	return error instanceof Error && error.message ? error.message : 'The local activity store rejected the request.';
}

export default function ActivityHistory(props: ActivityHistoryProps) {
	const [journal, setJournal] = createSignal<ActivityJournal | null>(props.journal ?? null);
	const [persistence, setPersistence] = createSignal<'indexeddb' | 'memory'>(props.persistence ?? 'indexeddb');
	const [diagnostic, setDiagnostic] = createSignal<string | null>(props.diagnostic ?? null);
	const [resetRequired, setResetRequired] = createSignal(props.resetRequired ?? false);
	const [resetConfirmation, setResetConfirmation] = createSignal(false);
	const [records, setRecords] = createSignal<readonly ActivityRecord[]>([]);
	const [appliedQuery, setAppliedQuery] = createSignal<ActivityQuery>({ limit: 100 });
	const [pageCursors, setPageCursors] = createSignal<readonly (ActivityCursor | undefined)[]>([undefined]);
	const [nextCursor, setNextCursor] = createSignal<ActivityCursor | null>(null);
	const [loading, setLoading] = createSignal(true);
	const [exporting, setExporting] = createSignal(false);
	const [error, setError] = createSignal<string | null>(null);
	const [confirmation, setConfirmation] = createSignal(false);
	const [notice, setNotice] = createSignal<string | null>(null);
	const [retention, setRetention] = createSignal<ActivityRetentionDays>(readActivityRetention());
	const [text, setText] = createSignal('');
	const [tool, setTool] = createSignal('');
	const [eventType, setEventType] = createSignal('');
	const [outcome, setOutcome] = createSignal('');
	const [after, setAfter] = createSignal('');
	const [before, setBefore] = createSignal('');
	const requests = createAsyncScope();
	const exports = createAsyncScope();
	onCleanup(() => { requests.dispose(); exports.dispose(); });

	function activityQuery(form?: HTMLFormElement): ActivityQuery {
		const submitted = form ? new FormData(form) : null;
		const submittedValue = (name: string, fallback: string): string => {
			const value = submitted?.get(name);
			return typeof value === 'string' ? value : fallback;
		};
		const queryText = submittedValue('text', text());
		const queryTool = submittedValue('tool', tool());
		const queryEventType = submittedValue('eventType', eventType());
		const queryOutcome = submittedValue('outcome', outcome());
		const queryAfter = submittedValue('after', after());
		const queryBefore = submittedValue('before', before());
		return {
			limit: 100,
			...(queryText.trim() ? { text: queryText.trim() } : {}),
			...(queryTool.trim() ? { tool: queryTool.trim() } : {}),
			...(queryEventType ? { eventType: queryEventType as ParsecEvent['type'] } : {}),
			...(queryOutcome ? { outcome: queryOutcome as ActivityOutcome } : {}),
			...(queryAfter ? { after: new Date(`${queryAfter}T00:00:00`).getTime() / 1_000 } : {}),
			...(queryBefore ? { before: new Date(`${queryBefore}T23:59:59.999`).getTime() / 1_000 } : {}),
		};
	}

	async function refresh(target = journal(), query = appliedQuery(), cursors: readonly (ActivityCursor | undefined)[] = [undefined]): Promise<void> {
		if (!target) return;
		requests.invalidate();
		const isCurrent = requests.capture();
		setLoading(true);
		setError(null);
		try {
			const page = await target.queryPage({ ...query, cursor: cursors.at(-1) });
			if (isCurrent()) {
				setRecords(page.records);
				setNextCursor(page.nextCursor);
				setPageCursors(cursors);
				setAppliedQuery(query);
			}
		} catch (caught) {
			if (isCurrent()) {
				setRecords([]);
				setError(`Activity history unavailable: ${activityErrorMessage(caught)}`);
			}
		} finally {
			if (isCurrent()) setLoading(false);
		}
	}

	async function initialize(): Promise<void> {
		requests.invalidate();
		const isCurrent = requests.capture();
		setLoading(true);
		setError(null);
		try {
			let target = journal();
			if (!target) {
				const opened = await getBrowserActivityJournal();
				if (!isCurrent()) return;
				target = opened.journal;
				setJournal(target);
				setPersistence(opened.persistence);
				setDiagnostic(opened.diagnostic);
				setResetRequired(opened.resetRequired);
			}
			if (!target) return;
			await target.prune(retention(), Date.now() / 1_000);
			if (!isCurrent()) return;
			await refresh(target, activityQuery());
		} catch (caught) {
			if (isCurrent()) {
				setRecords([]);
				setError(`Activity history unavailable: ${activityErrorMessage(caught)}`);
			}
		} finally {
			if (isCurrent()) setLoading(false);
		}
	}

	onMount(() => { void initialize(); });

	async function updateRetention(value: string): Promise<void> {
		const next = retentionFromValue(value);
		setRetention(next);
		writeActivityRetention(next);
		const target = journal();
		if (!target) return;
		requests.invalidate();
		const isCurrent = requests.capture();
		setError(null);
		try {
			const removed = await target.prune(next, Date.now() / 1_000);
			if (!isCurrent()) return;
			setNotice(removed > 0 ? `Pruned ${removed} expired activity record${removed === 1 ? '' : 's'}.` : 'Retention updated.');
			await refresh(target);
		} catch (caught) {
			if (isCurrent()) setError(`Activity history unavailable: ${activityErrorMessage(caught)}`);
		}
	}

	async function exportRecords(format: 'json' | 'csv'): Promise<void> {
		const target = journal();
		if (!target || exporting()) return;
		const isCurrent = exports.capture();
		// Bound new activity at the start; each read holds only one page of records.
		const query = { ...appliedQuery(), limit: 1_000, before: Math.min(appliedQuery().before ?? Infinity, Date.now() / 1_000) };
		const chunks: string[] = [];
		let cursor: ActivityCursor | undefined;
		let count = 0;
		setExporting(true);
		setError(null);
		try {
			do {
				const page = await target.queryPage({ ...query, cursor });
				if (!isCurrent()) return;
				if (format === 'json') {
					if (page.records.length > 0) chunks.push(page.records.map((record) => JSON.stringify(record, null, 2)).join(',\n'));
				} else chunks.push(recordsToCsv(page.records, cursor === undefined));
				count += page.records.length;
				cursor = page.nextCursor ?? undefined;
			} while (cursor);
			(props.download ?? browserDownload)({
				filename: `parsec-activity-history.${format}`,
				mediaType: format === 'json' ? 'application/json' : 'text/csv',
				content: format === 'json' ? `[\n${chunks.join(',\n')}\n]` : chunks.join(''),
			});
			setNotice(`Exported ${count} matching activity record${count === 1 ? '' : 's'}.`);
		} catch (caught) {
			if (isCurrent()) setError(`Activity export unavailable: ${activityErrorMessage(caught)}`);
		} finally {
			if (isCurrent()) setExporting(false);
		}
	}

	async function clearHistory(): Promise<void> {
		const target = journal();
		if (!target) return;
		requests.invalidate();
		const isCurrent = requests.capture();
		setLoading(true);
		setError(null);
		try {
			const count = await target.clear();
			if (!isCurrent()) return;
			setRecords([]);
			setNextCursor(null);
			setPageCursors([undefined]);
			setConfirmation(false);
			setNotice(`Cleared ${count} activity record${count === 1 ? '' : 's'}.`);
		} catch (caught) {
			if (isCurrent()) setError(`Activity history unavailable: ${activityErrorMessage(caught)}`);
		} finally {
			if (isCurrent()) setLoading(false);
		}
	}

	async function resetIncompatibleDatabase(): Promise<void> {
		try {
			const result = await (props.resetJournal ?? resetIndexedDbJournal)();
			setResetConfirmation(false);
			if (result === 'reset') {
				setResetRequired(false);
				setDiagnostic(null);
				setNotice('Activity database reset. Reload to resume durable history.');
				return;
			}
			setNotice(result === 'blocked'
				? 'Close other app tabs, then try the activity database reset again.'
				: 'The activity database could not be reset in this browser.');
		} catch (caught) {
			setError(`Activity history unavailable: ${activityErrorMessage(caught)}`);
		}
	}

	return (
		<section
			id="activity-history"
			class={styles.history}
			aria-labelledby="activity-history-heading"
			aria-busy={loading() || exporting() ? 'true' : 'false'}
		>
			<div class={styles.headingRow}>
				<div>
					<p class={styles.eyebrow}>Local data</p>
					<h2 id="activity-history-heading">Activity history</h2>
				</div>
				<p class={styles.storage}>
					{persistence() === 'indexeddb' ? 'Durable browser storage' : 'Session memory fallback'}
				</p>
			</div>
			<Show when={diagnostic()}>{(message) => <p class={styles.warning}>Storage status: {message()}</p>}</Show>
			<Show when={resetRequired()}>
				<div class={styles.confirmation}>
					<span>A newer activity database is preserved but cannot be read by this version.</span>
					<button type="button" aria-label="Reset incompatible activity database" onClick={() => setResetConfirmation(true)}>Reset database</button>
					<Show when={resetConfirmation()}>
						<button type="button" aria-label="Confirm reset incompatible activity database" onClick={() => void resetIncompatibleDatabase()}>Confirm reset</button>
						<button type="button" onClick={() => setResetConfirmation(false)}>Cancel</button>
					</Show>
				</div>
			</Show>
			<p class={styles.help}>Parsec's transcript is linked to structured app activity. Lore bodies are never stored here.</p>

			<form class={styles.filters} onSubmit={(event) => { event.preventDefault(); void refresh(undefined, activityQuery(event.currentTarget)); }}>
				<label>Search <input name="text" aria-label="Activity search" value={text()} onInput={(event) => setText(event.currentTarget.value)} /></label>
				<label>Tool <input name="tool" aria-label="Activity tool" value={tool()} onInput={(event) => setTool(event.currentTarget.value)} /></label>
				<label>Event
					<select name="eventType" aria-label="Activity event" value={eventType()} onChange={(event) => setEventType(event.currentTarget.value)}>
						<option value="">All</option>
						<For each={['search', 'fetch', 'mutation', 'job', 'connection', 'validation', 'interaction', 'idle', 'notice']}>{(value) => <option value={value}>{value}</option>}</For>
					</select>
				</label>
				<label>Outcome
					<select name="outcome" aria-label="Activity outcome" value={outcome()} onChange={(event) => setOutcome(event.currentTarget.value)}>
						<option value="">All</option>
						<For each={['started', 'completed', 'cancelled', 'warning', 'failed', 'notice']}>{(value) => <option value={value}>{value}</option>}</For>
					</select>
				</label>
				<label>After <input name="after" aria-label="Activity after" type="date" value={after()} onInput={(event) => setAfter(event.currentTarget.value)} /></label>
				<label>Before <input name="before" aria-label="Activity before" type="date" value={before()} onInput={(event) => setBefore(event.currentTarget.value)} /></label>
				<button
					type="submit"
					disabled={exporting()}
					onClick={(event) => {
						event.preventDefault();
						const form = event.currentTarget.form;
						if (form) void refresh(undefined, activityQuery(form));
					}}
				>
					Apply filters
				</button>
			</form>

			<div class={styles.controls}>
				<label>Retention
					<select aria-label="Activity retention" disabled={loading() || exporting()} value={String(retention())} onChange={(event) => void updateRetention(event.currentTarget.value)}>
						<option value="7">7 days</option><option value="30">30 days</option><option value="90">90 days</option><option value="365">1 year</option><option value="manual">Until manually cleared</option>
					</select>
				</label>
				<button type="button" disabled={loading() || exporting()} aria-label="Export activity history as JSON" onClick={() => void exportRecords('json')}>Export JSON</button>
				<button type="button" disabled={loading() || exporting()} aria-label="Export activity history as CSV" onClick={() => void exportRecords('csv')}>Export CSV</button>
				<button type="button" disabled={loading() || exporting()} aria-label="Clear activity history" onClick={() => setConfirmation(true)}>Clear history</button>
			</div>
			<p class={styles.help}>{exporting() ? 'Exporting matching activity…' : 'Exports include all records matching the applied filters, across every page.'}</p>
			<Show when={confirmation()}>
				<div class={styles.confirmation} role="group" aria-label="Confirm activity history clear">
					<span>This removes local activity history only. Parsec's profile stays intact.</span>
					<button type="button" disabled={loading() || exporting()} aria-label="Confirm clear activity history" onClick={() => void clearHistory()}>Confirm clear</button>
					<button type="button" onClick={() => setConfirmation(false)}>Cancel</button>
				</div>
			</Show>
			<Show when={notice()}>{(message) => <p role="status">{message()}</p>}</Show>
			<Show when={error()}>{ (message) => <p role="alert">{message()}</p> }</Show>
			<Show when={!error()}>
				<div class={styles.controls} aria-label="Activity pages">
					<button type="button" aria-label="Newer activity" disabled={loading() || exporting() || pageCursors().length <= 1} onClick={() => void refresh(journal(), appliedQuery(), pageCursors().slice(0, -1))}>Newer</button>
					<span>Page {pageCursors().length}</span>
					<button type="button" aria-label="Older activity" disabled={loading() || exporting() || !nextCursor()} onClick={() => { const cursor = nextCursor(); if (cursor) void refresh(journal(), appliedQuery(), [...pageCursors(), cursor]); }}>Older</button>
				</div>
				<Show when={!loading()} fallback={<p>Loading local activity history…</p>}>
					<Show when={records().length > 0} fallback={<p class={styles.help}>No matching activity yet.</p>}>
						<ol class={styles.records}>
							<For each={records()}>{(entry) => (
								<li id={`activity-${encodeURIComponent(entry.id)}`} data-activity-id={entry.id}>
									<div><time dateTime={new Date(entry.at * 1_000).toISOString()}>{new Date(entry.at * 1_000).toLocaleString()}</time> <strong>[{entry.outcome}]</strong> {entry.eventType}:{entry.phase}</div>
									<Show when={entry.parsecText}>{(copy) => <div><strong>Parsec:</strong> {copy()}</div>}</Show>
									<Show when={entry.tool}><div>Tool: {entry.tool}</div></Show>
									<Show when={entry.technicalDetail}>{(detail) => <div><code>{detail()}</code></div>}</Show>
								</li>
							)}</For>
						</ol>
					</Show>
				</Show>
			</Show>
		</section>
	);
}

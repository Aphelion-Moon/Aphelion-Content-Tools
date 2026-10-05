import { For, Show, createResource, createSignal } from 'solid-js';
import OpenFileActions from '~/components/OpenFileActions';
import { api } from '~/lib/api';
import type { components } from '~/lib/api-schema';
import { reportParsec } from '~/lib/parsec/coordinator';
import styles from './ContentGraph.module.css';

type GraphEdit = components['schemas']['GraphEditModel'];
type GraphEditsResponse = components['schemas']['GraphEditsResponse'];
type GraphModulesResponse = components['schemas']['GraphModulesResponse'];
type GraphUnresolvedResponse = components['schemas']['GraphUnresolvedResponse'];
type Marker = components['schemas']['UnresolvedMarkerModel'];
type MarkerHistoryResponse = components['schemas']['MarkerHistoryResponse'];

const MARKER_PAGE_SIZE = 50;

export default function ModularDebugPanel(props: {
	readonly scanned: boolean;
	readonly refreshToken: number;
	readonly onRescan: () => Promise<void>;
}) {
	const [coreFile, setCoreFile] = createSignal('');
	const [lookupBusy, setLookupBusy] = createSignal(false);
	const [lookupMessage, setLookupMessage] = createSignal('');
	const [edits, setEdits] = createSignal<readonly GraphEdit[]>([]);
	const [markerLimit, setMarkerLimit] = createSignal(MARKER_PAGE_SIZE);

	const [missingReadmes, { refetch: refetchMissingReadmes }] = createResource(
		() => props.scanned ? props.refreshToken : null,
		() => api.get<GraphModulesResponse>('/api/graph/modules?missing_readme=true'),
	);
	const [unresolved, { refetch: refetchUnresolved }] = createResource(
		() => props.scanned ? props.refreshToken : null,
		() => api.get<GraphUnresolvedResponse>('/api/graph/unresolved'),
	);

	async function lookupCoreFile(): Promise<void> {
		const path = coreFile().trim();
		if (!path) {
			setLookupMessage('Enter a core file path first.');
			setEdits([]);
			return;
		}
		setLookupBusy(true);
		try {
			const response = await api.get<GraphEditsResponse>(`/api/graph/edits?core_file=${encodeURIComponent(path)}`);
			setEdits(response.edits ?? []);
			setLookupMessage(response.scanned ? '' : 'No content graph has been scanned yet.');
		} catch (error) {
			const message = error instanceof Error ? error.message : String(error);
			setLookupMessage(message);
			reportParsec({ type: 'fetch', phase: 'failed', tool: 'content-graph', summary: 'Could not inspect modular edits.', technicalDetail: message });
		} finally {
			setLookupBusy(false);
		}
	}

	async function refreshDebug(): Promise<void> {
		setMarkerLimit(MARKER_PAGE_SIZE);
		await Promise.all([refetchMissingReadmes(), refetchUnresolved()]);
	}

	return (
		<details class={styles.debugPanel}>
			<summary>Modular Debug</summary>
			<p class={styles.metadata}>
				Inspect edit-marker attribution, missing module documentation, and unresolved labels.
				Preview marker changes before applying them to a clean game checkout.
			</p>
			<div class={styles.buttonRow}>
				<button type="button" disabled={!props.scanned} onClick={() => void refreshDebug()}>Refresh diagnostics</button>
				<button type="button" onClick={() => void props.onRescan()}>Rescan content</button>
			</div>

			<div class={styles.debugGrid}>
				<section class={styles.debugSection} aria-labelledby="core-edits-heading">
					<h3 id="core-edits-heading">Core-file edits</h3>
					<div class={styles.inlineControls}>
						<input
							type="search"
							placeholder="code/modules/example.dm"
							value={coreFile()}
							onInput={(event) => setCoreFile(event.currentTarget.value)}
							onKeyDown={(event) => {
								if (event.key === 'Enter') void lookupCoreFile();
							}}
						/>
						<button type="button" disabled={lookupBusy()} onClick={() => void lookupCoreFile()}>Look up</button>
					</div>
					<Show when={lookupMessage()}>{(message) => <p role="status" class={styles.metadata}>{message()}</p>}</Show>
					<Show when={!lookupBusy() && coreFile().trim() && !lookupMessage() && edits().length === 0}>
						<p class={styles.metadata}>No edits found for that core file.</p>
					</Show>
					<div class={styles.debugResults}>
						<For each={edits()}>{(edit) => <EditRow edit={edit} />}</For>
					</div>
				</section>

				<section class={styles.debugSection} aria-labelledby="missing-readme-heading">
					<h3 id="missing-readme-heading">Modules missing readme.md</h3>
					<Show when={!missingReadmes.loading} fallback={<p class={styles.metadata}>Loading…</p>}>
						<Show when={(missingReadmes()?.modules ?? []).length > 0} fallback={<p class={styles.metadata}>Every module has a readme.md.</p>}>
							<div class={styles.debugResults}>
								<For each={missingReadmes()?.modules ?? []}>{(module) => (
									<div class={styles.debugItem}>
										<strong>{module.owner}:{module.module_id}</strong>
										<span>{module.path}</span>
										<Show when={module.path}>{(path) => <OpenFileActions label="Module" repository="game" path={path()} />}</Show>
									</div>
								)}</For>
							</div>
						</Show>
					</Show>
				</section>
			</div>

			<section class={styles.debugSection} aria-labelledby="unresolved-heading">
				<h3 id="unresolved-heading">Unresolved markers ({unresolved()?.unresolved_markers?.length ?? 0})</h3>
				<Show when={!unresolved.loading} fallback={<p class={styles.metadata}>Loading…</p>}>
					<Show when={(unresolved()?.unresolved_markers ?? []).length > 0} fallback={<p class={styles.metadata}>No unresolved markers.</p>}>
						<div class={styles.markerList}>
							<For each={(unresolved()?.unresolved_markers ?? []).slice(0, markerLimit())}>
								{(marker) => <MarkerRow marker={marker} onSaved={props.onRescan} />}
							</For>
						</div>
						<Show when={markerLimit() < (unresolved()?.unresolved_markers ?? []).length}>
							<button type="button" class={styles.loadMore} onClick={() => setMarkerLimit((value) => value + MARKER_PAGE_SIZE)}>
								Show {Math.min(MARKER_PAGE_SIZE, (unresolved()?.unresolved_markers ?? []).length - markerLimit())} more
							</button>
						</Show>
					</Show>
				</Show>
			</section>
		</details>
	);
}

function EditRow(props: { readonly edit: GraphEdit }) {
	const path = () => props.edit.core_file ?? props.edit.target ?? '';
	return (
		<div class={styles.debugItem}>
			<strong>{props.edit.owner ?? 'unknown'} {props.edit.edit_type ?? 'edit'}{props.edit.line_number ? ` · line ${props.edit.line_number}` : ''}</strong>
			<span>{props.edit.resolved ? 'Resolved' : 'Unresolved'} · {props.edit.raw_label ?? props.edit.source_module_id ?? '(no label)'}</span>
			<Show when={path()}>{(value) => <OpenFileActions label="Core file" repository="game" path={value()} line={props.edit.line_number} />}</Show>
		</div>
	);
}

function MarkerRow(props: { readonly marker: Marker; readonly onSaved: () => Promise<void> }) {
	const [history, setHistory] = createSignal<MarkerHistoryResponse | null>(null);
	const [historyOpen, setHistoryOpen] = createSignal(false);
	const [editing, setEditing] = createSignal(false);
	const [label, setLabel] = createSignal(props.marker.raw_label);
	const [busy, setBusy] = createSignal(false);
	const [message, setMessage] = createSignal('');
	const [stage, setStage] = createSignal<components['schemas']['MarkerEditResponse'] | null>(null);

	async function toggleHistory(): Promise<void> {
		const opening = !historyOpen();
		setHistoryOpen(opening);
		if (!opening || history()) return;
		try {
			setHistory(await api.get<MarkerHistoryResponse>(
				`/api/git/marker-history?core_file=${encodeURIComponent(props.marker.core_file)}&line=${props.marker.line_number}`,
			));
		} catch (error) {
			setMessage(error instanceof Error ? error.message : String(error));
		}
	}

	async function save(): Promise<void> {
		if (busy()) return;
		setBusy(true);
		setMessage('');
		try {
			const prepared = await api.post<components['schemas']['MarkerEditResponse']>('/api/graph/markers/edit', {
				core_file: props.marker.core_file,
				line_number: props.marker.line_number,
				expected_line: props.marker.line_text,
				new_label: label(),
			});
			setStage(prepared);
		} catch (error) {
			const message = error instanceof Error ? error.message : String(error);
			setMessage(message);
			reportParsec({ type: 'mutation', phase: 'failed', tool: 'content-graph', summary: 'Could not save the marker label.', technicalDetail: message });
		} finally {
			setBusy(false);
		}
	}

	async function apply(): Promise<void> {
		const prepared = stage();
		if (!prepared || busy()) return;
		setBusy(true);
		try {
			await api.post('/api/graph/markers/apply', { stage_id: prepared.stage_id });
			setStage(null); setEditing(false);
			setMessage('Applied. Rescanning to refresh attribution…');
			reportParsec({ type: 'mutation', phase: 'completed', tool: 'content-graph', summary: 'Marker label saved.' });
			await props.onSaved();
		} catch (error) {
			setStage(null);
			setMessage(error instanceof Error ? error.message : String(error));
		} finally { setBusy(false); }
	}

	return (
		<article class={styles.markerItem}>
			<strong>{props.marker.core_file}:{props.marker.line_number}</strong>
			<span>{props.marker.owner} {props.marker.edit_type} · {props.marker.attribution}</span>
			<code>{props.marker.raw_label || '(no label)'}</code>
			<OpenFileActions label="Source" repository="game" path={props.marker.core_file} line={props.marker.line_number} />
			<div class={styles.buttonRow}>
				<button type="button" onClick={() => void toggleHistory()}>{historyOpen() ? 'Hide history' : 'View history'}</button>
				<button type="button" disabled={busy()} onClick={() => { setStage(null); setEditing((value) => !value); }}>{editing() ? 'Cancel edit' : 'Edit label'}</button>
			</div>
			<Show when={historyOpen()}>
				<div class={styles.history}>
					<Show when={history()} fallback={<p class={styles.metadata}>Loading history…</p>}>
						{(result) => <Show when={result().commits.length > 0} fallback={<p class={styles.metadata}>No Git history found for this line.</p>}>
							<For each={result().commits}>{(commit) => (
								<div class={styles.historyCommit}>
									<strong>{commit.short_commit} · {commit.author} · {commit.date}</strong>
									<span>{commit.subject}</span>
									<Show when={commit.pr_url}>{(url) => <a href={url()} target="_blank" rel="noopener">Pull request</a>}</Show>
									<pre>{commit.diff}</pre>
								</div>
							)}</For>
						</Show>}
					</Show>
				</div>
			</Show>
			<Show when={editing()}>
				<div class={styles.inlineControls}>
					<input type="text" aria-label="Marker label" disabled={busy()} value={label()} onInput={(event) => { setStage(null); setLabel(event.currentTarget.value); }} />
					<button type="button" disabled={busy()} onClick={() => void save()}>Preview change</button>
				</div>
				<Show when={stage()}>{(prepared) => <div>
					<pre aria-label="Marker change preview">{prepared().preview || 'No changes.'}</pre>
					<button type="button" disabled={busy() || !prepared().preview} onClick={() => void apply()}>Apply change</button>
				</div>}</Show>
			</Show>
			<Show when={message()}>{(text) => <p class={styles.metadata} role="status">{text()}</p>}</Show>
		</article>
	);
}

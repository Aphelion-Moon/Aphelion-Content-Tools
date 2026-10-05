import { For, Show, createEffect, createResource, createSignal, onCleanup } from 'solid-js';
import Card, { cardStyles } from '~/components/Card';
import { api } from '~/lib/api';
import { createAsyncScope } from '~/lib/asyncScope';
import { waitForToolRun } from '~/lib/toolRuns';
import { reportParsec } from '~/lib/parsec/coordinator';
import { appState } from '~/store/appStore';
import { formatBytes } from '~/lib/format';
import type { components } from '~/lib/api-schema';
import styles from './FileManagement.module.css';

type ToolSummary = components['schemas']['ToolSummary'];
type ToolRun = components['schemas']['ToolRun'];

interface ToolList {
	readonly tools: readonly ToolSummary[];
}

// Release loading is the writer recovery path. Native probe and generated-output operations stay
// under the advanced disclosure because they require a configured game build environment.
const GROUPS: Record<string, string> = {
	'catalog-reload': 'catalog',
	'refresh-validate': 'catalog-advanced',
	'catalog-refresh': 'catalog-advanced',
	validate: 'catalog-advanced',
	generate: 'catalog-advanced',
	'scan-content': 'graph',
	'rebuild-search-embeddings': 'maintenance',
	'optimize-store': 'maintenance',
};

export default function ToolRunner() {
	const [tools] = createResource(() => api.get<ToolList>('/api/tools'));
	const [output, setOutput] = createSignal('');
	const [logPath, setLogPath] = createSignal('');
	const [activeRunId, setActiveRunId] = createSignal<string | null>(null);
	const [stopping, setStopping] = createSignal(false);
	const [starting, setStarting] = createSignal(false);
	const requests = createAsyncScope();

	const observer = new AbortController();
	const attachedRunIds = new Set<string>();
	onCleanup(() => { requests.dispose(); observer.abort(); });

	const inGroup = (group: string) =>
		(tools()?.tools ?? []).filter((tool) => (GROUPS[tool.id] ?? 'catalog') === group);

	async function poll(runId: string): Promise<void> {
		const isCurrent = requests.capture();
		try {
			const run = await waitForToolRun(runId, {
				signal: observer.signal,
				onUpdate: (progress) => { setOutput(progress.output || ''); setLogPath(progress.log_path ?? ''); },
			});
			if (!isCurrent()) return;

			setActiveRunId(null);
			setStopping(false);
			if (run.status === 'succeeded') {
				reportParsec({ type: 'job', phase: 'completed', tool: 'file-management', summary: `${run.tool_id} completed successfully.`, dedupeKey: `tool-run:${runId}` });
			} else if (run.status === 'failed') {
				const message = run.output || `${run.tool_id} failed.`;
				reportParsec({ type: 'job', phase: 'failed', tool: 'file-management', summary: `${run.tool_id} failed.`, technicalDetail: message, dedupeKey: `tool-run:${runId}` });
			}
		} catch (error) {
			if (!isCurrent()) return;
			const message = error instanceof Error ? error.message : String(error);
			setOutput(message);
			setActiveRunId(null);
			setStopping(false);
			reportParsec({ type: 'job', phase: 'failed', tool: 'file-management', summary: 'Could not read the tool run.', technicalDetail: message, dedupeKey: `tool-run:${runId}` });
		}
	}

	createEffect(() => {
		const repositoryRun = appState.activeRuns[0];
		if (!repositoryRun || starting() || activeRunId() !== null || attachedRunIds.has(repositoryRun.run_id)) return;
		attachedRunIds.add(repositoryRun.run_id);
		setActiveRunId(repositoryRun.run_id);
		void poll(repositoryRun.run_id);
	});

	async function runTool(toolId: string): Promise<void> {
		if (starting() || activeRunId() !== null) return;
		requests.invalidate();
		const isCurrent = requests.capture();
		setStarting(true);
		setOutput(`Starting ${toolId}…`);
		setLogPath('');
		try {
			const run = await api.post<ToolRun>(`/api/tools/${encodeURIComponent(toolId)}`);
			if (!isCurrent()) return;
			attachedRunIds.add(run.run_id);
			setActiveRunId(run.run_id);
			reportParsec({ type: 'job', phase: 'started', tool: 'file-management', summary: `Running ${toolId}.`, dedupeKey: `tool-run:${run.run_id}` });
			await poll(run.run_id);
		} catch (error) {
			if (!isCurrent()) return;
			const message = error instanceof Error ? error.message : String(error);
			setOutput(message);
			reportParsec({ type: 'job', phase: 'failed', tool: 'file-management', summary: `Could not start ${toolId}.`, technicalDetail: message });
		} finally { if (isCurrent()) setStarting(false); }
	}

	async function stopRun(): Promise<void> {
		const isCurrent = requests.capture();
		const runId = activeRunId();
		if (!runId) return;
		setStopping(true);
		try {
			await api.post(`/api/tools/runs/${encodeURIComponent(runId)}/stop`);
		} catch (error) {
			if (!isCurrent()) return;
			const message = error instanceof Error ? error.message : String(error);
			reportParsec({ type: 'job', phase: 'failed', tool: 'file-management', summary: 'Could not stop the tool run.', technicalDetail: message });
			setStopping(false);
		}
	}

	const busy = () => starting() || activeRunId() !== null;

	return (
		<Card eyebrow="Repository operations" heading="Database and Git">
			<p class={cardStyles.metadata}>
				Background jobs that keep the shared data store in sync with the game checkout, plus the store's
				own health. Nothing here runs on its own except one automatic database optimize shortly after
				startup — everything else is a snapshot that updates only when you run the matching job.
			</p>

			<ToolGroup
				title="1. Catalog & validation"
				blurb="Load the release catalog supplied by your maintainer. Advanced actions rebuild local authoring data or validate content."
				tools={inGroup('catalog')}
				advanced={inGroup('catalog-advanced')}
				busy={busy()}
				onRun={runTool}
			/>
			<ToolGroup
				title="2. Content graph"
				blurb="Run after pulling game-repo changes, or after editing marker comments or master_files overrides."
				tools={inGroup('graph')}
				busy={busy()}
				onRun={runTool}
			/>
			<ToolGroup
				title="3. Database maintenance"
				blurb="Rebuild embeddings only after changing the embedding model. Optimize compacts and prunes the store."
				tools={inGroup('maintenance')}
				busy={busy()}
				onRun={runTool}
			/>

			<Show when={appState.health}>
				{(health) => (
					<p class={cardStyles.metadata}>
						<strong>{health().total_rows.toLocaleString()}</strong> rows across{' '}
						{Object.keys(health().tables).length} tables · {formatBytes(health().disk_bytes)} on disk
					</p>
				)}
			</Show>

			<Show when={activeRunId() !== null}>
				<div class={styles.stopRow}>
					<button type="button" disabled={stopping()} onClick={() => void stopRun()}>
						{stopping() ? 'Stopping…' : 'Stop'}
					</button>
				</div>
			</Show>

			<Show when={output()}>
				{(text) => (
					<pre class={styles.output} aria-live="polite">
						{text()}
					</pre>
				)}
			</Show>
			<Show when={logPath()}>{(path) => <p class={cardStyles.metadata}>Log file: {path()}</p>}</Show>
		</Card>
	);
}

function ToolGroup(props: {
	readonly title: string;
	readonly blurb: string;
	readonly tools: readonly ToolSummary[];
	readonly advanced?: readonly ToolSummary[];
	readonly busy: boolean;
	readonly onRun: (toolId: string) => void;
}) {
	return (
		<div class={styles.group}>
			<h3>{props.title}</h3>
			<p class={cardStyles.metadata}>{props.blurb}</p>
			<div class={styles.toolList}>
				<For each={props.tools}>
					{(tool) => (
						<button type="button" title={tool.description} disabled={props.busy} onClick={() => props.onRun(tool.id)}>
							{tool.label}
						</button>
					)}
				</For>
			</div>
			<Show when={props.advanced?.length}>
				<details class={styles.advanced}>
					<summary>Advanced catalog actions</summary>
					<div class={styles.toolList}>
						<For each={props.advanced}>
							{(tool) => (
								<button
									type="button"
									title={tool.description}
									disabled={props.busy}
									onClick={() => props.onRun(tool.id)}
								>
									{tool.label}
								</button>
							)}
						</For>
					</div>
				</details>
			</Show>
		</div>
	);
}

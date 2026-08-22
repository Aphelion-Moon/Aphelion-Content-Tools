import { For, Show, createResource, createSignal, onCleanup } from 'solid-js';
import Card, { cardStyles } from '~/components/Card';
import { api } from '~/lib/api';
import { announceError, announceSuccess } from '~/lib/notify';
import { appState } from '~/store/appStore';
import { formatBytes } from '~/lib/format';
import type { components } from '~/lib/api-schema';
import styles from './FileManagement.module.css';

type ToolSummary = components['schemas']['ToolSummary'];
type ToolRun = components['schemas']['ToolRun'];

interface ToolList {
	readonly tools: readonly ToolSummary[];
}

// Which panel each tool's button belongs to. "refresh-validate" is the one pipeline step most people
// want; its individual halves sit under the advanced disclosure rather than competing with it at the
// same level.
const GROUPS: Record<string, string> = {
	'refresh-validate': 'catalog',
	'catalog-refresh': 'catalog-advanced',
	validate: 'catalog-advanced',
	generate: 'catalog-advanced',
	'scan-content': 'graph',
	'rebuild-search-embeddings': 'maintenance',
	'optimize-store': 'maintenance',
};

const POLL_MS = 750;

export default function ToolRunner() {
	const [tools] = createResource(() => api.get<ToolList>('/api/tools'));
	const [output, setOutput] = createSignal('');
	const [logPath, setLogPath] = createSignal('');
	const [activeRunId, setActiveRunId] = createSignal<string | null>(null);
	const [stopping, setStopping] = createSignal(false);

	let pollTimer: ReturnType<typeof setTimeout> | undefined;
	onCleanup(() => clearTimeout(pollTimer));

	const inGroup = (group: string) =>
		(tools()?.tools ?? []).filter((tool) => (GROUPS[tool.id] ?? 'catalog') === group);

	async function poll(runId: string): Promise<void> {
		try {
			const run = await api.get<ToolRun>(`/api/tools/runs/${encodeURIComponent(runId)}`);
			setOutput(run.output || '');
			setLogPath(run.log_path ?? '');

			if (run.status === 'queued' || run.status === 'running') {
				pollTimer = setTimeout(() => void poll(runId), POLL_MS);
				return;
			}

			setActiveRunId(null);
			setStopping(false);
			if (run.status === 'succeeded') announceSuccess(`${run.tool_id} completed successfully.`, 'file-management');
			else if (run.status === 'failed') announceError(new Error(`${run.tool_id} failed.`), 'file-management');
		} catch (error) {
			setOutput(error instanceof Error ? error.message : String(error));
			setActiveRunId(null);
			setStopping(false);
		}
	}

	async function runTool(toolId: string): Promise<void> {
		setOutput(`Starting ${toolId}…`);
		setLogPath('');
		try {
			const run = await api.post<ToolRun>(`/api/tools/${encodeURIComponent(toolId)}`);
			setActiveRunId(run.run_id);
			await poll(run.run_id);
		} catch (error) {
			setOutput(error instanceof Error ? error.message : String(error));
			announceError(error, 'file-management');
		}
	}

	async function stopRun(): Promise<void> {
		const runId = activeRunId();
		if (!runId) return;
		setStopping(true);
		try {
			await api.post(`/api/tools/runs/${encodeURIComponent(runId)}/stop`);
		} catch (error) {
			announceError(error, 'file-management');
			setStopping(false);
		}
	}

	const busy = () => activeRunId() !== null;

	return (
		<Card eyebrow="Repository operations" heading="Database and Git">
			<p class={cardStyles.metadata}>
				Background jobs that keep the shared data store in sync with the game checkout, plus the store's
				own health. Nothing here runs on its own except one automatic database optimize shortly after
				startup — everything else is a snapshot that updates only when you run the matching job.
			</p>

			<ToolGroup
				title="1. Catalog & validation"
				blurb="Run after pulling game-repo changes, or after hand-editing override JSON outside the Lore Editor."
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

			<Show when={busy()}>
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
					<summary>Run an individual step instead</summary>
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

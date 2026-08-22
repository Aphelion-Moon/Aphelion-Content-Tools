import { For, Show, createResource, createSignal } from 'solid-js';
import Card, { cardStyles } from '~/components/Card';
import { api } from '~/lib/api';
import { announceError, announceSuccess } from '~/lib/notify';
import { cx } from '~/lib/cx';
import type { components } from '~/lib/api-schema';
import styles from './FileManagement.module.css';

type RepositoryStatus = components['schemas']['RepositoryStatus'];
// RepositoryName is a Literal alias on the Python side, so it is inlined into each operation's
// parameters rather than emitted as a named schema. Declared here to match, in one place.
export type RepositoryName = 'tool' | 'game';

interface BranchList {
	readonly branches: readonly string[];
}

interface RepositoryPanelProps {
	readonly repository: RepositoryName;
	readonly heading: string;
	readonly blurb: string;
}

/** One repository's Git panel. Rendered twice -- for this tool's checkout and for the game checkout. */
export default function RepositoryPanel(props: RepositoryPanelProps) {
	const [message, setMessage] = createSignal('');
	const [busy, setBusy] = createSignal(false);
	const [newBranch, setNewBranch] = createSignal('');
	const [commitMessage, setCommitMessage] = createSignal('');
	const [selectedBranch, setSelectedBranch] = createSignal('');

	const [status, { refetch: refetchStatus }] = createResource(
		() => props.repository,
		(repository) => api.get<RepositoryStatus>(`/api/git/status?repository=${repository}`),
	);
	const [branches, { refetch: refetchBranches }] = createResource(
		() => props.repository,
		(repository) => api.get<BranchList>(`/api/git/branches?repository=${repository}`),
	);

	const currentBranch = () => selectedBranch() || status()?.branch || '';

	async function refreshAll(): Promise<void> {
		await Promise.all([refetchStatus(), refetchBranches()]);
	}

	/** Every mutation reports the same way: inline message plus a Parsec announcement. */
	async function run(action: () => Promise<string>): Promise<void> {
		setBusy(true);
		try {
			const result = await action();
			setMessage(result);
			announceSuccess(result, 'file-management');
			await refreshAll();
		} catch (error) {
			const text = error instanceof Error ? error.message : String(error);
			setMessage(text);
			announceError(error, 'file-management');
		} finally {
			setBusy(false);
		}
	}

	const createBranch = () =>
		run(async () => {
			const name = newBranch().trim();
			if (!name) throw new Error('Enter a branch name first.');
			await api.post('/api/git/branch', { name, repository: props.repository });
			setNewBranch('');
			return `Created and switched to ${name}.`;
		});

	const switchBranch = () =>
		run(async () => {
			const name = currentBranch();
			if (!name) throw new Error('Choose a branch to switch to first.');
			await api.post('/api/git/switch-branch', { name, repository: props.repository });
			return `Switched to ${name}.`;
		});

	const commit = () =>
		run(async () => {
			const changed = status()?.changed_files ?? [];
			const text = commitMessage().trim();
			if (!changed.length) throw new Error('No changed files to commit.');
			if (!text) throw new Error('Enter a commit message first.');
			await api.post('/api/git/commit', {
				message: text,
				paths: changed,
				repository: props.repository,
			});
			setCommitMessage('');
			return `Committed ${changed.length} file(s).`;
		});

	const openDesktop = () =>
		run(async () => {
			await api.post('/api/git/open', { repository: props.repository });
			return 'Opened in GitHub Desktop.';
		});

	return (
		<Card eyebrow="Local Git workflow" heading={props.heading}>
			<p class={cardStyles.metadata}>{props.blurb}</p>

			<Show when={status()} fallback={<p class={cardStyles.metadata}>Loading status…</p>}>
				{(current) => (
					<>
						<p class={cx(current().dirty ? styles.dirty : styles.clean)}>
							{current().dirty ? 'Changes pending' : 'Clean'} · {current().branch}
						</p>
						<p class={cardStyles.metadata}>
							{current().changed_files.length
								? `${current().changed_files.length} changed file(s)`
								: 'No changed files'}
							<Show when={current().ahead}>{(n) => <> · ahead {n()}</>}</Show>
							<Show when={current().behind}>{(n) => <> · behind {n()}</>}</Show>
							<Show when={current().conflicted}> · conflicts need attention</Show>
							<Show when={current().truncated_change_count}>
								{(n) => <> · {n()} more not listed</>}
							</Show>
						</p>

						<Show when={current().changed_files.length > 0}>
							<div class={styles.fileList}>
								<For each={current().changed_files}>
									{(path) => <ChangedFile repository={props.repository} path={path} />}
								</For>
							</div>
						</Show>
					</>
				)}
			</Show>

			<div class={styles.controls}>
				<div class={styles.row}>
					<label class={styles.field}>
						<span>Switch branch</span>
						<select
							value={currentBranch()}
							onChange={(event) => setSelectedBranch(event.currentTarget.value)}
						>
							<For each={branches()?.branches ?? []}>{(branch) => <option value={branch}>{branch}</option>}</For>
						</select>
					</label>
					<button type="button" disabled={busy()} onClick={switchBranch}>
						Switch
					</button>
				</div>

				<div class={styles.row}>
					<label class={styles.field}>
						<span>New local branch</span>
						<input
							type="text"
							placeholder="lore/company-review"
							value={newBranch()}
							onInput={(event) => setNewBranch(event.currentTarget.value)}
						/>
					</label>
					<button type="button" disabled={busy()} onClick={createBranch}>
						Create
					</button>
				</div>

				<div class={styles.row}>
					<label class={styles.field}>
						<span>Commit message</span>
						<input
							type="text"
							placeholder="Update lore review decisions"
							value={commitMessage()}
							onInput={(event) => setCommitMessage(event.currentTarget.value)}
						/>
					</label>
					<button type="button" disabled={busy()} onClick={commit}>
						Commit
					</button>
				</div>

				<div class={styles.row}>
					<button type="button" disabled={busy()} onClick={openDesktop}>
						Open in GitHub Desktop
					</button>
					<button type="button" disabled={busy()} onClick={() => void refreshAll()}>
						Refresh status
					</button>
				</div>
			</div>

			<Show when={message()}>{(text) => <p class={cardStyles.metadata}>{text()}</p>}</Show>
		</Card>
	);
}

/** One changed file, expanding to show its diff. The diff is fetched on first open, not up front. */
function ChangedFile(props: { readonly repository: RepositoryName; readonly path: string }) {
	const [open, setOpen] = createSignal(false);
	const [diff] = createResource(
		() => (open() ? { repository: props.repository, path: props.path } : undefined),
		async ({ repository, path }) => {
			const payload = await api.get<{ diff: string }>(
				`/api/git/diff?repository=${repository}&path=${encodeURIComponent(path)}`,
			);
			return payload.diff || '(no textual diff for this change)';
		},
	);

	return (
		<details class={styles.changedFile} onToggle={(event) => setOpen(event.currentTarget.open)}>
			<summary>{props.path}</summary>
			<Show when={open()}>
				<pre class={styles.diff}>{diff.loading ? 'Loading diff…' : (diff.error?.message ?? diff())}</pre>
			</Show>
		</details>
	);
}

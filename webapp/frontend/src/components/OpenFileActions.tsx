import { Show, createSignal } from 'solid-js';
import { api } from '~/lib/api';
import type { components } from '~/lib/api-schema';
import { reportParsec } from '~/lib/parsec/coordinator';
import styles from './OpenFileActions.module.css';

type RepositoryName = 'tool' | 'game';
type GithubUrlResponse = components['schemas']['GithubUrlResponse'];

export default function OpenFileActions(props: {
	readonly label: string;
	readonly repository: RepositoryName;
	readonly path: string;
	readonly line?: number | null | undefined;
}) {
	const [error, setError] = createSignal('');

	async function run(action: () => Promise<void>): Promise<void> {
		try {
			await action();
			setError('');
		} catch (caught) {
			const message = caught instanceof Error ? caught.message : String(caught);
			setError(message);
			reportParsec({ type: 'fetch', phase: 'failed', tool: 'open-file', summary: 'Could not open that file location.', technicalDetail: message });
		}
	}

	function openLocal(target: 'editor' | 'explorer'): Promise<void> {
		return run(async () => {
			await api.post('/api/git/open-file', {
				repository: props.repository,
				path: props.path,
				target,
			});
		});
	}

	function openGithub(): Promise<void> {
		return run(async () => {
			const response = await api.get<GithubUrlResponse>(
				`/api/git/github-url?repository=${props.repository}&path=${encodeURIComponent(props.path)}`,
			);
			if (!response.url) throw new Error('No GitHub remote is configured for this repository.');
			window.open(`${response.url}${props.line ? `#L${props.line}` : ''}`, '_blank', 'noopener');
		});
	}

	return (
		<div class={styles.actions}>
			<span class={styles.label}>{props.label}{props.line ? ` (line ${props.line})` : ''}:</span>
			<button type="button" onClick={() => void openLocal('editor')}>Editor</button>
			<button type="button" onClick={() => void openLocal('explorer')}>Explorer</button>
			<button type="button" onClick={() => void openGithub()}>GitHub</button>
			<Show when={error()}>{(message) => <p class={styles.error} role="alert">{message()}</p>}</Show>
		</div>
	);
}

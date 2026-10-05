import { Show, createSignal, onCleanup, onMount } from 'solid-js';
import { ApiError } from '~/lib/api';
import { createAsyncScope } from '~/lib/asyncScope';
import { collaborationApi, type CollaborationCapabilities } from './api';
import { type CollaborationState, versionState } from './state';
import styles from './CollaborationStatus.module.css';

export default function CollaborationStatus() {
	const [capabilities, setCapabilities] = createSignal<CollaborationCapabilities | null>(null);
	const [state, setState] = createSignal<CollaborationState>({ phase: 'checking', message: 'Checking…' });
	const scope = createAsyncScope();
	const isCurrent = scope.capture();

	async function loadVersion(): Promise<void> {
		setState({ phase: 'checking', message: 'Checking…' });
		try {
			const version = await collaborationApi.version();
			if (isCurrent()) setState(versionState(version, capabilities()?.reason ?? 'Session actions require user authorization.'));
		} catch (error) {
			if (!isCurrent()) return;
			const message = error instanceof ApiError ? error.message : 'Collaboration request failed.';
			setState({ phase: 'unavailable', message: `Unavailable — ${message}` });
		}
	}

	onMount(() => {
		void collaborationApi.capabilities().then(async (available) => {
			if (!isCurrent()) return;
			setCapabilities(available);
			if (available.configured && available.version) await loadVersion();
		}).catch(() => {
			// Local connectivity is owned by the shared live connection. An unknown or unconfigured
			// optional integration must not produce a second failing shell widget.
		});
	});
	onCleanup(() => scope.dispose());

	return (
		<Show when={capabilities()?.configured}>
			<section class={styles.panel} aria-label="Map collaboration">
				<div class={styles.heading}>Map collaboration</div>
				<p class={styles.status} role="status" aria-live="polite">{state().message}</p>
				<Show when={state().phase === 'unavailable'}>
					<button type="button" onClick={() => void loadVersion()}>Retry</button>
				</Show>
			</section>
		</Show>
	);
}

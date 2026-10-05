import { useNavigate } from '@solidjs/router';
import { For, Show, createEffect, createSignal, onCleanup } from 'solid-js';
import { listReferences, removeReference, type Reference, type ReferenceListResponse } from '~/lib/references';
import { createAsyncScope } from '~/lib/asyncScope';
import { reportParsec } from '~/lib/parsec/coordinator';
import { appState, setSelectedContext, type SelectedContext } from '~/store/appStore';
import styles from './SharedReferences.module.css';

export function contextFromReference(reference: Reference): SelectedContext {
	return {
		tool: reference.tool,
		record_kind: reference.kind,
		record_id: reference.key,
		type_path: reference.kind === 'catalog_target' || reference.kind === 'definition' ? reference.key : null,
		...(reference.catalog_id ? { catalog_id: reference.catalog_id } : {}),
		groups: [],
		module: null,
	};
}

export function referenceRoute(reference: Reference): string {
	const params = new URLSearchParams({ selected: reference.key });
	if (reference.kind === 'catalog_target' || reference.kind === 'definition') params.set('type_path', reference.key);
	if (reference.catalog_id) params.set('catalog_id', reference.catalog_id);
	const route = reference.tool === 'lore-editor'
		? '/lore-editor'
		: reference.tool === 'graph' ? '/graph' : reference.tool === 'job-editor' || reference.tool === 'outfit-editor' ? `/${reference.tool}` : '/file-management';
	return `${route}?${params.toString()}`;
}

export default function SharedReferences() {
	const navigate = useNavigate();
	const [error, setError] = createSignal('');
	const [references, setReferences] = createSignal<ReferenceListResponse | null>(null);
	const [loading, setLoading] = createSignal(true);
	const [revisionNotice, setRevisionNotice] = createSignal<string | null>(null);
	const requests = createAsyncScope();
	let observedRevisionKey: string | undefined;

	onCleanup(() => requests.dispose());

	async function load(): Promise<void> {
		requests.invalidate();
		const isCurrent = requests.capture();
		setLoading(true);
		try {
			const response = await listReferences();
			if (!isCurrent()) return;
			setReferences(response);
			setError('');
			if (revisionNotice()) setRevisionNotice('Workspace changed. References refreshed.');
		} catch (caught) {
			if (!isCurrent()) return;
			setError(caught instanceof Error ? caught.message : String(caught));
			setReferences({ references: [] });
		} finally {
			if (isCurrent()) setLoading(false);
		}
	}

	createEffect(() => {
		const revision = appState.workspaceRevision;
		const nextKey = revision === null ? '' : JSON.stringify(revision);
		if (observedRevisionKey === undefined) {
			observedRevisionKey = nextKey;
			void load();
			return;
		}
		if (nextKey === observedRevisionKey) return;
		observedRevisionKey = nextKey;
		requests.invalidate();
		setReferences(null);
		setError('');
		setRevisionNotice('Workspace changed. Refreshing references…');
		void load();
	});

	function select(reference: Reference): void {
		setSelectedContext(contextFromReference(reference));
		navigate(referenceRoute(reference));
	}

	async function remove(reference: Reference): Promise<void> {
		try {
			await removeReference(reference.id);
			setError('');
			reportParsec({ type: 'mutation', phase: 'completed', tool: 'references', summary: `Removed ${reference.label} from references.` });
			await load();
		} catch (caught) {
			const message = caught instanceof Error ? caught.message : String(caught);
			setError(message);
			reportParsec({ type: 'mutation', phase: 'failed', tool: 'references', summary: 'Could not remove the shared reference.', technicalDetail: message });
		}
	}

	return (
		<section class={styles.panel} aria-labelledby="shared-references-heading">
			<h2 id="shared-references-heading" class={styles.heading}>Shared references</h2>
			<Show when={!loading()} fallback={<p class={styles.status}>{revisionNotice() ?? 'Loading references…'}</p>}>
				<Show when={(references()?.references.length ?? 0) > 0} fallback={<p class={styles.empty}>No pinned references yet.</p>}>
					<ul class={styles.list}>
						<For each={references()?.references ?? []}>
							{(reference) => (
								<li class={styles.item}>
									<button type="button" class={styles.select} title={reference.key} onClick={() => select(reference)}>{reference.label}</button>
									<button type="button" class={styles.remove} aria-label={`Remove ${reference.label} from references`} onClick={() => void remove(reference)}>×</button>
								</li>
							)}
						</For>
					</ul>
				</Show>
			</Show>
			<Show when={revisionNotice() && !loading()}>{(message) => <p class={styles.status} role="status">{message()}</p>}</Show>
			<Show when={error()}>{(message) => <p class={styles.status} role="alert">{message()}</p>}</Show>
		</section>
	);
}

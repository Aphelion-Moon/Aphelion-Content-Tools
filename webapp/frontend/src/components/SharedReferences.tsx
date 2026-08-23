import { useNavigate } from '@solidjs/router';
import { For, Show, createResource, createSignal } from 'solid-js';
import { listReferences, referenceRevision, removeReference, type Reference } from '~/lib/references';
import { announceError, announceSuccess } from '~/lib/notify';
import { setSelectedContext, type SelectedContext } from '~/store/appStore';
import styles from './SharedReferences.module.css';

export function contextFromReference(reference: Reference): SelectedContext {
	return {
		tool: reference.tool,
		record_kind: reference.kind,
		record_id: reference.key,
		type_path: reference.kind === 'catalog_target' ? reference.key : null,
		groups: [],
		module: null,
	};
}

export function referenceRoute(reference: Reference): string {
	const params = new URLSearchParams({ selected: reference.key });
	if (reference.kind === 'catalog_target') params.set('type_path', reference.key);
	const route = reference.tool === 'lore-editor'
		? '/lore-editor'
		: reference.tool === 'graph' ? '/graph' : '/file-management';
	return `${route}?${params.toString()}`;
}

export default function SharedReferences() {
	const navigate = useNavigate();
	const [error, setError] = createSignal('');
	const [references, { refetch }] = createResource(
		() => referenceRevision() + 1,
		async () => {
			try {
				const response = await listReferences();
				setError('');
				return response;
			} catch (caught) {
				setError(caught instanceof Error ? caught.message : String(caught));
				return { references: [] };
			}
		},
	);

	function select(reference: Reference): void {
		setSelectedContext(contextFromReference(reference));
		navigate(referenceRoute(reference));
	}

	async function remove(reference: Reference): Promise<void> {
		try {
			await removeReference(reference.id);
			setError('');
			announceSuccess(`Removed ${reference.label} from references.`, 'references');
			await refetch();
		} catch (caught) {
			setError(caught instanceof Error ? caught.message : String(caught));
			announceError(caught, 'references');
		}
	}

	return (
		<section class={styles.panel} aria-labelledby="shared-references-heading">
			<h2 id="shared-references-heading" class={styles.heading}>Shared references</h2>
			<Show when={!references.loading} fallback={<p class={styles.status}>Loading references…</p>}>
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
			<Show when={error()}>{(message) => <p class={styles.status} role="alert">{message()}</p>}</Show>
		</section>
	);
}

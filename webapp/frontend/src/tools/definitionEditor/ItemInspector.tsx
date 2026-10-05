import { For, Show, createEffect, createSignal, onCleanup } from 'solid-js';
import { api } from '~/lib/api';
import type { components } from '~/lib/api-schema';
import styles from './DefinitionEditor.module.css';

type Metadata = components['schemas']['ItemPreview'];

export default function ItemInspector(props: { typePath: string; catalogId: string; slot?: string | undefined }) {
	const [metadata, setMetadata] = createSignal<Metadata>();
	const [message, setMessage] = createSignal('');
	const [direction, setDirection] = createSignal(2);
	const [frame, setFrame] = createSignal(0);
	createEffect(() => {
		const controller = new AbortController();
		onCleanup(() => controller.abort());
		setMetadata(undefined); setMessage('Loading item preview…'); setFrame(0); setDirection(2);
		const params = new URLSearchParams({ type_path: props.typePath, catalog_id: props.catalogId, slot: props.slot ?? '' });
		void api.get<Metadata>(`/api/definitions/item-preview?${params}`, { signal: controller.signal }).then((result) => {
			if (!controller.signal.aborted) { setMetadata(result); setMessage(''); }
		}).catch((error) => { if (!controller.signal.aborted) setMessage(String(error)); });
	});
	const image = () => `/api/definitions/item-image?${new URLSearchParams({ type_path: props.typePath, catalog_id: props.catalogId, asset_hash: metadata()!.asset_sha256, direction: String(direction()), frame: String(frame()) })}`;
	return <section class={styles.group} aria-label="Item preview">
		<h3>Item preview</h3><code>{props.typePath}</code>
		<Show when={message()}><p role="status">{message()}</p></Show>
		<Show when={metadata()}>
			<div class={styles.preview}><img src={image()} alt={`Item ${props.typePath}, direction ${direction()}, frame ${frame() + 1}`} /></div>
			<label>Direction<select value={direction()} onChange={(event) => setDirection(Number(event.currentTarget.value))}><For each={metadata()!.directions}>{(value) => <option value={value}>{({ 2: 'South', 1: 'North', 4: 'East', 8: 'West' } as Record<number, string>)[value] ?? value}</option>}</For></select></label>
			<label>Frame<input type="number" min="1" max={metadata()!.frames} value={frame() + 1} onInput={(event) => setFrame(Math.max(0, Math.min(metadata()!.frames - 1, Number(event.currentTarget.value) - 1)))} /></label>
			<p class={styles.hint}>{metadata()!.file} · {metadata()!.state}</p>
			<For each={metadata()!.diagnostics}>{(line) => <p class={styles.hint}>{line}</p>}</For>
		</Show>
	</section>;
}

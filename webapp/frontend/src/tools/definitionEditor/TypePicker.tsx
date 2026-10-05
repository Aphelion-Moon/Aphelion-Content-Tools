import { For, Show, createEffect, createSignal, onCleanup } from 'solid-js';
import { createVirtualizer } from '@tanstack/solid-virtual';
import { api } from '~/lib/api';
import type { Definition, DefinitionList } from './types';
import { title } from './draft';
import styles from './DefinitionEditor.module.css';

export default function TypePicker(props: { kind: string; label: string; catalogId: string; onPick: (definition: Definition) => void }) {
	const [query, setQuery] = createSignal('');
	const [parent, setParent] = createSignal('');
	const [items, setItems] = createSignal<Definition[]>([]);
	const [total, setTotal] = createSignal(0);
	const [message, setMessage] = createSignal('');
	const [loading, setLoading] = createSignal(false);
	const [active, setActive] = createSignal(0);
	let scroller!: HTMLDivElement;
	let controller: AbortController | undefined;
	let generation = 0;
	const virtual = createVirtualizer({ get count() { return items().length; }, getScrollElement: () => scroller, estimateSize: () => 66, overscan: 6 });
	async function load(reset: boolean) {
		if (!reset && loading()) return;
		if (reset) { controller?.abort(); setItems([]); setActive(0); generation++; }
		const current = generation;
		controller = new AbortController();
		setLoading(true); setMessage('');
		try {
			const response = await api.get<DefinitionList>(`/api/definitions/catalog?kind=${encodeURIComponent(props.kind)}&query=${encodeURIComponent(query())}&subtype_of=${encodeURIComponent(parent())}&offset=${reset ? 0 : items().length}&limit=100`, { signal: controller.signal });
			if (current !== generation) return;
			if (response.catalog_id !== props.catalogId) { setMessage('Catalog changed. Refresh this selection.'); return; }
			setItems((previous) => reset ? response.definitions : [...previous, ...response.definitions]); setTotal(response.total);
		} catch (error) { if (current === generation && !(error instanceof DOMException && error.name === 'AbortError')) setMessage(String(error)); }
		finally { if (current === generation) setLoading(false); }
	}
	createEffect(() => { query(); parent(); props.kind; props.catalogId; controller?.abort(); generation++; setItems([]); setTotal(0); setActive(0); setLoading(true); const timer = setTimeout(() => void load(true), 150); onCleanup(() => clearTimeout(timer)); });
	onCleanup(() => { generation++; controller?.abort(); });
	const keyboard = (event: KeyboardEvent) => {
		if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
			event.preventDefault(); const index = Math.max(0, Math.min(items().length - 1, active() + (event.key === 'ArrowDown' ? 1 : -1))); setActive(index); virtual.scrollToIndex(index);
		} else if (event.key === 'Enter' && items()[active()]) { event.preventDefault(); props.onPick(items()[active()]!); }
	};
	const id = `types-${crypto.randomUUID()}`;
	return <section class={styles.picker} aria-label={props.label}>
		<label>{props.label}<input type="search" value={query()} onInput={(event) => setQuery(event.currentTarget.value)} onKeyDown={keyboard} role="combobox" aria-autocomplete="list" aria-expanded="true" aria-controls={id} aria-activedescendant={items().length ? `${id}-${active()}` : undefined} placeholder="Name or type path" /></label>
		<label class={styles.hint}>Subtypes of<input value={parent()} onInput={(event) => setParent(event.currentTarget.value)} placeholder="Optional parent type path" /></label>
		<div class={styles.typeList} ref={scroller} role="listbox" id={id} aria-label={props.label}>
			<div style={{ height: `${virtual.getTotalSize()}px`, position: 'relative' }}>
				<For each={virtual.getVirtualItems()}>{(row) => { const item = () => items()[row.index]!; return <div id={`${id}-${row.index}`} role="option" aria-selected={active() === row.index} class={styles.typeRow} style={{ transform: `translateY(${row.start}px)` }} onPointerMove={() => setActive(row.index)} onClick={() => props.onPick(item())}><Show when={item().kind === 'item' && item().fields?.some((field) => field.name === 'icon' && typeof field.value === 'string')}><img class={styles.thumbnail} loading="lazy" alt="" src={`/api/definitions/thumbnail?type_path=${encodeURIComponent(item().type_path)}&catalog_id=${encodeURIComponent(props.catalogId)}`} onError={(event) => { event.currentTarget.hidden = true; }} /></Show><strong>{title(item())}</strong><code>{item().type_path}</code></div>; }}</For>
			</div>
		</div>
		<p role="status">{message() || (loading() ? 'Loading definitions…' : `${items().length} of ${total()} definitions`)}</p>
		<Show when={items().length < total()}><button disabled={loading()} onClick={() => void load(false)}>Load more</button></Show>
	</section>;
}

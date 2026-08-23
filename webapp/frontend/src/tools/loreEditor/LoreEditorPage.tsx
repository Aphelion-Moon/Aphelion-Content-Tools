import { useBeforeLeave, useSearchParams } from '@solidjs/router';
import { For, Show, createEffect, createSignal } from 'solid-js';
import Card, { cardStyles } from '~/components/Card';
import { announceError } from '~/lib/notify';
import { appState, setSelectedContext } from '~/store/appStore';
import { DEFAULT_FILTERS, createReviewFeed, type ReviewEntry } from './reviewFeed';
import EntryEditor from './EntryEditor';
import GroupManager from './GroupManager';
import ReviewActions from './ReviewActions';
import ReviewList from './ReviewList';
import styles from './LoreEditor.module.css';

const SORTS = [
	{ value: 'name', label: 'Name' },
	{ value: 'type_path', label: 'Type path' },
	{ value: 'status', label: 'Status' },
	{ value: 'reviewed_at', label: 'Recently reviewed' },
];

const STATUSES = [
	{ value: 'unreviewed', label: 'Unreviewed' },
	{ value: 'reviewed', label: 'Reviewed' },
	{ value: 'overridden', label: 'Overridden' },
	{ value: 'needs-attention', label: 'Needs attention' },
];

export default function LoreEditorPage() {
	const [searchParams] = useSearchParams();
	const typePathParameter = searchParams.type_path;
	const linkedTypePath = Array.isArray(typePathParameter) ? typePathParameter[0] : typePathParameter;
	const requestedTypePath = linkedTypePath
		?? (appState.selectedContext?.tool === 'lore-editor' ? appState.selectedContext.type_path : null);
	const feed = createReviewFeed(requestedTypePath ? {
		...DEFAULT_FILTERS,
		query: requestedTypePath,
		sort: 'type_path',
		includeDirectional: true,
		includeRedundant: true,
	} : DEFAULT_FILTERS);
	const [selected, setSelected] = createSignal<ReviewEntry | null>(null);
	const [activeSection, setActiveSection] = createSignal<'review' | 'groups'>('review');
	const [editorDirty, setEditorDirty] = createSignal(false);
	const [reviewDirty, setReviewDirty] = createSignal(false);
	const [pendingReloadTypePath, setPendingReloadTypePath] = createSignal<string | null>(null);
	let errorElement: HTMLParagraphElement | undefined;
	let announcedError: string | null = null;

	useBeforeLeave((event) => {
		if (!(editorDirty() || reviewDirty()) || event.defaultPrevented) return;
		event.preventDefault();
		if (window.confirm('Discard the unsaved Lore changes?')) event.retry(true);
	});

	const changeSection = (section: 'review' | 'groups') => {
		if (section === activeSection()) return;
		if ((editorDirty() || reviewDirty()) && !window.confirm('Discard the unsaved Lore changes?')) return;
		setEditorDirty(false);
		setReviewDirty(false);
		setActiveSection(section);
	};

	const selectEntry = (entry: ReviewEntry) => {
		if ((editorDirty() || reviewDirty()) && selected()?.id !== entry.id && !window.confirm('Discard the unsaved Lore changes?')) return;
		setSelected(entry);
		setEditorDirty(false);
		setReviewDirty(false);
		setSelectedContext({
			tool: 'lore-editor',
			record_kind: 'catalog_target',
			record_id: entry.id,
			type_path: entry.type_path,
			groups: [...(entry.groups ?? [])],
		});
	};

	createEffect(() => {
		const target = pendingReloadTypePath() ?? requestedTypePath;
		if (!target || (!pendingReloadTypePath() && selected()?.type_path === target)) return;
		const exact = feed.entries().find((entry) => entry.type_path === target);
		if (!exact) return;
		setPendingReloadTypePath(null);
		selectEntry(exact);
	});

	const reloadTarget = (typePath: string) => {
		setEditorDirty(false);
		setReviewDirty(false);
		setSelected(null);
		setPendingReloadTypePath(typePath);
		feed.reload();
	};

	// Surface each load failure through Parsec and move focus to the inline alert so keyboard and
	// screen-reader users do not have to discover that the list silently stopped updating.
	createEffect(() => {
		const message = feed.error();
		if (!message || message === announcedError) return;
		announcedError = message;
		announceError(new Error(message), 'lore-editor');
		queueMicrotask(() => errorElement?.focus());
	});

	const update = (patch: Partial<typeof DEFAULT_FILTERS>) => feed.setFilters({ ...feed.filters(), ...patch });
	const toggleValue = (values: readonly string[], value: string, checked: boolean) =>
		checked ? [...new Set([...values, value])] : values.filter((current) => current !== value);

	return (
		<>
			<div class={styles.tabs} role="tablist" aria-label="Lore editor sections">
				<button type="button" role="tab" aria-selected={activeSection() === 'review'} onClick={() => changeSection('review')}>Review and author</button>
				<button type="button" role="tab" aria-selected={activeSection() === 'groups'} onClick={() => changeSection('groups')}>Group configuration</button>
			</div>

			<Show when={activeSection() === 'review'}>
			<Card eyebrow="Catalog" heading="Review and author">
				<p class={cardStyles.metadata}>
					Every entry matching the current filters is reachable — the list renders only what is on
					screen and loads further pages as you scroll. Directional subtypes and redundant inherited
					descriptions stay hidden unless you ask for them; they are a large, noisy tail.
				</p>

				<div class={styles.filters}>
					<label class={styles.field}>
						<span>Search</span>
						<input
							type="search"
							placeholder="Name, type path, description…"
							value={feed.filters().query}
							onInput={(event) => update({ query: event.currentTarget.value })}
						/>
					</label>


					<fieldset class={styles.filterChecks}>
						<legend>Status <span>{feed.filters().statuses.length ? `(${feed.filters().statuses.length})` : '(any)'}</span></legend>
						<For each={STATUSES}>{(option) => <label><input type="checkbox" checked={feed.filters().statuses.includes(option.value)} onChange={(event) => update({ statuses: toggleValue(feed.filters().statuses, option.value, event.currentTarget.checked) })} /> {option.label}</label>}</For>
					</fieldset>

					<fieldset class={styles.filterChecks}>
						<legend>Groups <span>{feed.filters().groups.length ? `(${feed.filters().groups.length})` : '(any)'}</span></legend>
						<div class={styles.filterButtons}>
							<button type="button" onClick={() => update({ groups: (feed.meta()?.groups ?? []).map((group) => group.id) })}>Select all</button>
							<button type="button" onClick={() => update({ groups: [] })}>Clear</button>
						</div>
						<div class={styles.filterCheckList}><For each={feed.meta()?.groups ?? []}>
							{(group) => <label><input type="checkbox" checked={feed.filters().groups.includes(group.id)} onChange={(event) => update({ groups: toggleValue(feed.filters().groups, group.id, event.currentTarget.checked) })} /> {group.label}</label>}
						</For></div>
					</fieldset>

					<label class={styles.field}>
						<span>Sort</span>
						<select value={feed.filters().sort} onChange={(event) => update({ sort: event.currentTarget.value })}>
							<For each={SORTS}>{(option) => <option value={option.value}>{option.label}</option>}</For>
						</select>
					</label>
					<button type="button" class={styles.clearFilters} onClick={() => feed.setFilters(DEFAULT_FILTERS)}>Clear filters</button>
				</div>

				<div class={styles.toggles}>
					<label class={styles.toggle}>
						<input
							type="checkbox"
							checked={feed.filters().includeDirectional}
							onChange={(event) => update({ includeDirectional: event.currentTarget.checked })}
						/>
						Include directional
						<Show when={feed.meta()?.suppressed_counts['directional']}>
							{(n) => <> ({n().toLocaleString()})</>}
						</Show>
					</label>
					<label class={styles.toggle}>
						<input
							type="checkbox"
							checked={feed.filters().includeRedundant}
							onChange={(event) => update({ includeRedundant: event.currentTarget.checked })}
						/>
						Include redundant
						<Show when={feed.meta()?.suppressed_counts['redundant']}>
							{(n) => <> ({n().toLocaleString()})</>}
						</Show>
					</label>
				</div>

				<Show when={feed.meta()}>
					{(meta) => (
						<p class={styles.counts}>
							{meta().catalog_count.toLocaleString()} catalog targets ·{' '}
							{meta().approved_count.toLocaleString()} approved ·{' '}
							{meta().matched_entry_count.toLocaleString()} match the current filters
						</p>
					)}
				</Show>

				<Show when={feed.error()}>
					{(message) => (
						<p ref={errorElement} class={cardStyles.metadata} role="alert" tabIndex={-1}>
							{message()}
						</p>
					)}
				</Show>

				<ReviewList feed={feed} selectedId={selected()?.id ?? null} onSelect={selectEntry} />
			</Card>

			<Show when={selected()} keyed>
				{(entry) => (
					<Card eyebrow="Selected entry" heading={entry.name || entry.base_name || entry.label || 'Entry'}>
						<EntryEditor entry={entry} onDirtyChange={setEditorDirty} onReload={reloadTarget} />
						<ReviewActions entry={entry} onDirtyChange={setReviewDirty} onReload={reloadTarget} />
					</Card>
				)}
			</Show>
			</Show>

			<Show when={activeSection() === 'groups'}>
				<Card eyebrow="Taxonomy" heading="Group configuration"><GroupManager /></Card>
			</Show>
		</>
	);
}

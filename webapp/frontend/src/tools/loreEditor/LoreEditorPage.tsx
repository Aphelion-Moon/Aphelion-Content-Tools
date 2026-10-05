import { useBeforeLeave, useSearchParams } from '@solidjs/router';
import { Show, Suspense, createEffect, createSignal, onCleanup, onMount, untrack } from 'solid-js';
import Card, { cardStyles } from '~/components/Card';
import LoadingIndicator from '~/components/LoadingIndicator';
import { reportParsec } from '~/lib/parsec/coordinator';
import { appState, setSelectedContext } from '~/store/appStore';
import { DEFAULT_FILTERS, createReviewFeed, type ReviewEntry } from './reviewFeed';
import EntryEditor from './EntryEditor';
import GroupManager from './GroupManager';
import ReviewActions from './ReviewActions';
import ReviewFilters from './ReviewFilters';
import ReviewList from './ReviewList';
import { readReviewerIdentity, writeReviewerIdentity } from './reviewerIdentity';
import styles from './LoreEditor.module.css';

export default function LoreEditorPage() {
	const [searchParams] = useSearchParams();
	const linkedTypePath = () => {
		const parameter = searchParams.type_path;
		return Array.isArray(parameter) ? parameter[0] : parameter;
	};
	const requestedTypePath = linkedTypePath()
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
	const [reviewerName, setReviewerName] = createSignal(readReviewerIdentity());
	const [editorDirty, setEditorDirty] = createSignal(false);
	const [reviewDirty, setReviewDirty] = createSignal(false);
	const [groupDirty, setGroupDirty] = createSignal(false);
	const hasUnsavedChanges = () => editorDirty() || reviewDirty() || groupDirty();
	onMount(() => {
		const warn = (event: BeforeUnloadEvent) => { if (hasUnsavedChanges()) { event.preventDefault(); event.returnValue = ''; } };
		window.addEventListener('beforeunload', warn);
		onCleanup(() => window.removeEventListener('beforeunload', warn));
	});
	const [pendingReloadTypePath, setPendingReloadTypePath] = createSignal<string | null>(requestedTypePath ?? null);
	let errorElement: HTMLParagraphElement | undefined;
	let announcedError: string | null = null;

	useBeforeLeave((event) => {
		if (!hasUnsavedChanges() || event.defaultPrevented) return;
		event.preventDefault();
		if (window.confirm('Discard the unsaved Lore changes?')) event.retry(true);
	});

	const changeSection = (section: 'review' | 'groups') => {
		if (section === activeSection()) return;
		if (hasUnsavedChanges() && !window.confirm('Discard the unsaved Lore changes?')) return;
		setEditorDirty(false);
		setReviewDirty(false);
		setActiveSection(section);
	};

	const selectEntry = (entry: ReviewEntry) => {
		if (hasUnsavedChanges() && selected()?.id !== entry.id && !window.confirm('Discard the unsaved Lore changes?')) return;
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
		const target = pendingReloadTypePath();
		if (!target) return;
		const exact = feed.entries().find((entry) => entry.type_path === target);
		if (!exact) return;
		setPendingReloadTypePath(null);
		selectEntry(exact);
	});

	let previousLinkedTypePath = linkedTypePath();
	createEffect(() => {
		const target = linkedTypePath();
		if (target === previousLinkedTypePath) return;
		previousLinkedTypePath = target;
		if (!target) return;
		untrack(() => {
			setSelected(null);
			setEditorDirty(false);
			setReviewDirty(false);
			setActiveSection('review');
			feed.setFilters({ ...DEFAULT_FILTERS, query: target, sort: 'type_path', includeDirectional: true, includeRedundant: true });
			setPendingReloadTypePath(target);
		});
	});

	const reloadTarget = (typePath: string) => {
		setEditorDirty(false);
		setReviewDirty(false);
		setSelected(null);
		feed.reload();
		setPendingReloadTypePath(typePath);
	};

	const updateReviewerName = (value: string) => {
		setReviewerName(value);
		writeReviewerIdentity(value);
	};

	const selectedLabel = () => {
		const entry = selected();
		return entry?.name ?? entry?.base_name ?? entry?.label ?? entry?.type_path ?? 'selected catalog entry';
	};

	const authoringLoadingLabel = () => activeSection() === 'groups'
		? 'Loading group configuration'
		: `Loading ${selectedLabel()}`;
	const authoringFeedbackKey = () => activeSection() === 'groups'
		? 'lore-groups'
		: `lore-entry:${selected()?.id ?? 'unselected'}`;

	// Surface each load failure through Parsec and move focus to the inline alert so keyboard and
	// screen-reader users do not have to discover that the list silently stopped updating.
	createEffect(() => {
		const message = feed.error();
		if (!message || message === announcedError) return;
		announcedError = message;
		reportParsec({ type: 'fetch', phase: 'failed', tool: 'lore-editor', summary: 'Could not load the lore review queue.', technicalDetail: message });
		queueMicrotask(() => errorElement?.focus());
	});

	return (
		<>
			<section class={styles.workspaceHeader} aria-label="Lore workspace status">
				<div>
					<p class={cardStyles.eyebrow}>Workspace status</p>
					<h2>Writer review desk</h2>
					<Show when={feed.meta()} fallback={<p class={cardStyles.metadata}>Loading catalog…</p>}>
						{(meta) => <p class={cardStyles.metadata}>{meta().catalog_count.toLocaleString()} catalog targets · {meta().matched_entry_count.toLocaleString()} currently match</p>}
					</Show>
				</div>
				<label class={styles.reviewerField}>
					<span>Reviewer</span>
					<input
						autocomplete="name"
						value={reviewerName()}
						onInput={(event) => updateReviewerName(event.currentTarget.value)}
						placeholder="Your name"
					/>
				</label>
			</section>

			<section class={styles.workspace} aria-label="Lore review workspace">
				<div class={styles.workspaceCard}>
					<Card eyebrow="Review queue" heading="Catalog">
						<section class={styles.queuePane} aria-label="Lore review queue">
							<ReviewFilters feed={feed} />
							<Show when={feed.error()}>
								{(message) => (
									<p ref={errorElement} class={cardStyles.metadata} role="alert" tabIndex={-1}>
										{message()}
									</p>
								)}
							</Show>
							<ReviewList feed={feed} selectedId={selected()?.id ?? null} onSelect={selectEntry} />
						</section>
					</Card>
				</div>

				<div class={styles.workspaceCard}>
					<Card eyebrow="Selected target" heading={selected()?.name || selected()?.base_name || selected()?.label || 'Entry editor'}>
						<section class={styles.authoringPane} aria-label="Lore authoring surface">
							<div class={styles.tabs} role="tablist" aria-label="Lore editor sections">
								<button type="button" role="tab" aria-selected={activeSection() === 'review'} onClick={() => changeSection('review')}>Review</button>
								<button type="button" role="tab" aria-selected={activeSection() === 'groups'} onClick={() => changeSection('groups')}>Group configuration</button>
							</div>
							<div class={styles.authoringScroll}>
								<Suspense fallback={(
									<LoadingIndicator
										label={authoringLoadingLabel()}
										tool="lore-editor"
										reportThroughParsec
										feedbackKey={authoringFeedbackKey()}
									/>
								)}>
									<Show when={activeSection() === 'review'}>
										<Show when={selected()} keyed fallback={<p class={cardStyles.metadata}>Select a catalog target to begin reviewing or authoring.</p>}>
											{(entry) => (
												<>
													<EntryEditor entry={entry} onDirtyChange={setEditorDirty} onReload={reloadTarget} />
													<ReviewActions entry={entry} reviewerName={reviewerName()} onDirtyChange={setReviewDirty} onReload={reloadTarget} />
												</>
											)}
										</Show>
									</Show>
									<Show when={activeSection() === 'groups'}><GroupManager onDirtyChange={setGroupDirty} /></Show>
								</Suspense>
							</div>
						</section>
					</Card>
				</div>
			</section>
		</>
	);
}

import { For, Show, createEffect, onMount } from 'solid-js';
import { createVirtualizer } from '@tanstack/solid-virtual';
import { cx } from '~/lib/cx';
import type { ReviewEntry } from './reviewFeed';
import { PAGE_SIZE, createReviewFeed } from './reviewFeed';
import styles from './LoreEditor.module.css';

const ROW_HEIGHT = 62;
// Start fetching the next page while this many rows are still ahead of the viewport, so scrolling
// rarely reaches an unloaded region.
const PREFETCH_ROWS = 40;

function entryTitle(entry: ReviewEntry): string {
	return entry.name || entry.base_name || entry.label || entry.type_path || entry.id;
}

const STATUS_LABELS: Readonly<Record<string, string>> = {
	unreviewed: 'Unreviewed',
	reviewed: 'Reviewed',
	overridden: 'Overridden',
	'needs-attention': 'Needs attention',
};

function statusLabel(entry: ReviewEntry): string {
	return entry.status ? (STATUS_LABELS[entry.status] ?? entry.status) : 'Unknown status';
}

interface ReviewListProps {
	readonly feed: ReturnType<typeof createReviewFeed>;
	readonly selectedId: string | null;
	readonly onSelect: (entry: ReviewEntry) => void;
}

/**
 * The catalog review list.
 *
 * Virtualised: only the rows in view exist in the DOM, so the list stays responsive at any length. This
 * is what removes the old 500-row cap -- combined with paged fetching in reviewFeed, a writer can reach
 * every matching entry instead of the first 500.
 */
export default function ReviewList(props: ReviewListProps) {
	// A plain ref, not a signal: solid-virtual resolves the scroll element once inside its own onMount,
	// which runs after Solid has assigned refs. Passing a signal accessor here instead leaves the
	// virtualizer holding a null element -- it still reports a total size, but never produces any virtual
	// items, so the list renders empty.
	let scroller!: HTMLDivElement;

	const virtualizer = createVirtualizer({
		get count() {
			return props.feed.entries().length;
		},
		getScrollElement: () => scroller,
		estimateSize: () => ROW_HEIGHT,
		overscan: 12,
	});

	// Fetch the next page as the rendered window approaches the end of what is loaded.
	createEffect(() => {
		const items = virtualizer.getVirtualItems();
		const last = items[items.length - 1];
		if (!last) return;
		if (last.index >= props.feed.entries().length - PREFETCH_ROWS) {
			props.feed.loadMore();
		}
	});

	onMount(() => props.feed.reload());

	const selectWithKeyboard = (event: KeyboardEvent, entry: ReviewEntry) => {
		if (event.key !== 'Enter' && event.key !== ' ') return;
		event.preventDefault();
		props.onSelect(entry);
	};

	return (
		<>
			<div ref={scroller} class={styles.scroller} role="listbox" aria-label="Lore catalog entries">
				<div class={styles.rows} style={{ height: `${virtualizer.getTotalSize()}px` }}>
					<For each={virtualizer.getVirtualItems()}>
						{(item) => {
							const entry = () => props.feed.entries()[item.index];
							return (
								<Show when={entry()}>
									{(current) => (
									<button
										type="button"
										role="option"
										aria-selected={props.selectedId === current().id}
											class={cx(styles.row, props.selectedId === current().id && styles.rowSelected)}
											style={{ height: `${item.size}px`, transform: `translateY(${item.start}px)` }}
											onClick={() => props.onSelect(current())}
											onKeyDown={(event) => selectWithKeyboard(event, current())}
										>
											<span class={styles.rowTitle}>
												<Show when={current().approved}>
													<span class={cx(styles.badge, styles.badgeApproved)}>ok</span>
												</Show>
												<Show when={current().has_override}>
													<span class={cx(styles.badge, styles.badgeOverride)}>override</span>
												</Show>
												<Show when={(current().issues ?? []).length > 0}>
													<span class={cx(styles.badge, styles.badgeIssue)}>issue</span>
												</Show>
												{entryTitle(current())}
											</span>
											<span class={styles.rowMeta}>{current().type_path} · {statusLabel(current())}</span>
											<Show when={(current().group_labels ?? []).length > 0}><span class={styles.rowMeta}>{(current().group_labels ?? []).join(' · ')}</span></Show>
									</button>
									)}
								</Show>
							);
						}}
					</For>
				</div>
			</div>

			<div class={styles.footer} role="status" aria-live="polite" aria-atomic="true">
				<span>
					Showing {props.feed.entries().length.toLocaleString()} of{' '}
					{props.feed.matchedCount().toLocaleString()} matching
					<Show when={props.feed.loading()}> · loading…</Show>
					<Show when={props.feed.isExhausted() && props.feed.entries().length > 0}> · all loaded</Show>
				</span>
				<Show when={!props.feed.isExhausted()}>
					<button type="button" aria-label={`Load ${PAGE_SIZE} more`} disabled={props.feed.loading()} onClick={() => props.feed.loadMore()}>
						Load more
					</button>
				</Show>
			</div>
		</>
	);
}

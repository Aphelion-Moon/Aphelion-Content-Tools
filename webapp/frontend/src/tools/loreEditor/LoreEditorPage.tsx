import { For, Show, createSignal } from 'solid-js';
import Card, { cardStyles } from '~/components/Card';
import { announceError } from '~/lib/notify';
import { DEFAULT_FILTERS, createReviewFeed, type ReviewEntry } from './reviewFeed';
import ReviewList from './ReviewList';
import styles from './LoreEditor.module.css';

const SORTS = [
	{ value: 'name', label: 'Name' },
	{ value: 'type_path', label: 'Type path' },
	{ value: 'status', label: 'Status' },
	{ value: 'reviewed_at', label: 'Recently reviewed' },
];

const STATUSES = [
	{ value: '', label: 'Any status' },
	{ value: 'unreviewed', label: 'Unreviewed' },
	{ value: 'approved', label: 'Approved' },
	{ value: 'needs_work', label: 'Needs work' },
];

export default function LoreEditorPage() {
	const feed = createReviewFeed();
	const [selected, setSelected] = createSignal<ReviewEntry | null>(null);

	// Surface load failures through Parsec as well as inline, matching the app-wide convention.
	const reportIfFailed = () => {
		const message = feed.error();
		if (message) announceError(new Error(message), 'lore-editor');
		return message;
	};

	const update = (patch: Partial<typeof DEFAULT_FILTERS>) => feed.setFilters({ ...feed.filters(), ...patch });

	return (
		<>
			<Card eyebrow="Catalog" heading="Review">
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

					<label class={styles.field}>
						<span>Status</span>
						<select value={feed.filters().status} onChange={(event) => update({ status: event.currentTarget.value })}>
							<For each={STATUSES}>{(option) => <option value={option.value}>{option.label}</option>}</For>
						</select>
					</label>

					<label class={styles.field}>
						<span>Group</span>
						<select value={feed.filters().group} onChange={(event) => update({ group: event.currentTarget.value })}>
							<option value="">Any group</option>
							<For each={feed.meta()?.groups ?? []}>
								{(group) => <option value={group.id}>{group.label}</option>}
							</For>
						</select>
					</label>

					<label class={styles.field}>
						<span>Sort</span>
						<select value={feed.filters().sort} onChange={(event) => update({ sort: event.currentTarget.value })}>
							<For each={SORTS}>{(option) => <option value={option.value}>{option.label}</option>}</For>
						</select>
					</label>
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

				<Show when={reportIfFailed()}>
					{(message) => <p class={cardStyles.metadata}>{message()}</p>}
				</Show>

				<ReviewList feed={feed} selectedId={selected()?.id ?? null} onSelect={setSelected} />
			</Card>

			<Show when={selected()}>
				{(entry) => (
					<Card eyebrow="Selected entry" heading={entry().name || entry().base_name || entry().label || 'Entry'}>
						<div class={styles.detail}>
							<DetailRow label="Type path" value={entry().type_path} />
							<DetailRow label="Category" value={entry().category} />
							<DetailRow label="Status" value={entry().status} />
							<DetailRow label="Description" value={entry().description ?? entry().base_description} />
							<DetailRow label="Groups" value={entry().group_labels.join(', ') || null} />
							<DetailRow label="Has override" value={entry().has_override ? 'yes' : 'no'} />
						</div>
					</Card>
				)}
			</Show>
		</>
	);
}

function DetailRow(props: { readonly label: string; readonly value: string | null | undefined }) {
	return (
		<Show when={props.value}>
			{(value) => (
				<div class={styles.detailRow}>
					<span class={styles.detailLabel}>{props.label}</span>
					<span class={styles.detailValue}>{value()}</span>
				</div>
			)}
		</Show>
	);
}

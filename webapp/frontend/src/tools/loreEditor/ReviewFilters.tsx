import { For, Show } from 'solid-js';
import { DEFAULT_FILTERS, type ReviewFilters as ReviewFilterState, type createReviewFeed } from './reviewFeed';
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

export default function ReviewFilters(props: {
	readonly feed: ReturnType<typeof createReviewFeed>;
}) {
	const update = (patch: Partial<ReviewFilterState>) =>
		props.feed.setFilters({ ...props.feed.filters(), ...patch });
	const toggleValue = (values: readonly string[], value: string, checked: boolean) =>
		checked ? [...new Set([...values, value])] : values.filter((current) => current !== value);

	return (
		<>
			<div class={styles.filters}>
				<label class={styles.field}>
					<span>Search</span>
					<input
						type="search"
						placeholder="Name, type path, description…"
						value={props.feed.filters().query}
						onInput={(event) => update({ query: event.currentTarget.value })}
					/>
				</label>

				<details class={styles.filterDisclosure}>
					<summary>Status {props.feed.filters().statuses.length ? `(${props.feed.filters().statuses.length})` : '(any)'}</summary>
					<fieldset class={styles.filterChecks}>
						<legend class="sr-only">Review status</legend>
						<For each={STATUSES}>{(option) => (
							<label>
								<input
									type="checkbox"
									checked={props.feed.filters().statuses.includes(option.value)}
									onChange={(event) => update({
										statuses: toggleValue(props.feed.filters().statuses, option.value, event.currentTarget.checked),
									})}
								/>
								{option.label}
							</label>
						)}</For>
					</fieldset>
				</details>

				<details class={styles.filterDisclosure}>
					<summary>Groups {props.feed.filters().groups.length ? `(${props.feed.filters().groups.length})` : '(any)'}</summary>
					<fieldset class={styles.filterChecks}>
						<legend class="sr-only">Lore groups</legend>
						<div class={styles.filterButtons}>
							<button type="button" onClick={() => update({ groups: (props.feed.meta()?.groups ?? []).map((group) => group.id) })}>Select all</button>
							<button type="button" onClick={() => update({ groups: [] })}>Clear groups</button>
						</div>
						<div class={styles.filterCheckList}>
							<For each={props.feed.meta()?.groups ?? []}>{(group) => (
								<label>
									<input
										type="checkbox"
										checked={props.feed.filters().groups.includes(group.id)}
										onChange={(event) => update({
											groups: toggleValue(props.feed.filters().groups, group.id, event.currentTarget.checked),
										})}
									/>
									{group.label}
								</label>
							)}</For>
						</div>
					</fieldset>
				</details>

				<label class={styles.field}>
					<span>Sort</span>
					<select value={props.feed.filters().sort} onChange={(event) => update({ sort: event.currentTarget.value })}>
						<For each={SORTS}>{(option) => <option value={option.value}>{option.label}</option>}</For>
					</select>
				</label>
				<button type="button" class={styles.clearFilters} onClick={() => props.feed.setFilters(DEFAULT_FILTERS)}>Clear all filters</button>
			</div>

			<details class={styles.filterDisclosure}>
				<summary>Visibility</summary>
				<div class={styles.toggles}>
					<label class={styles.toggle}>
						<input
							type="checkbox"
							checked={props.feed.filters().includeDirectional}
							onChange={(event) => update({ includeDirectional: event.currentTarget.checked })}
						/>
						Include directional
						<Show when={props.feed.meta()?.suppressed_counts['directional']}>
							{(count) => <> ({count().toLocaleString()})</>}
						</Show>
					</label>
					<label class={styles.toggle}>
						<input
							type="checkbox"
							checked={props.feed.filters().includeRedundant}
							onChange={(event) => update({ includeRedundant: event.currentTarget.checked })}
						/>
						Include redundant
						<Show when={props.feed.meta()?.suppressed_counts['redundant']}>
							{(count) => <> ({count().toLocaleString()})</>}
						</Show>
					</label>
				</div>
			</details>

			<Show when={props.feed.meta()}>
				{(meta) => (
					<p class={styles.counts}>
						{meta().catalog_count.toLocaleString()} catalog targets ·{' '}
						{meta().approved_count.toLocaleString()} approved ·{' '}
						{meta().matched_entry_count.toLocaleString()} match the current filters
					</p>
				)}
			</Show>
		</>
	);
}

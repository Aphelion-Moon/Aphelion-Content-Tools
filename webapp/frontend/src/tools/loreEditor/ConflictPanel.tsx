import { Show } from 'solid-js';
import { ApiError } from '~/lib/api';
import styles from './LoreEditor.module.css';

export interface RecordConflictDetails {
	record_id: string;
	expected_hash: string | null;
	current_hash: string | null;
	base: unknown;
	current: unknown;
	proposed: unknown;
}

export function recordConflictFrom(error: unknown): RecordConflictDetails | null {
	if (!(error instanceof ApiError) || error.code !== 'record_conflict') return null;
	const details = error.details;
	if (typeof details['record_id'] !== 'string') return null;
	return {
		record_id: details['record_id'],
		expected_hash: typeof details['expected_hash'] === 'string' ? details['expected_hash'] : null,
		current_hash: typeof details['current_hash'] === 'string' ? details['current_hash'] : null,
		base: details['base'],
		current: details['current'],
		proposed: details['proposed'],
	};
}

function RecordColumn(props: { readonly title: string; readonly value: unknown }) {
	return (
		<section class={styles.conflictColumn}>
			<h4>{props.title}</h4>
			<pre>{props.value == null ? '(record did not exist)' : JSON.stringify(props.value, null, 2)}</pre>
		</section>
	);
}

export default function ConflictPanel(props: {
	readonly conflict: RecordConflictDetails | null;
	readonly onKeepEditing: () => void;
	readonly onReloadCurrent: () => void;
}) {
	return (
		<Show when={props.conflict}>
			{(conflict) => (
				<div class={styles.conflictPanel} role="alertdialog" aria-modal="true" aria-labelledby="record-conflict-title">
					<h3
						id="record-conflict-title"
						tabIndex={-1}
						ref={(heading) => queueMicrotask(() => heading.focus())}
					>
						This record changed in another writer's branch or tab
					</h3>
					<p>
						Nothing was overwritten. Compare the current Git record with your proposed edit, then reload or keep
						your draft while you copy the parts you need.
					</p>
					<div class={styles.conflictGrid}>
						<RecordColumn title="Base when loaded" value={conflict().base} />
						<RecordColumn title="Current record" value={conflict().current} />
						<RecordColumn title="Your proposed record" value={conflict().proposed} />
					</div>
					<div class={styles.actions}>
						<button type="button" onClick={props.onReloadCurrent}>Reload current record</button>
						<button type="button" class={styles.secondary} onClick={props.onKeepEditing}>Keep editing my draft</button>
					</div>
				</div>
			)}
		</Show>
	);
}

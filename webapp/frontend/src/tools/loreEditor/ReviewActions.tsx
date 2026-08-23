import { For, Show, createEffect, createMemo, createResource, createSignal, onCleanup } from 'solid-js';
import { api } from '~/lib/api';
import type { components } from '~/lib/api-schema';
import { announceError, announceSuccess } from '~/lib/notify';
import ConflictPanel, { recordConflictFrom, type RecordConflictDetails } from './ConflictPanel';
import type { ReviewEntry } from './reviewFeed';
import styles from './LoreEditor.module.css';

type GroupsResponse = components['schemas']['GroupsResponse'];
type ReviewWriteResponse = components['schemas']['ReviewWriteResponse'];
type AssignmentWriteResponse = components['schemas']['AssignmentWriteResponse'];

export default function ReviewActions(props: {
	readonly entry: ReviewEntry;
	readonly onDirtyChange: (dirty: boolean) => void;
	readonly onReload: (typePath: string) => void;
}) {
	const [groups, { refetch }] = createResource(() => api.get<GroupsResponse>('/api/groups'));
	const [reviewer, setReviewer] = createSignal(props.entry.review?.reviewed_by ?? '');
	const [notes, setNotes] = createSignal(props.entry.review?.notes ?? '');
	const [saving, setSaving] = createSignal(false);
	const [message, setMessage] = createSignal('');
	const [conflict, setConflict] = createSignal<RecordConflictDetails | null>(null);
	const baselineReviewer = props.entry.review?.reviewed_by ?? '';
	const baselineNotes = props.entry.review?.notes ?? '';
	const dirty = createMemo(() => reviewer() !== baselineReviewer || notes() !== baselineNotes);

	createEffect(() => props.onDirtyChange(dirty()));
	onCleanup(() => props.onDirtyChange(false));

	const manuallyAssigned = () => new Set(groups()?.assignments[props.entry.type_path] ?? []);

	async function saveReview(status: 'reviewed' | 'needs-attention' | null): Promise<void> {
		if (status && !reviewer().trim()) {
			setMessage('Enter a reviewer name before saving a review decision.');
			return;
		}
		setSaving(true);
		try {
			await api.put<ReviewWriteResponse>(`/api/reviews/${encodeURIComponent(props.entry.type_path)}`, {
				status,
				reviewed_by: reviewer().trim(),
				notes: notes().trim(),
				expected_record_hash: props.entry.review?.record_hash ?? null,
			});
			setMessage(status ? 'Review decision saved.' : 'Review decision cleared.');
			announceSuccess(status ? 'Review decision saved.' : 'Review decision cleared.', 'lore-editor');
			props.onDirtyChange(false);
			props.onReload(props.entry.type_path);
		} catch (error) {
			const details = recordConflictFrom(error);
			if (details) setConflict({ ...details, base: details.base ?? props.entry.review });
			else {
				setMessage(error instanceof Error ? error.message : String(error));
				announceError(error, 'lore-editor');
			}
		} finally {
			setSaving(false);
		}
	}

	async function toggleAssignment(groupId: string, checked: boolean): Promise<void> {
		const response = groups();
		if (!response) return;
		const next = new Set(response.assignments[props.entry.type_path] ?? []);
		if (checked) next.add(groupId);
		else next.delete(groupId);
		setSaving(true);
		try {
			await api.put<AssignmentWriteResponse>(
				`/api/group-assignments/${encodeURIComponent(props.entry.type_path)}`,
				{
					group_ids: [...next].sort(),
					expected_record_hash: response.assignment_record_hashes[props.entry.type_path] ?? null,
				},
			);
			await refetch();
			setMessage('Manual group assignment saved.');
			announceSuccess('Manual group assignment saved.', 'lore-editor');
			props.onReload(props.entry.type_path);
		} catch (error) {
			const details = recordConflictFrom(error);
			if (details) {
				setConflict({
					...details,
					base: details.base ?? {
						type_path: props.entry.type_path,
						group_ids: response.assignments[props.entry.type_path] ?? [],
					},
				});
			}
			else {
				setMessage(error instanceof Error ? error.message : String(error));
				announceError(error, 'lore-editor');
			}
		} finally {
			setSaving(false);
		}
	}

	return (
		<section class={styles.reviewActions} aria-labelledby="review-actions-heading">
			<h3 id="review-actions-heading">Review and grouping</h3>
			<div class={styles.formGrid}>
				<label class={styles.field}>
					<span>Reviewer</span>
					<input value={reviewer()} onInput={(event) => setReviewer(event.currentTarget.value)} />
				</label>
				<label class={styles.field}>
					<span>Review notes</span>
					<textarea rows={3} value={notes()} onInput={(event) => setNotes(event.currentTarget.value)} />
				</label>
			</div>
			<div class={styles.actions}>
				<button type="button" disabled={saving()} onClick={() => void saveReview('reviewed')}>Mark reviewed</button>
				<button type="button" disabled={saving()} onClick={() => void saveReview('needs-attention')}>Needs attention</button>
				<button type="button" class={styles.secondary} disabled={saving()} onClick={() => void saveReview(null)}>Clear review</button>
			</div>

			<fieldset class={styles.assignmentList} disabled={saving() || groups.loading}>
				<legend>Manual group assignments</legend>
				<p class={styles.help}>These supplement keyword and type-path matches; they do not replace automatic grouping.</p>
				<For each={groups()?.groups ?? []}>
					{(group) => (
						<label>
							<input
								type="checkbox"
								checked={manuallyAssigned().has(group.id)}
								onChange={(event) => void toggleAssignment(group.id, event.currentTarget.checked)}
							/>
							<span class={styles.groupSwatch} style={{ background: group.color ?? '#9614d0' }} />
							{group.label}
						</label>
					)}
				</For>
			</fieldset>
			<Show when={message()}>{(text) => <p class={styles.operationStatus} role="status">{text()}</p>}</Show>
			<ConflictPanel
				conflict={conflict()}
				onKeepEditing={() => setConflict(null)}
				onReloadCurrent={() => {
					setConflict(null);
					props.onReload(props.entry.type_path);
				}}
			/>
		</section>
	);
}

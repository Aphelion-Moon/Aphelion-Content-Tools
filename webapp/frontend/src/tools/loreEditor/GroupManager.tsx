import { For, Show, createResource, createSignal } from 'solid-js';
import { createStore } from 'solid-js/store';
import { api } from '~/lib/api';
import type { components } from '~/lib/api-schema';
import { announceError, announceSuccess } from '~/lib/notify';
import ConflictPanel, { recordConflictFrom, type RecordConflictDetails } from './ConflictPanel';
import styles from './LoreEditor.module.css';

type Group = components['schemas']['ReviewGroupModel'];
type GroupsResponse = components['schemas']['GroupsResponse'];
type GroupWriteResponse = components['schemas']['GroupWriteResponse'];
type DeleteGroupResponse = components['schemas']['DeleteGroupResponse'];

const SCOPE_FIELDS = [
	['name', 'Name'],
	['description', 'Description'],
	['label', 'Label'],
	['type_path', 'Type path'],
	['parent_type', 'Parent type'],
] as const;

function emptyDraft() {
	return {
		id: '',
		label: '',
		color: '#9614d0',
		keywords: '',
		typePathPrefixes: '',
		keywordScope: ['name', 'description', 'label'] as string[],
		recordHash: null as string | null,
	};
}

export default function GroupManager() {
	const [groups, { refetch }] = createResource(() => api.get<GroupsResponse>('/api/groups'));
	const [draft, setDraft] = createStore(emptyDraft());
	const [editing, setEditing] = createSignal(false);
	const [saving, setSaving] = createSignal(false);
	const [message, setMessage] = createSignal('');
	const [conflict, setConflict] = createSignal<RecordConflictDetails | null>(null);

	function startNew(): void {
		setDraft(emptyDraft());
		setEditing(true);
	}

	function edit(group: Group): void {
		setDraft({
			id: group.id,
			label: group.label,
			color: group.color ?? '#9614d0',
			keywords: (group.keywords ?? []).join(', '),
			typePathPrefixes: (group.type_path_prefixes ?? []).join(', '),
			keywordScope: [...(group.keyword_scope ?? [])],
			recordHash: group.record_hash ?? null,
		});
		setEditing(true);
	}

	function commaSeparated(value: string): string[] {
		return [...new Set(value.split(',').map((item) => item.trim()).filter(Boolean))];
	}

	async function save(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		setSaving(true);
		try {
			const payload = {
				id: draft.id.trim(),
				label: draft.label.trim(),
				color: draft.color,
				keywords: commaSeparated(draft.keywords),
				type_path_prefixes: commaSeparated(draft.typePathPrefixes),
				keyword_scope: draft.keywordScope,
				assignments: [],
			};
			if (draft.recordHash) {
				await api.put<GroupWriteResponse>(`/api/groups/${encodeURIComponent(draft.id)}`, {
					...payload,
					expected_record_hash: draft.recordHash,
				});
			} else {
				await api.post<GroupWriteResponse>('/api/groups', payload);
			}
			await refetch();
			setEditing(false);
			setMessage('Group configuration saved.');
			announceSuccess('Group configuration saved.', 'lore-editor');
		} catch (error) {
			const details = recordConflictFrom(error);
			if (details) setConflict({ ...details, base: details.base ?? {
				id: draft.id,
				label: draft.label,
				color: draft.color,
				keywords: commaSeparated(draft.keywords),
				type_path_prefixes: commaSeparated(draft.typePathPrefixes),
				keyword_scope: draft.keywordScope,
			} });
			else {
				setMessage(error instanceof Error ? error.message : String(error));
				announceError(error, 'lore-editor');
			}
		} finally {
			setSaving(false);
		}
	}

	async function remove(): Promise<void> {
		if (!draft.recordHash || !window.confirm(`Delete the group "${draft.label}"? Manual assignments to it will also be removed.`)) return;
		setSaving(true);
		try {
			const response = await api.delete<DeleteGroupResponse>(`/api/groups/${encodeURIComponent(draft.id)}`, {
				expected_record_hash: draft.recordHash,
			});
			await refetch();
			setEditing(false);
			setMessage(`Group deleted; ${response.updated_assignments} manual assignment record(s) updated.`);
			announceSuccess('Group deleted.', 'lore-editor');
		} catch (error) {
			const details = recordConflictFrom(error);
			if (details) setConflict({ ...details, base: details.base ?? {
				id: draft.id,
				label: draft.label,
				color: draft.color,
				keywords: commaSeparated(draft.keywords),
				type_path_prefixes: commaSeparated(draft.typePathPrefixes),
				keyword_scope: draft.keywordScope,
			} });
			else announceError(error, 'lore-editor');
		} finally {
			setSaving(false);
		}
	}

	return (
		<section aria-labelledby="group-manager-heading">
			<div class={styles.editorHeading}>
				<div><h3 id="group-manager-heading">Writer-maintained groups</h3><p class={styles.help}>Groups combine explicit assignments, type-path prefixes, and scoped keyword rules.</p></div>
				<button type="button" onClick={startNew}>New group</button>
			</div>
			<div class={styles.groupCards}>
				<For each={groups()?.groups ?? []}>
					{(group) => (
						<article class={styles.groupCard}>
							<div><span class={styles.groupSwatch} style={{ background: group.color ?? '#9614d0' }} /><strong>{group.label}</strong></div>
							<p class={styles.help}>{group.id} · {group.count.toLocaleString()} matches</p>
							<p>Keywords: {(group.keywords ?? []).join(', ') || 'none'}</p>
							<p>Type paths: {(group.type_path_prefixes ?? []).join(', ') || 'none'}</p>
							<button type="button" class={styles.secondary} onClick={() => edit(group)}>Edit</button>
						</article>
					)}
				</For>
			</div>

			<Show when={editing()}>
				<form class={styles.groupForm} onSubmit={(event) => void save(event)}>
					<h3>{draft.recordHash ? `Edit ${draft.label}` : 'New group'}</h3>
					<label class={styles.field}><span>Group ID</span><input required disabled={Boolean(draft.recordHash)} pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value={draft.id} onInput={(event) => setDraft('id', event.currentTarget.value)} /></label>
					<label class={styles.field}><span>Group name</span><input required value={draft.label} onInput={(event) => setDraft('label', event.currentTarget.value)} /></label>
					<label class={styles.field}><span>Color</span><input type="color" value={draft.color} onInput={(event) => setDraft('color', event.currentTarget.value)} /></label>
					<label class={styles.field}><span>Keywords, comma-separated</span><input value={draft.keywords} onInput={(event) => setDraft('keywords', event.currentTarget.value)} /></label>
					<fieldset><legend>Keyword search scope</legend><For each={SCOPE_FIELDS}>{(scope) => <label class={styles.checkbox}><input type="checkbox" checked={draft.keywordScope.includes(scope[0])} onChange={(event) => setDraft('keywordScope', (current) => event.currentTarget.checked ? [...current, scope[0]] : current.filter((field) => field !== scope[0]))} /> {scope[1]}</label>}</For></fieldset>
					<label class={styles.field}><span>Type-path prefixes, comma-separated</span><input value={draft.typePathPrefixes} onInput={(event) => setDraft('typePathPrefixes', event.currentTarget.value)} /></label>
					<div class={styles.actions}><button type="submit" disabled={saving()}>{saving() ? 'Saving…' : 'Save group'}</button><Show when={draft.recordHash}><button type="button" class={styles.danger} disabled={saving()} onClick={() => void remove()}>Delete group</button></Show><button type="button" class={styles.secondary} onClick={() => setEditing(false)}>Cancel</button></div>
				</form>
			</Show>
			<Show when={message()}>{(text) => <p class={styles.operationStatus} role="status">{text()}</p>}</Show>
			<ConflictPanel conflict={conflict()} onKeepEditing={() => setConflict(null)} onReloadCurrent={() => { setConflict(null); setEditing(false); void refetch(); }} />
		</section>
	);
}

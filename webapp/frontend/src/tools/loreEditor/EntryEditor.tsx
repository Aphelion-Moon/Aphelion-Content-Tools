import { For, Show, createEffect, createMemo, createResource, createSignal, onCleanup, onMount } from 'solid-js';
import { createStore } from 'solid-js/store';
import OpenFileActions from '~/components/OpenFileActions';
import { api } from '~/lib/api';
import type { components } from '~/lib/api-schema';
import { addReference } from '~/lib/references';
import { reportParsec } from '~/lib/parsec/coordinator';
import ConflictPanel, { recordConflictFrom, type RecordConflictDetails } from './ConflictPanel';
import { buildEntryPayload, draftFromEntry, type IconSlot } from './entryDraft';
import type { ReviewEntry } from './reviewFeed';
import styles from './LoreEditor.module.css';

type DefinitionResponse = components['schemas']['DefinitionResponse'];
type EntityFilesResponse = components['schemas']['EntityFilesResponse'];
type IconFilesResponse = components['schemas']['IconFilesResponse'];
type IconStatesResponse = components['schemas']['IconStatesResponse'];
type ValidationResponse = components['schemas']['ValidationResponse'];
type SaveEntryResponse = components['schemas']['SaveEntryResponse'];
type DeleteEntryResponse = components['schemas']['DeleteEntryResponse'];

const SPECIAL_REQUIREMENTS = [
	['', 'Inherit current requirement'],
	['none', 'Always show'],
	['syndicate', 'Syndicate affiliation'],
	['syndicate_toy', 'Syndicate toy behavior'],
	['mindshield', 'Mindshield'],
	['role', 'Specific role'],
	['job', 'Specific job'],
	['faction', 'Specific faction'],
	['contractor', 'Contractor or syndicate agent'],
] as const;

const ICON_SLOTS: ReadonlyArray<{ value: IconSlot; label: string }> = [
	{ value: 'icon', label: 'Main icon' },
	{ value: 'worn_icon', label: 'Worn icon' },
	{ value: 'inhand_icon', label: 'In-hand icon' },
];

const STATUS_LABELS: Readonly<Record<string, string>> = {
	unreviewed: 'Unreviewed',
	reviewed: 'Reviewed',
	overridden: 'Overridden',
	'needs-attention': 'Needs attention',
};

function previewUrl(file: string, state: string): string {
	return `/api/icon?file=${encodeURIComponent(file)}&state=${encodeURIComponent(state)}`;
}

function sourceFileFor(group: string): string {
	return `tools/lore_editor/content/overrides/${group}.json`;
}

function baseIcon(entry: ReviewEntry, slot: IconSlot): { file: string; state: string } | null {
	const value = (entry.icon_metadata ?? {})[slot];
	if (!value || typeof value !== 'object') return null;
	const record = value as Record<string, unknown>;
	return typeof record['file'] === 'string' && typeof record['state'] === 'string'
		? { file: record['file'], state: record['state'] }
		: null;
}

export default function EntryEditor(props: {
	readonly entry: ReviewEntry;
	readonly onDirtyChange: (dirty: boolean) => void;
	readonly onReload: (typePath: string) => void;
}) {
	const initial = draftFromEntry(props.entry);
	const [draft, setDraft] = createStore(initial);
	const [editing, setEditing] = createSignal(props.entry.has_override);
	const [iconSlot, setIconSlot] = createSignal<IconSlot>('icon');
	const [iconStates, setIconStates] = createSignal<readonly string[]>([]);
	const [sourceFile, setSourceFile] = createSignal(props.entry.source_file ?? '');
	const [newGroup, setNewGroup] = createSignal('');
	const [saving, setSaving] = createSignal(false);
	const [issues, setIssues] = createSignal<readonly components['schemas']['ValidationIssueModel'][]>(props.entry.issues ?? []);
	const [message, setMessage] = createSignal('');
	const [conflict, setConflict] = createSignal<RecordConflictDetails | null>(null);
	const [definition] = createResource(() => api.get<DefinitionResponse>(
		`/api/lore/definition?type_path=${encodeURIComponent(props.entry.type_path)}`,
	));
	const [entityFiles] = createResource(() => api.get<EntityFilesResponse>('/api/entity-files'));
	const [iconFiles] = createResource(() => api.get<IconFilesResponse>('/api/icon-files'));
	const baseline = JSON.stringify(buildEntryPayload(initial));
	const dirty = createMemo(() => editing() && (
		!props.entry.has_override
		|| JSON.stringify(buildEntryPayload(draft)) !== baseline
	));

	createEffect(() => props.onDirtyChange(dirty()));
	onCleanup(() => props.onDirtyChange(false));
	onMount(() => {
		const warn = (event: BeforeUnloadEvent) => {
			if (!dirty()) return;
			event.preventDefault();
		};
		window.addEventListener('beforeunload', warn);
		onCleanup(() => window.removeEventListener('beforeunload', warn));
	});

	createEffect(() => {
		const file = draft.icons[iconSlot()].file.trim();
		if (!file) {
			setIconStates([]);
			return;
		}
		const controller = new AbortController();
		void api.get<IconStatesResponse>(`/api/icon-states?file=${encodeURIComponent(file)}`, {
			signal: controller.signal,
		}).then((response) => setIconStates(response.states)).catch((error: unknown) => {
			if (!controller.signal.aborted) setMessage(error instanceof Error ? error.message : String(error));
		});
		onCleanup(() => controller.abort());
	});

	function selectedSourceFile(): string {
		if (props.entry.has_override && props.entry.source_file) return props.entry.source_file;
		const group = newGroup().trim();
		if (group) {
			if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(group)) {
				throw new Error('New override group must use lowercase letters, numbers, and hyphens.');
			}
			return sourceFileFor(group);
		}
		if (!sourceFile()) throw new Error('Choose an existing override group or enter a new group name.');
		return sourceFile();
	}

	async function validate(): Promise<{ source: string; payload: Record<string, unknown>; valid: boolean }> {
		const source = selectedSourceFile();
		const payload = buildEntryPayload(draft);
		const response = await api.post<ValidationResponse>('/api/validate', {
			entries: [payload],
			source_file: source,
		});
		setIssues(response.issues);
		return { source, payload, valid: response.valid };
	}

	async function save(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		setSaving(true);
		setMessage('');
		try {
			const candidate = await validate();
			if (!candidate.valid) {
				setMessage('Save cancelled until the validation issues below are fixed.');
				return;
			}
			if (props.entry.has_override && !props.entry.record_hash) {
				throw new Error('The loaded override has no record hash. Reload it before saving.');
			}
			const response = props.entry.has_override
				? await api.put<SaveEntryResponse>(`/api/entries/${encodeURIComponent(props.entry.id)}`, {
					source_file: candidate.source,
					entry: candidate.payload,
					expected_record_hash: props.entry.record_hash,
				})
				: await api.post<SaveEntryResponse>('/api/entries', {
					source_file: candidate.source,
					entry: candidate.payload,
				});
			setMessage(response.created ? 'Override created and generated.' : 'Override saved and generated.');
			reportParsec({ type: 'mutation', phase: 'completed', tool: 'lore-editor', summary: response.created ? 'Override created and generated.' : 'Override saved and generated.' });
			props.onDirtyChange(false);
			props.onReload(props.entry.type_path);
		} catch (error) {
			const details = recordConflictFrom(error);
			if (details) setConflict({ ...details, base: details.base ?? props.entry.raw });
			else {
				const message = error instanceof Error ? error.message : String(error);
				setMessage(message);
				reportParsec({ type: 'mutation', phase: 'failed', tool: 'lore-editor', summary: 'Could not save the lore override.', technicalDetail: message });
			}
		} finally {
			setSaving(false);
		}
	}

	async function removeOverride(): Promise<void> {
		if (!props.entry.source_file || !props.entry.record_hash) return;
		const label = props.entry.name ?? props.entry.base_name ?? props.entry.type_path;
		if (!window.confirm(`Remove the override for "${label}"? It will revert to the catalog definition.`)) return;
		setSaving(true);
		try {
			await api.delete<DeleteEntryResponse>(`/api/entries/${encodeURIComponent(props.entry.id)}`, {
				source_file: props.entry.source_file,
				expected_record_hash: props.entry.record_hash,
			});
			reportParsec({ type: 'mutation', phase: 'completed', tool: 'lore-editor', summary: 'Override removed and generated.' });
			props.onDirtyChange(false);
			props.onReload(props.entry.type_path);
		} catch (error) {
			const details = recordConflictFrom(error);
			if (details) setConflict({ ...details, base: details.base ?? props.entry.raw });
			else {
				const message = error instanceof Error ? error.message : String(error);
				reportParsec({ type: 'mutation', phase: 'failed', tool: 'lore-editor', summary: 'Could not remove the lore override.', technicalDetail: message });
			}
		} finally {
			setSaving(false);
		}
	}

	async function pinReference(): Promise<void> {
		try {
			await addReference({
				tool: 'lore-editor',
				kind: 'catalog_target',
				key: props.entry.type_path,
				label: props.entry.name ?? props.entry.base_name ?? props.entry.label ?? props.entry.type_path,
			});
			setMessage('Added to shared references.');
			reportParsec({ type: 'mutation', phase: 'completed', tool: 'lore-editor', summary: 'Added to shared references.' });
		} catch (error) {
			const message = error instanceof Error ? error.message : String(error);
			setMessage(message);
			reportParsec({ type: 'mutation', phase: 'failed', tool: 'lore-editor', summary: 'Could not add the lore entry to shared references.', technicalDetail: message });
		}
	}

	const currentBaseIcon = () => baseIcon(props.entry, iconSlot());
	const currentOverrideIcon = () => draft.icons[iconSlot()];
	const currentIconStateAvailable = () => !currentOverrideIcon().state || iconStates().includes(currentOverrideIcon().state);

	return (
		<section class={styles.entryEditor} aria-labelledby="entry-editor-heading">
			<div class={styles.editorHeading}>
				<div>
					<h3 id="entry-editor-heading">{props.entry.name ?? props.entry.base_name ?? props.entry.label ?? props.entry.type_path}</h3>
					<p class={styles.help}>{props.entry.type_path} · {props.entry.field_profile ?? 'unknown profile'} · {STATUS_LABELS[props.entry.status] ?? props.entry.status}</p>
				</div>
				<button type="button" class={styles.secondary} onClick={() => void pinReference()}>Add to references</button>
			</div>
			<div class={styles.openActions}>
				<Show when={definition()?.path}>{(path) => <OpenFileActions label="Original" repository="game" path={path()} line={definition()?.line} />}</Show>
				<Show when={props.entry.has_override}>
					<OpenFileActions
						label="Override"
						repository="tool"
						path={`tools/lore_editor/content/overrides/${props.entry.id}.json`}
					/>
				</Show>
			</div>
			<details class={styles.advancedDetails}>
				<summary>Advanced details</summary>
				<dl>
					<div><dt>Record ID</dt><dd><code>{props.entry.id}</code></dd></div>
					<div><dt>Source group</dt><dd>{props.entry.source_file ?? 'Catalog only'}</dd></div>
					<div><dt>Groups</dt><dd>{(props.entry.group_labels ?? []).join(', ') || 'None'}</dd></div>
					<For each={Object.entries(props.entry.group_match_reasons ?? {})}>{([group, reasons]) => <div><dt>{group} match</dt><dd>{reasons.join(', ')}</dd></div>}</For>
					<Show when={(props.entry.suppression_reasons ?? []).length > 0}><div><dt>Visible by toggle</dt><dd>{(props.entry.suppression_reasons ?? []).join(', ')}</dd></div></Show>
				</dl>
			</details>

			<Show when={!editing()}>
				<div class={styles.actions}>
					<button type="button" onClick={() => setEditing(true)}>Create override</button>
				</div>
			</Show>

			<Show when={editing()}>
				<form class={styles.editorForm} onSubmit={(event) => void save(event)}>
					<div class={styles.previewGrid}>
						<section><h4>Base text</h4><strong>{props.entry.base_name ?? '(no base name)'}</strong><p>{props.entry.base_description ?? '(no base description)'}</p></section>
						<section><h4>Override preview</h4><strong>{draft.name || props.entry.base_name || '(unchanged)'}</strong><p>{draft.description || props.entry.base_description || '(unchanged)'}</p></section>
					</div>
					<label class={styles.field}><span>Name override</span><input value={draft.name} onInput={(event) => setDraft('name', event.currentTarget.value)} /></label>
					<label class={styles.field}><span>Description override</span><textarea rows={6} value={draft.description} onInput={(event) => setDraft('description', event.currentTarget.value)} /></label>
					<fieldset>
						<legend>Examine-more description</legend>
						<label class={styles.field}><span>Requirement</span><select value={draft.special_desc_requirement} onChange={(event) => setDraft('special_desc_requirement', event.currentTarget.value)}><For each={SPECIAL_REQUIREMENTS}>{(option) => <option value={option[0]}>{option[1]}</option>}</For></select></label>
						<label class={styles.field}><span>Special description</span><textarea rows={4} value={draft.special_desc} onInput={(event) => setDraft('special_desc', event.currentTarget.value)} /></label>
					</fieldset>

					<Show when={props.entry.field_profile !== 'named_datum'}>
						<fieldset>
							<legend>Icon override</legend>
							<label class={styles.field}><span>Icon slot</span><select value={iconSlot()} onChange={(event) => setIconSlot(event.currentTarget.value as IconSlot)}><For each={ICON_SLOTS}>{(slot) => <option value={slot.value}>{slot.label}</option>}</For></select></label>
							<div class={styles.iconGrid}>
								<section><h4>Base asset</h4><Show when={currentBaseIcon()} fallback={<p class={styles.help}>No base icon reference.</p>}>{(icon) => <><code>{icon().file} · {icon().state}</code><img class={styles.iconPreview} src={previewUrl(icon().file, icon().state)} alt="Base icon preview" onError={() => setMessage('The base icon could not be previewed.')} /></>}</Show></section>
								<section><h4>Override asset</h4><label class={styles.field}><span>DMI file</span><input type="search" list="lore-icon-files" value={currentOverrideIcon().file} onInput={(event) => setDraft('icons', iconSlot(), 'file', event.currentTarget.value)} /></label><datalist id="lore-icon-files"><For each={iconFiles()?.files ?? []}>{(file) => <option value={file} />}</For></datalist><label class={styles.field}><span>Icon state</span><select value={currentIconStateAvailable() ? currentOverrideIcon().state : ''} disabled={!currentOverrideIcon().file} onChange={(event) => setDraft('icons', iconSlot(), 'state', event.currentTarget.value)}><option value="">Choose an icon state</option><For each={iconStates()}>{(state) => <option value={state}>{state}</option>}</For><Show when={!currentIconStateAvailable()}><option value={currentOverrideIcon().state} disabled>{currentOverrideIcon().state} (unavailable)</option></Show></select></label><Show when={!currentIconStateAvailable()}><p class={styles.help}>The saved icon state is unavailable. Choose a replacement before saving.</p></Show><Show when={Boolean(currentOverrideIcon().file && currentOverrideIcon().state && currentIconStateAvailable())}><img class={styles.iconPreview} src={previewUrl(currentOverrideIcon().file, currentOverrideIcon().state)} alt="Override icon preview" onError={() => setMessage('That override icon could not be previewed.')} /></Show></section>
							</div>
						</fieldset>
					</Show>

					<fieldset>
						<legend>AutoWiki</legend>
						<label class={styles.checkbox}><input type="checkbox" checked={draft.wiki.enabled} onChange={(event) => setDraft('wiki', 'enabled', event.currentTarget.checked)} /> Export this entry to AutoWiki</label>
						<Show when={draft.wiki.enabled}>
							<label class={styles.field}><span>Wiki slug</span><input pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value={draft.wiki.slug} onInput={(event) => setDraft('wiki', 'slug', event.currentTarget.value)} /></label>
							<label class={styles.field}><span>Wiki summary</span><textarea rows={3} value={draft.wiki.summary} onInput={(event) => setDraft('wiki', 'summary', event.currentTarget.value)} /></label>
							<label class={styles.checkbox}><input type="checkbox" checked={draft.wiki.export_icon} onChange={(event) => setDraft('wiki', 'export_icon', event.currentTarget.checked)} /> Export selected icon</label>
						</Show>
					</fieldset>

					<Show when={!props.entry.has_override}>
						<fieldset>
							<legend>Override group</legend>
							<label class={styles.field}><span>Existing group file</span><select value={sourceFile()} onChange={(event) => setSourceFile(event.currentTarget.value)}><option value="">Choose a group</option><For each={entityFiles()?.files ?? []}>{(file) => <option value={file}>{file.split('/').at(-1)?.replace(/\.json$/, '')}</option>}</For></select></label>
							<label class={styles.field}><span>Or new group name</span><input pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value={newGroup()} onInput={(event) => setNewGroup(event.currentTarget.value)} /></label>
						</fieldset>
					</Show>

					<Show when={issues().length > 0}>
						<section class={styles.validationPanel} role="alert"><h4>Validation issues</h4><ul><For each={issues()}>{(issue) => <li><code>{issue.path}</code>: {issue.message}</li>}</For></ul></section>
					</Show>
					<Show when={message()}>{(text) => <p class={styles.operationStatus} role="status">{text()}</p>}</Show>
					<div class={styles.actions}>
						<button type="submit" disabled={saving()}>{saving() ? 'Saving…' : 'Save and generate'}</button>
						<Show when={props.entry.has_override}><button type="button" class={styles.danger} disabled={saving()} onClick={() => void removeOverride()}>Remove override</button></Show>
						<Show when={!props.entry.has_override}><button type="button" class={styles.secondary} onClick={() => setEditing(false)}>Cancel draft</button></Show>
					</div>
				</form>
			</Show>

			<ConflictPanel conflict={conflict()} onKeepEditing={() => setConflict(null)} onReloadCurrent={() => { setConflict(null); props.onReload(props.entry.type_path); }} />
		</section>
	);
}

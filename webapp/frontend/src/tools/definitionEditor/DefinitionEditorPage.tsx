import { useBeforeLeave, useNavigate, useSearchParams } from '@solidjs/router';
import { For, Show, createEffect, createMemo, createSignal, on, onCleanup, onMount } from 'solid-js';
import { api } from '~/lib/api';
import LoadingIndicator from '~/components/LoadingIndicator';
import type { components } from '~/lib/api-schema';
import { reportParsec } from '~/lib/parsec/coordinator';
import { addReference } from '~/lib/references';
import { appState, setDefinitionRuns, setSelectedContext } from '~/store/appStore';
import FieldEditor from './Fields';
import ItemInspector from './ItemInspector';
import PickerDialog from './PickerDialog';
import TypePicker from './TypePicker';
import { createDraft, formatContents, groupFor, makeStationBundle, modularOwners, parseContents, renameDraftType, setExpression, title } from './draft';
import type { CatalogStatus, Definition, DefinitionDraft, DefinitionEdit, EditorKind, EditorRun, EditorStage, SavedDraft } from './types';
import styles from './DefinitionEditor.module.css';

type Reference = components['schemas']['DefinitionReference'];

export default function DefinitionEditorPage(props: { kind: EditorKind }) {
	const [parameters] = useSearchParams();
	const navigate = useNavigate();
	const [status, setStatus] = createSignal<CatalogStatus>();
	const [drafts, setDrafts] = createSignal<SavedDraft[]>([]);
	const [base, setBase] = createSignal<Definition>();
	const [baseCatalogId, setBaseCatalogId] = createSignal('');
	const [draft, setDraft] = createSignal<DefinitionDraft>();
	const [recordHash, setRecordHash] = createSignal<string | null>(null);
	const [dirty, setDirty] = createSignal(false);
	const [editIndex, setEditIndex] = createSignal(0);
	const [message, setMessage] = createSignal('');
	const [error, setError] = createSignal('');
	const [busy, setBusy] = createSignal(false);
	const [stage, setStage] = createSignal<EditorStage>();
	const [receipt, setReceipt] = createSignal<components['schemas']['GameChangeReceipt']>();
	const [picker, setPicker] = createSignal<string>();
	const [references, setReferences] = createSignal<Reference[]>([]);
	const [species, setSpecies] = createSignal('/datum/species/human');
	const [bodyGender, setBodyGender] = createSignal('');
	const [bodyType, setBodyType] = createSignal('');
	const [procedure, setProcedure] = createSignal('pre_equip');
	const [previewPath, setPreviewPath] = createSignal('');
	const [previewSlot, setPreviewSlot] = createSignal<string>();
	const [runLog, setRunLog] = createSignal('');
	const [source, setSource] = createSignal<components['schemas']['SourceExcerpt']>();
	const [rebase, setRebase] = createSignal<components['schemas']['RebaseProposal']>();
	const [constantField, setConstantField] = createSignal<string>();
	const [constantQuery, setConstantQuery] = createSignal('');
	const [constants, setConstants] = createSignal<components['schemas']['DefinitionConstant'][]>([]);
	const edit = () => draft()?.edits[editIndex()];
	const tool = () => `${props.kind}-editor`;
	let disposed = false;
	let inspectRequest = 0;
	let editGeneration = 0;
	const fail = (cause: unknown) => { const text = String(cause); setError(text); reportParsec({ type: 'mutation', phase: 'failed', tool: tool(), summary: 'The definition change needs attention.', technicalDetail: text }); };
	async function refresh() {
		try {
			const [health, outfits, jobs] = await Promise.all([api.get<CatalogStatus>('/api/definitions/status'), api.get<components['schemas']['DraftList']>('/api/definitions/drafts?kind=outfit'), api.get<components['schemas']['DraftList']>('/api/definitions/drafts?kind=job')]);
			if (!disposed) {
				if (base() && baseCatalogId() !== health.catalog_id) { setBase(undefined); setBaseCatalogId(''); setReferences([]); setStage(undefined); setRebase(undefined); }
				setStatus(health); setDrafts([...outfits.drafts, ...jobs.drafts]);
				const current = [...outfits.drafts, ...jobs.drafts].find((item) => item.draft.id === draft()?.id);
				if (current && !dirty() && current.record_hash !== recordHash()) { setDraft(current.draft); setRecordHash(current.record_hash); setStage(undefined); setRebase(undefined); }
			}
		} catch (cause) { if (!disposed) fail(cause); }
	}
	const discard = () => !dirty() || window.confirm('Discard the unsaved definition changes?');
	useBeforeLeave((event) => { if (dirty() && !event.defaultPrevented) { event.preventDefault(); if (discard()) { setDirty(false); event.retry(true); } } });
	onMount(() => { void refresh(); const beforeUnload = (event: BeforeUnloadEvent) => { if (dirty()) { event.preventDefault(); event.returnValue = ''; } }; window.addEventListener('beforeunload', beforeUnload); onCleanup(() => window.removeEventListener('beforeunload', beforeUnload)); });
	onCleanup(() => { disposed = true; inspectRequest++; });
	async function inspect(typePath: string, catalogId: string) {
		const current = ++inspectRequest; setBase(undefined); setBaseCatalogId(''); setReferences([]); setSource(undefined);
		try {
			const value = await api.get<Definition>(`/api/definitions/definition?type_path=${encodeURIComponent(typePath)}&catalog_id=${encodeURIComponent(catalogId)}`);
			if (disposed || current !== inspectRequest) return;
			setBase(value); setBaseCatalogId(catalogId);
			setSelectedContext({ tool: tool(), record_kind: value.kind, record_id: value.type_path, type_path: value.type_path, catalog_id: catalogId, groups: [] });
			const refs = await api.get<Reference[]>(`/api/definitions/references?target_type=${encodeURIComponent(typePath)}&catalog_id=${encodeURIComponent(catalogId)}`);
			if (!disposed && current === inspectRequest) setReferences(refs);
		} catch (cause) { if (!disposed && current === inspectRequest) { const savedBase = draft()?.baseline?.find((item) => item.type_path === typePath); if (savedBase && draft()?.catalog_id === catalogId) { setBase(savedBase); setBaseCatalogId(catalogId); } fail(cause); } }
	}
	function selectDefinition(value: Definition) {
		if (!discard() || !status()?.catalog_id) return;
		const owner = drafts().find((saved) => saved.draft.edits.some((item) => item.type_path === value.type_path && item.operation !== 'update'));
		if (owner && [value.source, ...(value.occurrences ?? [])].some((span) => span?.path.includes('/content_tools/code/generated_'))) {
			if (owner.draft.kind !== props.kind) navigate(`/${owner.draft.kind}-editor?draft_id=${encodeURIComponent(owner.draft.id)}`);
			else void load(owner);
			return;
		}
		editGeneration++; setPicker(undefined); setConstantField(undefined); setBase(value); editGeneration++; setPicker(undefined); setConstantField(undefined); setDraft(undefined); setDirty(false); setRecordHash(null); setStage(undefined); setRebase(undefined); setError(''); setEditIndex(0);
		void inspect(value.type_path, status()!.catalog_id!);
	}
	function begin(operation: DefinitionEdit['operation']) {
		if (!base() || baseCatalogId() !== status()?.catalog_id || !discard()) return;
		editGeneration++; setPicker(undefined); setConstantField(undefined); setDraft(createDraft(base()!, baseCatalogId(), operation)); setRecordHash(null); setDirty(true); setStage(undefined); setRebase(undefined); setEditIndex(0);
	}
	function change(next: DefinitionDraft) { editGeneration++; setPicker(undefined); setConstantField(undefined); setDraft(next); setDirty(true); setStage(undefined); setRebase(undefined); setError(''); }
	function updateEdit(values: Partial<DefinitionEdit>) { const next = values.type_path !== undefined && values.type_path !== edit()!.type_path ? renameDraftType(draft()!, editIndex(), values.type_path) : structuredClone(draft()!); Object.assign(next.edits[editIndex()]!, values); change(next); }
	async function save() {
		if (!draft()) return;
		setBusy(true); setError('');
		const saving = draft()!, generation = editGeneration;
		try {
			const saved = await api.post<SavedDraft>('/api/definitions/drafts', { draft: draft(), expected_record_hash: recordHash() });
			if (disposed) return;
			if (draft()?.id === saving.id) {
				setRecordHash(saved.record_hash);
				if (generation === editGeneration) { setDraft(saved.draft); setDirty(false); }
				setStage(undefined); setRebase(undefined);
			}
			setMessage(generation === editGeneration ? 'Draft saved. Game files are unchanged.' : 'Earlier draft version saved. Your newer changes remain unsaved.'); await refresh();
			reportParsec({ type: 'mutation', phase: 'completed', tool: tool(), summary: 'Definition draft saved.' });
		} catch (cause) { fail(cause); } finally { setBusy(false); }
	}
	async function load(saved: SavedDraft) {
		if (!discard()) return;
		editGeneration++; setPicker(undefined); setConstantField(undefined); setDraft(structuredClone(saved.draft)); setRecordHash(saved.record_hash); setDirty(false); setStage(undefined); setRebase(undefined); setEditIndex(0); setError('');
		const primary = saved.draft.edits[0]!;
		setBase(saved.draft.baseline?.find((item) => item.type_path === primary.source_type || item.type_path === primary.type_path));
		await inspect(primary.source_type ?? primary.parent_type ?? primary.type_path, saved.draft.catalog_id);
	}
	const actionPayload = () => ({ kind: draft()!.kind, id: draft()!.id, record_hash: recordHash()! });
	async function start(operation: 'index' | 'analyze' | 'validate' | 'render' | 'interactive') {
		setBusy(true); setError('');
		try {
			const native = operation === 'render' || operation === 'interactive';
			const path = native ? 'preview' : operation;
			const target = edit()?.kind === 'id_trim' ? draft()!.edits[0]! : edit()!;
			const body = operation === 'index' ? {} : { ...actionPayload(), ...(native ? { mode: operation, type_path: target.type_path, species: species() || null, body_gender: bodyGender() || null, body_type: bodyType() || null } : {}) };
			const run = await api.post<EditorRun>(`/api/definitions/${path}`, body);
			setDefinitionRuns([...appState.definitionRuns.filter((item) => item.id !== run.id), run]);
			reportParsec({ type: 'job', phase: 'started', tool: tool(), summary: `${operation} started.` });
		} catch (cause) { fail(cause); } finally { setBusy(false); }
	}
	const completed = new Set<string>();
	createEffect(() => {
		for (const run of appState.definitionRuns) {
			if (run.status !== 'ready' && run.status !== 'failed' && run.status !== 'cancelled' || completed.has(`${run.id}:${run.status}`)) continue;
			completed.add(`${run.id}:${run.status}`); void refresh();
			if (run.draft_hash === recordHash() || run.operation === 'catalog') reportParsec({ type: 'job', phase: run.status === 'ready' ? 'completed' : 'failed', tool: tool(), summary: run.message });
		}
	});
	let linked = '';
	createEffect(on(() => [parameters.type_path, parameters.catalog_id, status()?.catalog_id] as const, ([value, requested, active]) => {
		const typePath = Array.isArray(value) ? value[0] : value;
		const binding = `${typePath}:${requested ?? active}`;
		if (!typePath || !active || binding === linked || !discard()) return;
		linked = binding;
		editGeneration++; setPicker(undefined); setConstantField(undefined); setDraft(undefined); setDirty(false); setRecordHash(null); setStage(undefined); setRebase(undefined); setEditIndex(0); setBase(undefined);
		void inspect(typePath, typeof requested === 'string' ? requested : active);
	}));
	let linkedDraft = '';
	createEffect(() => { const id = parameters.draft_id; const saved = drafts().find((item) => item.draft.id === id); if (saved && id !== linkedDraft && discard()) { linkedDraft = saved.draft.id; setDirty(false); void load(saved); } });
	createEffect(on(() => appState.workspaceRevision, () => void refresh(), { defer: true }));
	const groups = createMemo(() => [...new Set((base()?.fields ?? []).map((field) => groupFor(field.name)))]);
	const runs = () => appState.definitionRuns.filter((run) => run.operation === 'catalog' || run.draft_hash === recordHash());
	const validSaved = () => Boolean(recordHash() && !dirty() && status()?.current && draft()?.catalog_id === status()?.catalog_id);
	const operationRunning = () => appState.definitionRuns.some((run) => run.status === 'running' || run.status === 'queued' || run.operation === 'interactive' && run.status === 'ready');
	const validated = () => validSaved() && runs().some((run) => run.operation === 'validate' && run.status === 'ready');
	const procText = () => edit()?.procedures?.[procedure()] ?? (base()?.procedures?.filter((item) => item.name === procedure()).at(-1)?.text ?? `${edit()?.type_path}/proc/${procedure()}()\n\treturn\n`).replace(base()?.type_path ?? '\0', edit()?.type_path ?? '');
	function setProc(text: string) { updateEdit({ procedures: { ...edit()?.procedures, [procedure()]: text } }); }
	async function inspectSource(member?: string) {
		try { setSource(await api.get<components['schemas']['SourceExcerpt']>(`/api/definitions/source?${new URLSearchParams({ type_path: base()!.type_path, catalog_id: baseCatalogId(), ...(member ? { member } : {}) })}`)); } catch (cause) { fail(cause); }
	}
	async function reviewRebase() { const generation = editGeneration, payload = actionPayload(); setBusy(true); try { const proposal = await api.post<components['schemas']['RebaseProposal']>('/api/definitions/rebase', payload); if (!disposed && generation === editGeneration && recordHash() === proposal.expected_record_hash) setRebase(proposal); } catch (cause) { fail(cause); } finally { setBusy(false); } }
	async function addLinked(typePath: string) {
		const generation = editGeneration;
		const already = draft()!.edits.findIndex((item) => item.type_path === typePath);
		if (already >= 0) { setEditIndex(already); const selected = draft()!.edits[already]!; await inspect(selected.source_type ?? selected.parent_type ?? selected.type_path, draft()!.catalog_id); return; }
		try {
			const value = await api.get<Definition>(`/api/definitions/definition?${new URLSearchParams({ type_path: typePath, catalog_id: draft()!.catalog_id })}`);
			if (disposed || generation !== editGeneration) return;
			const addition = createDraft(value, draft()!.catalog_id, modularOwners(value).length ? 'update' : 'override').edits[0]!;
			change({ ...draft()!, edits: [...draft()!.edits, addition] }); setEditIndex(draft()!.edits.length - 1); await inspect(typePath, draft()!.catalog_id);
		} catch (cause) { fail(cause); }
	}
	const related = () => (base()?.fields ?? []).filter((field) => /outfit|job(type)?$|id_trim/.test(field.name)).map((field) => ({ name: field.name, path: edit()?.fields?.[field.name] ?? field.value })).filter((item): item is { name: string; path: string } => typeof item.path === 'string' && /^\/datum\/(job|outfit|id_trim)(?:\/|$)/.test(item.path));
	createEffect(() => {
		if (!constantField() || !draft()) return;
		const controller = new AbortController();
		onCleanup(() => controller.abort());
		const query = constantQuery();
		void api.get<components['schemas']['DefinitionConstant'][]>(`/api/definitions/constants?${new URLSearchParams({ catalog_id: draft()!.catalog_id, query })}`, { signal: controller.signal }).then((items) => { if (!controller.signal.aborted) setConstants(items); }).catch((cause) => { if (!controller.signal.aborted) fail(cause); });
	});
	function chooseConstant(name: string) {
		const field = constantField()!;
		const current = edit()?.fields?.[field] ?? base()?.fields?.find((item) => item.name === field)?.expression ?? '';
		let expression = name;
		if (/access/.test(field) && current !== 'null' && current !== '' && !/^list\([A-Z0-9_,\s]*\)$/.test(current)) { fail('This access expression is not a literal list. Edit it in source mode or clear it before choosing constants.'); return; }
		if (/access/.test(field)) expression = /^list\([A-Z0-9_,\s]*\)$/.test(current) ? `${current.slice(0, -1)}${current !== 'list()' ? ', ' : ''}${name})` : `list(${name})`;
		else if (/flags/.test(field) && current && current !== '0' && current !== 'NONE') expression = `(${current}) | ${name}`;
		change(setExpression(draft()!, editIndex(), field, expression)); setConstantField(undefined);
	}
	async function stageChanges() { setBusy(true); try { setStage(await api.post<EditorStage>('/api/definitions/prepare', actionPayload())); } catch (cause) { fail(cause); } finally { setBusy(false); } }
	async function apply() { if (!stage()) return; setBusy(true); try { setReceipt(await api.post<components['schemas']['GameChangeReceipt']>('/api/definitions/apply', { ...actionPayload(), stage_id: stage()!.stage_id })); setStage(undefined); setRebase(undefined); setMessage('Applied the reviewed change set. Refreshing the source catalog.'); await refresh(); } catch (cause) { fail(cause); } finally { setBusy(false); } }

	return <div>
		<p>Author definitions, inspect inheritance, and review exact game changes.</p>
		<div class={styles.status} role="status">{status()?.current ? 'Source catalog is current.' : status()?.reason ?? 'Loading authoring workspace...'}<div class={styles.toolbar}><button disabled={busy() || operationRunning() || !status()?.analyzer_available} onClick={() => void start('index')}>Refresh source catalog</button><Show when={status() && !status()!.analyzer_available}><span>Pinned analyzer unavailable</span></Show><Show when={status() && !status()!.byond_available}><span>BYOND unavailable  /  native validation and previews disabled</span></Show></div></div>
		<Show when={error()}><p role="alert" class={styles.error}>{error()}</p></Show><Show when={message()}><p role="status">{message()}</p></Show>
		<div class={styles.workspace}>
			<aside class={styles.panel}><Show when={status()?.catalog_id}><TypePicker kind={props.kind} label={`Find ${props.kind === 'job' ? 'a job' : 'an outfit'}`} catalogId={status()!.catalog_id!} onPick={selectDefinition} /></Show><h2>Saved drafts</h2><div class={styles.drafts}><For each={drafts().filter((saved) => saved.draft.kind === props.kind)}>{(saved) => <button onClick={() => void load(saved)}>{saved.draft.label || saved.draft.edits[0]!.type_path}</button>}</For><Show when={!drafts().length}><p class={styles.hint}>Your saved drafts will appear here.</p></Show></div></aside>
			<section class={styles.panel} aria-label="Definition workspace">
				<Show when={base()} fallback={<p>Select a definition to inspect it or open a saved draft.</p>}>
					<h2>{title(base()!)}</h2><code>{base()!.type_path}</code><p class={styles.hint}>Parent: {base()!.parent_type ?? 'none'}  /  Source: {base()!.source?.path ?? base()!.occurrences?.[0]?.path ?? 'inherited / unavailable'}</p>
					<p class={styles.hint}>{references().length} incoming source references. Editing this shared definition can affect every linked user.</p>
					<Show when={base()!.kind === 'job'}><p class={styles.hint}>Category: {base()!.job_category ?? 'unresolved'} / player selection: {base()!.player_selectable === null || base()!.player_selectable === undefined ? 'unresolved' : base()!.player_selectable ? 'selectable' : 'not selectable'}</p></Show><div class={styles.toolbar}><button onClick={() => begin('override')}>Override</button><button disabled={modularOwners(base()!).length === 0} onClick={() => begin('update')}>Update module</button><button onClick={() => begin('create')}>Create from this</button><button onClick={() => begin('replace')}>Replace</button><button onClick={() => void inspectSource()}>Inspect source</button><button onClick={() => void addReference({ tool: props.kind === 'job' ? 'job-editor' : 'outfit-editor', kind: 'definition', key: base()!.type_path, label: title(base()!), catalog_id: baseCatalogId() }).then(() => setMessage('Definition pinned to shared references.')).catch(fail)}>Pin reference</button></div>
				</Show>
				<Show when={draft() && edit()}>
					<div class={styles.metadata}><label>Draft name<input value={draft()!.label ?? ''} onInput={(event) => change({ ...draft()!, label: event.currentTarget.value })} /></label><label>Definition in bundle<select value={editIndex()} onChange={(event) => { const index = Number(event.currentTarget.value); setEditIndex(index); const value = draft()!.edits[index]!; void inspect(value.source_type ?? value.parent_type ?? value.type_path, draft()!.catalog_id); }}><For each={draft()!.edits}>{(item, index) => <option value={index()}>{item.kind}: {item.type_path}</option>}</For></select></label><label>Type path<input value={edit()!.type_path} disabled={edit()!.operation === 'update' || edit()!.operation === 'override' || Boolean(draft()!.applied_stage_ids?.length)} onInput={(event) => updateEdit({ type_path: event.currentTarget.value })} /></label><Show when={edit()!.operation === 'create' || edit()!.operation === 'replace'}><label>Parent type<input value={edit()!.parent_type ?? ''} onInput={(event) => updateEdit({ parent_type: event.currentTarget.value })} /></label></Show></div>
					<Show when={edit()!.operation === 'replace' && edit()!.kind === 'job'}><label>Original job after replacement<select required value={edit()!.old_job_selection ?? ''} onChange={(event) => updateEdit({ old_job_selection: event.currentTarget.value as 'retain' | 'retire' })}><option value="" disabled>Choose explicitly...</option><option value="retain">Keep selectable</option><option value="retire">Retire from player selection</option></select></label></Show>
					<Show when={props.kind === 'job' && edit()!.kind === 'job' && draft()!.edits.length === 1 && (edit()!.operation === 'create' || edit()!.operation === 'replace')}><button onClick={() => change(makeStationBundle(draft()!))}>Create linked outfit and ID trim</button></Show>
					<Show when={related().length}><details class={styles.group}><summary>Linked definitions</summary><For each={related()}>{(item) => <div class={styles.toolbar}><span>{item.name}: <code>{item.path}</code></span><button onClick={() => void addLinked(item.path)}>Edit in this draft</button><a href={`/${item.path.startsWith('/datum/outfit') ? 'outfit' : 'job'}-editor?type_path=${encodeURIComponent(item.path)}`}>Open editor</a></div>}</For></details></Show>
					<Show when={edit()!.kind === 'outfit'}><section class={styles.group} aria-label="Equipment slots"><h3>Equipment</h3><div class={styles.equipment}><For each={(base()?.fields ?? []).filter((field) => /^(head|mask|neck|ears|glasses|uniform|suit|gloves|shoes|back|belt|id|pda|l_hand|r_hand|l_pocket|r_pocket|suit_store)$/.test(field.name))}>{(field) => <button onClick={() => { const value = edit()?.fields?.[field.name] ?? field.expression ?? ''; setPreviewSlot(field.name); if (/^\/obj\/item/.test(value)) setPreviewPath(value); setPicker(field.name); }}><strong>{field.name.replaceAll('_', ' ')}</strong><code>{edit()?.fields?.[field.name] ?? field.expression ?? 'unresolved'}</code></button>}</For></div></section></Show>
					<For each={groups()}>{(group) => <details class={styles.group} open={group === 'Identity'}><summary>{group}</summary><For each={(base()?.fields ?? []).filter((field) => groupFor(field.name) === group)}>{(field) => <FieldEditor field={field} expression={edit()?.fields?.[field.name]} onChange={(value) => change(setExpression(draft()!, editIndex(), field.name, value))} onPick={() => setPicker(field.name)} onInspect={() => void inspectSource(field.name)} onPreview={(path) => { setPreviewPath(path); setPreviewSlot(field.name); }} onConstants={() => { setConstantField(field.name); setConstantQuery(/access/.test(field.name) ? 'ACCESS_' : ''); }} />}</For></details>}</For>
					<Show when={edit()!.operation === 'update' && modularOwners(base()!).length > 1}><label>Module for additional overrides<select value={edit()!.target_file ?? ''} onChange={(event) => updateEdit({ target_file: event.currentTarget.value || null })}><option value="">Choose owning module</option><For each={modularOwners(base()!)}>{(path) => <option value={path}>{path}</option>}</For></select></label></Show><details class={styles.group}><summary>Advanced DM procedures</summary><p class={styles.hint}>Edit the complete procedure header and body. Native validation checks this exact source; game code runs only when you explicitly preview it.</p><label>Procedure name<input list="definition-procs" value={procedure()} onInput={(event) => setProcedure(event.currentTarget.value)} /></label><datalist id="definition-procs"><For each={base()?.procedures ?? []}>{(item) => <option value={item.name} />}</For></datalist><textarea class={styles.source} aria-label="DM procedure source" value={procText()} onInput={(event) => setProc(event.currentTarget.value)} spellcheck={false} /><button onClick={() => { const procs = { ...edit()!.procedures }; delete procs[procedure()]; updateEdit({ procedures: procs }); }}>Reset procedure</button></details>
					<Show when={edit()!.operation === 'replace'}><details class={styles.group} open><summary>Reference migration</summary><p class={styles.hint}>Select exact source references to move. Dynamic references, maps, saved preferences, bans, and operator configuration require separate review.</p><For each={references()}>{(ref) => <label class={styles.check}><input type="checkbox" disabled={!ref.editable} checked={edit()?.reference_ids?.includes(ref.id) ?? false} onChange={(event) => updateEdit({ reference_ids: event.currentTarget.checked ? [...(edit()!.reference_ids ?? []), ref.id] : (edit()!.reference_ids ?? []).filter((id) => id !== ref.id) })} /><code>{ref.source.path}:{ref.source.start}</code><span>{ref.reason}</span></label>}</For></details></Show>
					<div class={styles.toolbar}><button disabled={busy() || !dirty()} onClick={() => void save()}>Save draft</button><button disabled={busy() || operationRunning() || !validSaved() || !status()?.analyzer_available} onClick={() => void start('analyze')}>Reparse draft</button><button disabled={busy() || operationRunning() || !validSaved() || !status()?.byond_available} onClick={() => void start('validate')}>Validate and compile</button><button disabled={busy() || operationRunning() || !validated()} onClick={() => void stageChanges()}>Prepare changes</button><button disabled={busy() || dirty() || !recordHash() || !status()?.current} onClick={() => void reviewRebase()}>Review source refresh</button><span class={styles.hint}>{dirty() ? 'Unsaved changes' : recordHash() ? 'Saved' : ''}</span></div>
					<Show when={rebase()}><section class={styles.group}><h3>Review changed source values</h3><For each={rebase()!.changes}>{(line) => <p>{line}</p>}</For><button onClick={() => { if (recordHash() !== rebase()!.expected_record_hash) { setRebase(undefined); return; } change(rebase()!.draft); setRebase(undefined); void inspect(edit()!.source_type ?? edit()!.parent_type ?? edit()!.type_path, draft()!.catalog_id); }}>Use this source snapshot in the draft</button><button onClick={() => setRebase(undefined)}>Cancel refresh</button></section></Show>
					<details class={styles.group} open><summary>Native previews</summary><p class={styles.hint}>These controls compile and run local game code in private working directories. They are not a security sandbox.</p><label>Species type path<input value={species()} onInput={(event) => setSpecies(event.currentTarget.value)} /></label><div class={styles.metadata}><label>Gender<select value={bodyGender()} onChange={(event) => setBodyGender(event.currentTarget.value)}><option value="">Default</option><option value="male">Male</option><option value="female">Female</option></select></label><label>Body type<select value={bodyType()} onChange={(event) => setBodyType(event.currentTarget.value)}><option value="">Use gender / default</option><option value="male">Male physique</option><option value="female">Female physique</option></select></label></div><div class={styles.toolbar}><button disabled={busy() || operationRunning() || !validated()} onClick={() => void start('render')}>Render character</button><button disabled={busy() || operationRunning() || !validated()} onClick={() => void start('interactive')}>Launch test map</button></div></details>
					<Show when={stage()}><section class={styles.group}><h3>Review proposed changes</h3><For each={stage()!.compatibility_report}>{(line) => <p>{line}</p>}</For><pre class={styles.diff}>{stage()!.preview}</pre><button disabled={busy() || dirty()} onClick={() => void apply()}>Apply reviewed changes</button></section></Show>
				</Show>
				<Show when={receipt()}><section class={styles.group}><h3>Application receipt</h3><p>Stage {receipt()!.stage_id}</p><For each={receipt()!.paths}>{(path) => <p><code>{path}</code>  /  {receipt()!.sha256[path]}</p>}</For><Show when={receipt()!.refresh_warning}><p role="alert">{receipt()!.refresh_warning}</p></Show></section></Show>
				<For each={runs()}>{(run) => <section class={styles.group}><strong>{run.operation}  /  {run.status}</strong><Show when={run.status === 'running' || run.status === 'queued'} fallback={<p role="status">{run.message}</p>}><LoadingIndicator label={run.message || `${run.operation} in progress`} tool={tool()} /></Show><button onClick={() => void api.get<string>(`/api/definitions/runs/${run.id}/log`).then(setRunLog).catch(fail)}>View log</button><Show when={run.equipment?.length}><details><summary>Equipped items and access</summary><pre class={styles.source}>{JSON.stringify(run.equipment, null, 2)}</pre></details></Show><For each={run.diagnostics}>{(line) => <p class={styles.hint}>{line}</p>}</For><Show when={run.status === 'running' || run.status === 'queued' || run.operation === 'interactive' && run.status === 'ready'}><button onClick={() => void api.post(`/api/definitions/runs/${run.id}/stop`, {}).catch(fail)}>Stop</button></Show><div class={styles.preview}><For each={run.images ?? []}>{(_, index) => <img src={`/api/definitions/runs/${run.id}/images/${index()}`} alt={`${props.kind} preview direction ${index() + 1}`} />}</For></div></section>}</For>
			</section>
			<aside class={styles.inspector} aria-label="Inspector and previews"><Show when={previewPath() && status()?.catalog_id}><ItemInspector typePath={previewPath()} catalogId={status()!.catalog_id!} slot={previewSlot()} /></Show><Show when={runLog()}><details open><summary>Operation log</summary><pre class={styles.source}>{runLog()}</pre><button onClick={() => setRunLog('')}>Close log</button></details></Show><Show when={source()}><section class={styles.group}><h3>Source</h3><p>{source()!.path}:{source()!.line}</p><pre class={styles.diff}>{source()!.text}</pre></section></Show><For each={runs().filter((run) => run.effective?.length)}>{(run) => <details class={styles.group}><summary>Reparsed effective values  /  {run.operation}</summary><Show when={dirty()}><p class={styles.hint}>Draft changed since this result.</p></Show><For each={run.effective}>{(item) => <details><summary>{item.type_path}</summary><For each={item.fields ?? []}>{(field) => <p class={styles.hint}>{field.name}: <code>{field.value_known ? JSON.stringify(field.value) : field.expression ?? 'unresolved'}</code></p>}</For></details>}</For></details>}</For></aside>
		</div>
		<Show when={picker()}><PickerDialog label="Choose a definition" close={() => setPicker(undefined)}><TypePicker kind={/outfit/.test(picker()!) ? 'outfit' : /id_trim/.test(picker()!) ? 'id_trim' : /job(type)?$/.test(picker()!) ? 'job' : 'item'} label={`Choose ${picker()!.replaceAll('_', ' ')}`} catalogId={draft()!.catalog_id} onPick={(item) => { const field = picker()!; const current = edit()?.fields?.[field] ?? base()?.fields?.find((value) => value.name === field)?.expression ?? 'list()'; const contents = /contents|implants|skillchips/.test(field); const rows = contents ? (current === 'null' ? [] : parseContents(current)) : null; if (contents && rows === null) { fail('This contents expression is not a literal list. Edit it in source mode or clear it first.'); return; } change(setExpression(draft()!, editIndex(), field, rows ? formatContents([...rows, { typePath: item.type_path, count: 1, counted: !/implants|skillchips/.test(field) }]) : item.type_path)); if (item.kind === 'item') { setPreviewPath(item.type_path); setPreviewSlot(field); } setPicker(undefined); }} /></PickerDialog></Show>
		<Show when={constantField()}><PickerDialog label="Choose a constant" close={() => setConstantField(undefined)}><label>Find a constant<input autofocus value={constantQuery()} onInput={(event) => setConstantQuery(event.currentTarget.value)} /></label><div class={styles.drafts}><For each={constants()}>{(item) => <button onClick={() => chooseConstant(item.name)}><code>{item.name}</code> = {item.expression ?? 'unresolved'}</button>}</For></div></PickerDialog></Show>
	</div>;
}

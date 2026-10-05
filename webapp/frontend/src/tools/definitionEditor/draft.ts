import type { Definition, DefinitionDraft, DefinitionEdit } from './types';

export function createDraft(definition: Definition, catalogId: string, operation: DefinitionEdit['operation']): DefinitionDraft {
	const kind = definition.kind === 'outfit' ? 'outfit' : 'job';
	if (definition.kind !== 'job' && definition.kind !== 'outfit' && definition.kind !== 'id_trim') throw new Error('Select a job, outfit, or ID trim.');
	const isNew = operation === 'create' || operation === 'replace';
	return { schema_version: 1, id: `${kind}-${crypto.randomUUID()}`, kind, label: '', catalog_id: catalogId, edits: [{
		kind: definition.kind, operation, source_type: definition.type_path,
		type_path: isNew ? `${definition.type_path}/aphelion_variant` : definition.type_path,
		parent_type: isNew ? definition.type_path : null,
		fields: {}, procedures: {}, reference_ids: [], old_job_selection: null, target_file: modularOwners(definition).length === 1 ? modularOwners(definition)[0]! : null,
	}] };
}

export function modularOwners(definition: Definition): string[] {
	const spans = [definition.source, ...(definition.occurrences ?? []), ...(definition.fields ?? []).filter((field) => field.owner_type === definition.type_path).map((field) => field.source), ...(definition.procedures ?? []).filter((proc) => proc.owner_type === definition.type_path).map((proc) => proc.source)];
	if (spans.some((span) => span?.path.includes('/content_tools/code/generated_'))) return [];
	return [...new Set(spans.filter((span) => span?.path.startsWith('modular_nova/') || span?.path.startsWith('modular_aphelion/')).map((span) => span!.path))].sort();
}

export function setExpression(draft: DefinitionDraft, index: number, field: string, expression: string | undefined): DefinitionDraft {
	const next = structuredClone(draft);
	const edit = next.edits[index];
	if (!edit) throw new Error('Selected draft definition is missing.');
	const fields = { ...edit.fields };
	if (expression === undefined) delete fields[field];
	else fields[field] = expression;
	edit.fields = fields;
	return next;
}

export function renameDraftType(draft: DefinitionDraft, index: number, typePath: string): DefinitionDraft {
	const next = structuredClone(draft);
	const selected = next.edits[index];
	if (!selected || !['create', 'replace'].includes(selected.operation) || draft.applied_stage_ids?.length) throw new Error('Only unapplied new definitions can be renamed.');
	const previous = selected.type_path;
	selected.type_path = typePath;
	for (const edit of next.edits) {
		if (edit.parent_type === previous) edit.parent_type = typePath;
		for (const [name, expression] of Object.entries(edit.fields ?? {})) {
			if (expression === previous) edit.fields![name] = typePath;
		}
	}
	for (const [name, source] of Object.entries(selected.procedures ?? {})) {
		if (source.startsWith(`${previous}/`)) selected.procedures![name] = typePath + source.slice(previous.length);
	}
	return next;
}

export function makeStationBundle(draft: DefinitionDraft): DefinitionDraft {
	const next = structuredClone(draft);
	const job = next.edits[0];
	if (!job || job.kind !== 'job') throw new Error('A station bundle requires its primary job.');
	const suffix = job.type_path.split('/').slice(-2).join('_');
	const outfit = `/datum/outfit/job/${suffix}`;
	const trim = `/datum/id_trim/job/${suffix}`;
	job.fields = { title: '"New station job"', config_tag: JSON.stringify(`JOB_${suffix.toUpperCase()}`), alternate_titles: 'list()', alt_titles: 'list()', ...job.fields, job_flags: 'STATION_JOB_FLAGS', outfit };
	next.edits.push({ kind: 'outfit', operation: 'create', type_path: outfit, parent_type: '/datum/outfit/job', source_type: '/datum/outfit/job', fields: { jobtype: job.type_path, id_trim: trim }, procedures: {}, reference_ids: [] });
	next.edits.push({ kind: 'id_trim', operation: 'create', type_path: trim, parent_type: '/datum/id_trim/job', source_type: '/datum/id_trim/job', fields: { job: job.type_path, assignment: job.fields.title! }, procedures: {}, reference_ids: [] });
	return next;
}

export interface ContentItem { typePath: string; count: number; counted?: boolean }
export function parseContents(expression: string): ContentItem[] | null {
	if (expression === 'list()') return [];
	const match = /^list\(([^()]*)\)$/.exec(expression.trim());
	if (!match) return null;
	const result: ContentItem[] = [];
	for (const value of match[1]!.split(',')) {
		const item = /^\s*(\/[\w/]+)\s*(?:=\s*(\d+))?\s*$/.exec(value);
		if (!item || Number(item[2] ?? 1) > 1000 || Number(item[2] ?? 1) < 1) return null;
		result.push({ typePath: item[1]!, count: Number(item[2] ?? 1), counted: item[2] !== undefined });
	}
	return result;
}
export function formatContents(items: readonly ContentItem[]): string {
	return `list(${items.map((item) => item.counted === false ? Array.from({ length: item.count }, () => item.typePath).join(', ') : `${item.typePath} = ${item.count}`).join(', ')})`;
}

export function literalString(expression: string): string | null {
	if (!/^"(?:[^"\\\[\]\r\n]|\\["\\nrt\[\]])*"$/.test(expression)) return null;
	try { return JSON.parse(expression.replace(/\\([\[\]])/g, '$1')) as string; } catch { return null; }
}

export function stringExpression(value: string): string {
	return JSON.stringify(value).replaceAll('[', '\\[').replaceAll(']', '\\]');
}

export function title(definition: Definition): string {
	const value = definition.fields?.find((field) => field.name === 'name' || field.name === 'title')?.value;
	return typeof value === 'string' ? value : definition.type_path.split('/').at(-1) ?? definition.type_path;
}

export function groupFor(name: string): string {
	if (/^(name|title|description|alt|config_tag|faction)/.test(name)) return 'Identity';
	if (/contents|implant|skillchip/.test(name)) return 'Contents and grants';
	if (name === 'accessory') return 'Equipment';
	if (/(^|_)access($|_)|trim|assignment|hud|template/.test(name)) return 'ID and access';
	if (/outfit|department|supervisor|paycheck|account/.test(name)) return 'Job relationships';
	if (/position|age|experience|exp_|require|flag|skill|trait|banned|loadout/.test(name)) return 'Eligibility and rules';
	if (/uniform|suit|head|mask|neck|shoe|glove|ear|glass|belt|back|pocket|hand|pda|id$|underwear|undershirt|sock|bra|satchel|duffel/.test(name)) return 'Equipment';
	return 'Other settings';
}

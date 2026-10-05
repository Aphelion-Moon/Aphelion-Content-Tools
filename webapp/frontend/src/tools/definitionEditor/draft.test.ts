import { describe, expect, it } from 'vitest';
import { createDraft, setExpression, makeStationBundle, parseContents, formatContents, groupFor, renameDraftType } from './draft';
import type { Definition } from './types';

const definition: Definition = { type_path: '/datum/job/engineer', kind: 'job', parent_type: '/datum/job', fields: [], procedures: [], references: [] };

describe('definition drafts', () => {
	it('keeps a new identity separate and requires a replacement selection choice', () => {
		const draft = createDraft(definition, 'catalog-1', 'replace');
		expect(draft.edits[0]!.type_path).not.toBe(definition.type_path);
		expect(draft.edits[0]!.source_type).toBe(definition.type_path);
		expect(draft.edits[0]!.old_job_selection).toBeNull();
	});
	it('reset removes only the local edit and never flattens inherited values', () => {
		const draft = createDraft(definition, 'catalog-1', 'override');
		const changed = setExpression(draft, 0, 'title', '"Station engineer"');
		expect(changed.edits[0]!.fields?.title).toBe('"Station engineer"');
		expect(setExpression(changed, 0, 'title', undefined).edits[0]!.fields).toEqual({});
		expect(draft.edits[0]!.fields).toEqual({});
	});
	it('station bundle links job outfit and trim in one draft', () => {
		const draft = makeStationBundle(createDraft(definition, 'catalog-1', 'create'));
		const job = draft.edits[0]!, outfit = draft.edits[1]!, trim = draft.edits[2]!;
		expect(job.fields?.outfit).toBe(outfit.type_path);
		expect(outfit.fields?.id_trim).toBe(trim.type_path);
		expect(trim.fields?.job).toBe(job.type_path);
		expect(job.fields?.alt_titles).toBe('list()');
	});
	it('round trips ordered counted contents and declines complex expressions', () => {
		const source = 'list(/obj/item/wrench = 2, /obj/item/screwdriver = 1)';
		expect(formatContents(parseContents(source)!)).toBe(source);
		expect(parseContents('build_contents()')).toBeNull();
	});
	it('preserves repeated uncounted entries instead of converting them to associative keys', () => {
		const source = 'list(/obj/item/test, /obj/item/test)';
		expect(formatContents(parseContents(source)!)).toBe(source);
	});
});

it('groups outfit accessories and grants by meaning rather than substrings', () => {
	expect(groupFor('accessory')).toBe('Equipment');
	expect(groupFor('skillchips')).toBe('Contents and grants');
	expect(groupFor('minimal_access')).toBe('ID and access');
});

it('keeps internal bundle links coherent when a new definition is renamed', () => {
	const draft = makeStationBundle(createDraft(definition, 'catalog-1', 'create'));
	const oldPath = draft.edits[0]!.type_path;
	draft.edits[0]!.procedures = { custom: `${oldPath}/proc/custom()\n\treturn\n` };
	const next = renameDraftType(draft, 0, '/datum/job/new_engineer');
	expect(next.edits[1]!.fields?.jobtype).toBe('/datum/job/new_engineer');
	expect(next.edits[2]!.fields?.job).toBe('/datum/job/new_engineer');
	expect(next.edits[0]!.source_type).toBe(definition.type_path);
	expect(next.edits[0]!.procedures?.custom).toMatch(/^\/datum\/job\/new_engineer\/proc\/custom/);
	expect(draft.edits[0]!.type_path).toBe(oldPath);
});


it('does not apply station bundle fields to an outfit draft', () => {
	const outfit: Definition = { ...definition, type_path: '/datum/outfit/example', kind: 'outfit', parent_type: '/datum/outfit' };
	const draft = createDraft(outfit, 'catalog-1', 'create');
	expect(() => makeStationBundle(draft)).toThrow('A station bundle requires its primary job.');
	expect(draft.edits).toHaveLength(1);
});

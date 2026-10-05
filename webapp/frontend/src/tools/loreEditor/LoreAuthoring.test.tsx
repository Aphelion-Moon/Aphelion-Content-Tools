import axe from 'axe-core';
import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api } from '~/lib/api';
import EntryEditor from './EntryEditor';
import GroupManager from './GroupManager';
import ReviewActions from './ReviewActions';
import type { ReviewEntry } from './reviewFeed';

const HASH = 'a'.repeat(64);
const entry = {
	id: 'items.radio',
	type_path: '/obj/item/radio',
	name: 'Radio override',
	description: null,
	base_name: 'Radio',
	base_description: 'A standard radio.',
	source_file: 'tools/lore_editor/content/overrides/items.json',
	category: 'items',
	field_profile: 'atom_like',
	status: 'overridden',
	base_status: 'overridden',
	approved: true,
	has_override: true,
	record_hash: HASH,
	raw: { id: 'items.radio', type_path: '/obj/item/radio', name: 'Radio override' },
	groups: ['items'],
	group_labels: ['Items'],
	group_match_reasons: {},
	issues: [],
	directional: false,
	redundant: false,
	suppression_reasons: [],
	icon_metadata: {},
	review: null,
} as ReviewEntry;

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

afterEach(() => {
	vi.restoreAllMocks();
	document.body.replaceChildren();
});

describe('Lore Editor authoring controls', () => {
	it('keeps assignment checkboxes content-sized beside their labels', async () => {
		vi.spyOn(api, 'get').mockResolvedValue({
			groups: [{
				id: 'items',
				label: 'Items',
				color: '#9614d0',
				count: 1,
				keywords: [],
				type_path_prefixes: [],
				keyword_scope: [],
				record_hash: HASH,
			}],
			assignments: {},
			assignment_record_hashes: {},
			counts: {},
		});
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ReviewActions entry={entry} reviewerName="Zoe" onDirtyChange={vi.fn()} onReload={vi.fn()} />, host);
		await settle();

		const checkbox = host.querySelector<HTMLInputElement>('fieldset input[type="checkbox"]')!;
		expect(checkbox.className).toMatch(/compactCheckbox/);
		dispose();
	});

	it('validates and saves an override with its expected record hash', async () => {
		vi.spyOn(api, 'get').mockImplementation((path: string) => Promise.resolve(
			path.startsWith('/api/lore/definition') ? { path: null, line: null }
				: path === '/api/entity-files' ? { files: ['tools/lore_editor/content/overrides/items.json'] }
					: { files: [] },
		));
		const post = vi.spyOn(api, 'post').mockResolvedValue({ valid: true, issues: [] });
		const put = vi.spyOn(api, 'put').mockResolvedValue({
			saved: true,
			created: false,
			entry: entry.raw,
			record_hash: HASH,
			issues: [],
			projection: { current: true },
		});
		const reload = vi.fn();
		const dirty = vi.fn();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <EntryEditor entry={entry} onDirtyChange={dirty} onReload={reload} />, host);
		await settle();

		const name = [...host.querySelectorAll('label')].find((label) => label.textContent?.includes('Name override'))!
			.querySelector<HTMLInputElement>('input')!;
		name.value = 'Updated radio';
		name.dispatchEvent(new InputEvent('input', { bubbles: true }));
		host.querySelector('form')!.dispatchEvent(new SubmitEvent('submit', { bubbles: true, cancelable: true }));
		await settle();
		await settle();

		expect(post).toHaveBeenCalledWith('/api/validate', expect.objectContaining({
			entries: [expect.objectContaining({ id: 'items.radio', name: 'Updated radio' })],
		}));
		expect(put).toHaveBeenCalledWith('/api/entries/items.radio', expect.objectContaining({
			expected_record_hash: HASH,
		}));
		expect(reload).toHaveBeenCalledWith('/obj/item/radio');
		expect(dirty).toHaveBeenCalledWith(true);
		dispose();
	});

	it('pins the selected catalog target in shared references', async () => {
		vi.spyOn(api, 'get').mockResolvedValue({ files: [] });
		const post = vi.spyOn(api, 'post').mockResolvedValue({
			id: 'reference-1',
			tool: 'lore-editor',
			kind: 'catalog_target',
			key: entry.type_path,
			label: entry.name,
			created_at: '2026-08-22T10:00:00+00:00',
		});
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <EntryEditor entry={entry} onDirtyChange={vi.fn()} onReload={vi.fn()} />, host);
		await settle();

		[...host.querySelectorAll('button')].find((button) => button.textContent === 'Add to references')!.click();
		await settle();
		expect(post).toHaveBeenCalledWith('/api/references', {
			tool: 'lore-editor',
			kind: 'catalog_target',
			key: entry.type_path,
			label: entry.name,
		});
		dispose();
	});

	it('shows current and proposed records instead of overwriting a conflict', async () => {
		vi.spyOn(api, 'get').mockResolvedValue({ groups: [], assignments: {}, assignment_record_hashes: {}, counts: {} });
		vi.spyOn(api, 'put').mockRejectedValue(new ApiError('changed', 409, {
			code: 'record_conflict',
			record_id: '/obj/item/radio',
			current: { status: 'reviewed', notes: 'Other writer' },
			proposed: { status: 'needs-attention', notes: 'Mine' },
		}));
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ReviewActions entry={entry} reviewerName="Zoe" onDirtyChange={vi.fn()} onReload={vi.fn()} />, host);
		await settle();
		[...host.querySelectorAll('button')].find((button) => button.textContent === 'Needs attention')!.click();
		await settle();

		expect(api.put).toHaveBeenCalledWith('/api/reviews/%2Fobj%2Fitem%2Fradio', expect.objectContaining({
			status: 'needs-attention',
			reviewed_by: 'Zoe',
		}));
		expect(host.querySelector('[role="alertdialog"]')?.textContent).toContain('Other writer');
		expect(host.querySelector('[role="alertdialog"]')?.textContent).toContain('Mine');
		expect(document.activeElement).toBe(host.querySelector('#record-conflict-title'));
		dispose();
	});

	it('reports an edited review note as unsaved state', async () => {
		vi.spyOn(api, 'get').mockResolvedValue({ groups: [], assignments: {}, assignment_record_hashes: {}, counts: {} });
		const dirty = vi.fn();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ReviewActions entry={entry} reviewerName="Zoe" onDirtyChange={dirty} onReload={vi.fn()} />, host);
		await settle();

		const notes = [...host.querySelectorAll('label')].find((label) => label.textContent?.includes('Review notes'))!
			.querySelector<HTMLTextAreaElement>('textarea')!;
		notes.value = 'Unsaved writer note';
		notes.dispatchEvent(new InputEvent('input', { bubbles: true }));
		expect(dirty).toHaveBeenLastCalledWith(true);
		dispose();
	});

	it('creates a group through the typed configuration workflow without axe violations', async () => {
		vi.spyOn(api, 'get').mockResolvedValue({ groups: [], assignments: {}, assignment_record_hashes: {}, counts: {} });
		const post = vi.spyOn(api, 'post').mockResolvedValue({
			group: { id: 'new-group', label: 'New Group', color: '#9614d0', record_hash: HASH },
			issues: [],
			projection: { current: true },
		});
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <GroupManager onDirtyChange={vi.fn()} />, host);
		await settle();
		[...host.querySelectorAll('button')].find((button) => button.textContent === 'New group')!.click();
		const inputs = host.querySelectorAll<HTMLInputElement>('form input');
		inputs[0]!.value = 'new-group';
		inputs[0]!.dispatchEvent(new InputEvent('input', { bubbles: true }));
		inputs[1]!.value = 'New Group';
		inputs[1]!.dispatchEvent(new InputEvent('input', { bubbles: true }));
		host.querySelector('form')!.dispatchEvent(new SubmitEvent('submit', { bubbles: true, cancelable: true }));
		await settle();
		expect(post).toHaveBeenCalledWith('/api/groups', expect.objectContaining({ id: 'new-group', label: 'New Group' }));
		const accessibility = await axe.run(host, {
			rules: { region: { enabled: false }, 'color-contrast': { enabled: false } },
		});
		expect(accessibility.violations).toEqual([]);
		dispose();
	});
});

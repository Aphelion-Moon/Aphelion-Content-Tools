import { Route, Router, useNavigate } from '@solidjs/router';
import { For, Suspense, onMount } from 'solid-js';
import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '~/lib/api';
import { dismissParsec } from '~/lib/parsec/coordinator';
import { appState } from '~/store/appStore';
import LoreEditorPage from './LoreEditorPage';
import type { ReviewEntry } from './reviewFeed';

const editorLoading = vi.hoisted(() => ({ promise: null as Promise<void> | null }));

vi.mock('./ReviewList', () => ({
	default: (props: {
		feed: { entries: () => readonly ReviewEntry[]; reload: () => void };
		onSelect: (entry: ReviewEntry) => void;
	}) => {
		onMount(() => props.feed.reload());
		return (
			<div>
				<For each={props.feed.entries()}>{(entry) => (
					<button type="button" onClick={() => props.onSelect(entry)}>Select {entry.name}</button>
				)}</For>
			</div>
		);
	},
}));

vi.mock('./EntryEditor', async () => {
	const { createResource } = await import('solid-js');
	return {
		default: (props: { entry: ReviewEntry }) => {
			if (!editorLoading.promise) return <p data-testid="selected-name">{props.entry.name}</p>;
			const [ready] = createResource(() => editorLoading.promise!.then(() => true));
			return <p data-testid="selected-name">{ready() ? props.entry.name : ''}</p>;
		},
	};
});

vi.mock('./ReviewActions', () => ({
	default: (props: { entry: ReviewEntry; reviewerName: string; onReload: (typePath: string) => void }) => (
		<>
			<span data-testid="reviewer-prop">{props.reviewerName}</span>
			<button type="button" onClick={() => props.onReload(props.entry.type_path)}>Reload selected</button>
		</>
	),
}));

vi.mock('./GroupManager', () => ({ default: () => <p>Groups</p> }));

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
	groups: [],
	group_labels: [],
	group_match_reasons: {},
	issues: [],
	directional: false,
	redundant: false,
	suppression_reasons: [],
	icon_metadata: {},
	review: null,
} as ReviewEntry;

function response(entries: readonly ReviewEntry[]) {
	return {
		entries,
		matched_entry_count: entries.length,
		returned_entry_count: entries.length,
		has_more: false,
		offset: 0,
		limit: 200,
		catalog_count: entries.length,
		approved_count: entries.length,
		review_count: 0,
		status_counts: {},
		group_counts: {},
		visible_entry_count: entries.length,
		visible_catalog_count: 0,
		suppressed_counts: {},
		groups: [],
		issues: [],
	};
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

afterEach(() => {
	dismissParsec();
	editorLoading.promise = null;
	vi.restoreAllMocks();
	window.localStorage.clear();
	document.body.replaceChildren();
});

describe('Lore Editor selected record refresh', () => {
	it('follows a new search deep link while the same tool stays mounted', async () => {
		const second = { ...entry, id: 'items.pen', type_path: '/obj/item/pen', name: 'Pen' };
		vi.spyOn(api, 'get').mockImplementation((path) => Promise.resolve(response(path.includes('pen') ? [second] : [entry])));
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Router><Route path="*" component={() => {
			const navigate = useNavigate();
			return <><button onClick={() => navigate('/lore-editor?type_path=%2Fobj%2Fitem%2Fpen', { scroll: false })}>Follow pen link</button><LoreEditorPage /></>;
		}} /></Router>, host);
		await settle(); await settle();
		[...host.querySelectorAll('button')].find((button) => button.textContent === 'Follow pen link')!.click();
		await settle(); await settle();
		expect(host.querySelector('[data-testid="selected-name"]')?.textContent).toBe('Pen');
		dispose();
	});
	it('keeps the workspace mounted while selected-record resources load', async () => {
		let finishLoading!: () => void;
		editorLoading.promise = new Promise<void>((resolve) => {
			finishLoading = resolve;
		});
		vi.spyOn(api, 'get').mockResolvedValue(response([entry]));
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(
			() => (
				<Router>
					<Route path="*" component={() => (
						<Suspense fallback={<p>Whole Lore route replaced</p>}>
							<LoreEditorPage />
						</Suspense>
					)} />
				</Router>
			),
			host,
		);
		await settle();
		await settle();

		[...host.querySelectorAll('button')].find((button) => button.textContent === 'Select Radio override')!.click();
		await settle();

		expect(host.textContent).not.toContain('Whole Lore route replaced');
		expect(host.querySelector('[aria-label="Lore review queue"]')).not.toBeNull();
		expect(host.querySelector('[role="progressbar"]')?.getAttribute('aria-label')).toBe('Loading Radio override');
		expect(appState.parsecFeedback).toBeNull();
		await vi.waitFor(() => {
				expect(appState.parsecFeedback).toMatchObject({
				kind: 'info',
				tool: 'lore-editor',
				animation: 'fetch',
				dedupeKey: 'lore-entry:items.radio',
			});
			expect(appState.parsecFeedback?.text).toContain('Still fetching');
		});
		finishLoading();
		await settle();
		dispose();
	});

	it('keeps the review queue and selected authoring surface in one workspace', async () => {
		vi.spyOn(api, 'get').mockResolvedValue(response([entry]));
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(
			() => <Router><Route path="*" component={LoreEditorPage} /></Router>,
			host,
		);
		await settle();
		await settle();

		await vi.waitFor(() => {
			expect([...host.querySelectorAll('button')].some((button) => button.textContent === 'Select Radio override')).toBe(true);
		});
		[...host.querySelectorAll('button')].find((button) => button.textContent === 'Select Radio override')!.click();

		const workspace = host.querySelector('[aria-label="Lore review workspace"]');
		expect(workspace).not.toBeNull();
		expect(workspace!.querySelector('[aria-label="Lore review queue"]')).not.toBeNull();
		expect(workspace!.querySelector('[aria-label="Lore authoring surface"]')).not.toBeNull();
		expect(workspace!.querySelector('[data-testid="selected-name"]')?.textContent).toBe('Radio override');
		dispose();
	});

	it('keeps section tabs in the authoring pane without unmounting the review queue', async () => {
		vi.spyOn(api, 'get').mockResolvedValue(response([entry]));
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(
			() => <Router><Route path="*" component={LoreEditorPage} /></Router>,
			host,
		);
		await settle();
		await settle();

		const authoring = host.querySelector('[aria-label="Lore authoring surface"]');
		expect(authoring?.querySelector('[role="tablist"]')).not.toBeNull();
		[...host.querySelectorAll('button')].find((button) => button.textContent === 'Group configuration')!.click();
		expect(host.querySelector('[aria-label="Lore review queue"]')).not.toBeNull();
		expect(authoring?.textContent).toContain('Groups');
		dispose();
	});

	it('keeps the reviewer identity in the workspace header across selection and reload', async () => {
		vi.spyOn(api, 'get').mockResolvedValue(response([entry]));
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(
			() => <Router><Route path="*" component={LoreEditorPage} /></Router>,
			host,
		);
		await settle();
		await settle();

		const reviewer = [...host.querySelectorAll('label')]
			.find((label) => label.textContent?.includes('Reviewer'))!
			.querySelector<HTMLInputElement>('input')!;
		reviewer.value = 'Zoe';
		reviewer.dispatchEvent(new InputEvent('input', { bubbles: true }));
		expect(window.localStorage.getItem('aphelion-lore-reviewer')).toBe('Zoe');

		[...host.querySelectorAll('button')].find((button) => button.textContent === 'Select Radio override')!.click();
		expect(host.querySelector('[data-testid="reviewer-prop"]')?.textContent).toBe('Zoe');
		[...host.querySelectorAll('button')].find((button) => button.textContent === 'Reload selected')!.click();
		await settle();
		await settle();
		expect(reviewer.value).toBe('Zoe');
		dispose();
	});

	it('replaces the selected detail with the freshly reloaded version of the same record', async () => {
		const updated = {
			...entry,
			name: 'Updated radio',
			record_hash: 'b'.repeat(64),
			raw: { ...entry.raw, name: 'Updated radio' },
		} as ReviewEntry;
		vi.spyOn(api, 'get')
			.mockResolvedValueOnce(response([entry]))
			.mockResolvedValueOnce(response([updated]));
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(
			() => <Router><Route path="*" component={LoreEditorPage} /></Router>,
			host,
		);
		await settle();
		await settle();

		await vi.waitFor(() => {
			expect([...host.querySelectorAll('button')].some((button) => button.textContent === 'Select Radio override')).toBe(true);
		});
		[...host.querySelectorAll('button')].find((button) => button.textContent === 'Select Radio override')!.click();
		expect(host.querySelector('[data-testid="selected-name"]')?.textContent).toBe('Radio override');
		[...host.querySelectorAll('button')].find((button) => button.textContent === 'Reload selected')!.click();
		await settle();
		await settle();

		expect(host.querySelector('[data-testid="selected-name"]')?.textContent).toBe('Updated radio');
		dispose();
	});
});

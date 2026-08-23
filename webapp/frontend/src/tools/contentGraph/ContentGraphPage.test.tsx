import { Route, Router } from '@solidjs/router';
import axe from 'axe-core';
import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '~/lib/api';
import { appState, setSelectedContext } from '~/store/appStore';
import ContentGraphPage from './ContentGraphPage';

const graphResponse = {
	scanned: true,
	manifest: {
		format_version: 1,
		snapshot_sha256: 'a'.repeat(64),
		game_repo_revision: '0123456789abcdef',
		generated_at: '2026-08-22T00:00:00Z',
		node_count: 4,
		edge_count: 2,
		module_count: 1,
		master_files_count: 0,
		marker_count: 1,
		file_count: 1,
		directory_count: 1,
		reference_count: 0,
	},
	graph: {
		nodes: [
			{ id: 'dir:.', kind: 'directory', path: '.', name: 'root' },
			{ id: 'file:notes.md', kind: 'file', path: 'notes.md', name: 'notes.md' },
			{ id: 'module:aphelion:radio', kind: 'module', owner: 'aphelion', module_id: 'radio', path: 'modular_aphelion/modules/radio' },
			{ id: 'core_file:code/radio.dm', kind: 'core_file', path: 'code/radio.dm', marker_count: 1 },
		],
		edges: [
			{ source: 'dir:.', target: 'file:notes.md', relation: 'contains' },
			{ source: 'module:aphelion:radio', target: 'core_file:code/radio.dm', relation: 'marker_edit' },
		],
		unresolved_markers: [],
		counts: {
			module_count: 1, master_files_count: 0, core_file_count: 1, marker_count: 1,
			unresolved_marker_count: 0, file_count: 1, directory_count: 1, reference_count: 0,
		},
	},
} as const;

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

afterEach(() => {
	setSelectedContext(null);
	window.history.replaceState({}, '', '/');
	vi.restoreAllMocks();
	document.body.replaceChildren();
});

describe('Content Graph page', () => {
	it('loads the typed graph and starts in the curated semantic scope', async () => {
		vi.spyOn(api, 'get').mockImplementation((path: string) => {
			if (path === '/api/graph') return Promise.resolve(graphResponse);
			if (path.startsWith('/api/graph/modules')) return Promise.resolve({ scanned: true, modules: [] });
			if (path === '/api/graph/unresolved') return Promise.resolve({ scanned: true, unresolved_markers: [] });
			return Promise.reject(new Error(`Unexpected GET ${path}`));
		});
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Router><Route path="*" component={ContentGraphPage} /></Router>, host);
		await settle();
		await settle();

		expect(host.textContent).toContain('4 nodes · 2 edges · revision 0123456789ab');
		expect(host.textContent).toContain('2 of 4 nodes in scope');
		expect(host.querySelector('[data-testid="content-graph-canvas"]')).not.toBeNull();
		expect(host.textContent).toContain('Accessible node list (2 visible)');
		const accessibility = await axe.run(host, { rules: { 'color-contrast': { enabled: false } } });
		expect(accessibility.violations).toEqual([]);
		dispose();
	});

	it('adds the whole catalog to scope without conflating scope and visibility filters', async () => {
		vi.spyOn(api, 'get').mockImplementation((path: string) => {
			if (path === '/api/graph') return Promise.resolve(graphResponse);
			if (path.startsWith('/api/graph/modules')) return Promise.resolve({ scanned: true, modules: [] });
			if (path === '/api/graph/unresolved') return Promise.resolve({ scanned: true, unresolved_markers: [] });
			return Promise.reject(new Error(`Unexpected GET ${path}`));
		});
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Router><Route path="*" component={ContentGraphPage} /></Router>, host);
		await settle();
		await settle();

		[...host.querySelectorAll('button')].find((button) => button.textContent === 'Tick all')!.click();
		await settle();
		expect(host.textContent).toContain('4 of 4 nodes in scope');
		expect(host.textContent).toContain('4 visible');
		dispose();
	});

	it('restores shared selected context from an exact node deep link', async () => {
		vi.spyOn(api, 'get').mockImplementation((path: string) => {
			if (path === '/api/graph') return Promise.resolve(graphResponse);
			if (path.startsWith('/api/graph/modules')) return Promise.resolve({ scanned: true, modules: [] });
			if (path === '/api/graph/unresolved') return Promise.resolve({ scanned: true, unresolved_markers: [] });
			return Promise.reject(new Error(`Unexpected GET ${path}`));
		});
		window.history.replaceState({}, '', '/graph?selected=module%3Aaphelion%3Aradio');
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Router><Route path="*" component={ContentGraphPage} /></Router>, host);
		await settle();
		await settle();

		expect(host.textContent).toContain('radio');
		expect(appState.selectedContext).toMatchObject({
			tool: 'graph',
			record_id: 'module:aphelion:radio',
			module: 'radio',
		});
		dispose();
	});
});

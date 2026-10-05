import axe from 'axe-core';
import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '~/lib/api';
import { setActiveRuns } from '~/store/appStore';
import ToolRunner from './ToolRunner';

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

afterEach(() => {
	setActiveRuns([]);
	vi.restoreAllMocks();
	vi.useRealTimers();
	document.body.replaceChildren();
});

describe('ToolRunner', () => {
	it('offers the release catalog directly and keeps the local probe under advanced actions', async () => {
		vi.spyOn(api, 'get').mockResolvedValue({ tools: [
			{ id: 'catalog-reload', label: 'Load release catalog', description: 'Load the verified release catalog.' },
			{ id: 'refresh-validate', label: 'Refresh and validate', description: 'Build local authoring data.' },
		] });
		const post = vi.spyOn(api, 'post').mockImplementation(() => new Promise(() => undefined));
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ToolRunner />, host);
		await settle();
		const release = [...host.querySelectorAll('button')].find((button) => button.textContent === 'Load release catalog')!;
		const local = [...host.querySelectorAll('button')].find((button) => button.textContent === 'Refresh and validate')!;
		expect(release.closest('details')).toBeNull();
		expect(local.closest('details')).not.toBeNull();
		expect(release.type).toBe('button');
		release.focus();
		expect(document.activeElement).toBe(release);
		const accessibility = await axe.run(host, { rules: { 'color-contrast': { enabled: false } } });
		expect(accessibility.violations).toEqual([]);
		release.click();
		expect(post).toHaveBeenCalledWith('/api/tools/catalog-reload');
		dispose();
	});
	it('does not restart polling when an in-flight response arrives after unmount', async () => {
		vi.useFakeTimers();
		setActiveRuns([{ run_id: 'late-run', tool_id: 'validate', status: 'running', queued_at: 100 }]);
		let resolve!: (value: unknown) => void;
		const get = vi.spyOn(api, 'get').mockImplementation((path: string) => path === '/api/tools'
			? Promise.resolve({ tools: [] }) : new Promise((done) => { resolve = done; }));
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ToolRunner />, host);
		await vi.advanceTimersByTimeAsync(1);
		dispose();
		resolve({ run_id: 'late-run', tool_id: 'validate', status: 'running', output: 'Still running' });
		await vi.advanceTimersByTimeAsync(1000);
		expect(get.mock.calls.filter(([path]) => path === '/api/tools/runs/late-run')).toHaveLength(1);
	});
	it('reattaches to the repository active run after route navigation', async () => {
		setActiveRuns([{
			run_id: 'run-refresh-1',
			tool_id: 'refresh-validate',
			tool_label: 'Refresh catalog and validate',
			status: 'running',
			queued_at: 100,
		}]);
		vi.spyOn(api, 'get').mockImplementation((path: string) => {
			if (path === '/api/tools') return Promise.resolve({ tools: [] });
			if (path === '/api/tools/runs/run-refresh-1') {
				return Promise.resolve({
					run_id: 'run-refresh-1',
					tool_id: 'refresh-validate',
					status: 'running',
					queued_at: 100,
					output: 'Catalog: 300/900 records',
					log_path: 'logs/run-refresh-1.log',
				});
			}
			return Promise.reject(new Error(`Unexpected GET ${path}`));
		});

		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ToolRunner />, host);
		await settle();
		await settle();

		expect(host.textContent).toContain('Catalog: 300/900 records');
		expect(host.textContent).toContain('logs/run-refresh-1.log');
		expect([...host.querySelectorAll('button')].some((button) => button.textContent === 'Stop')).toBe(true);
		dispose();
	});

	it('starts a tool only once while the first start request is pending', async () => {
		let resolveStart!: (value: unknown) => void;
		const post = vi.spyOn(api, 'post').mockImplementation(() => new Promise((resolve) => { resolveStart = resolve; }));
		vi.spyOn(api, 'get').mockImplementation((path: string) => path === '/api/tools'
			? Promise.resolve({ tools: [{ id: 'validate', label: 'Validate', description: 'Validate the catalog.' }] })
			: Promise.reject(new Error(`Unexpected GET ${path}`)));
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ToolRunner />, host);
		await settle();

		const button = [...host.querySelectorAll('button')].find((candidate) => candidate.textContent === 'Validate')!;
		button.click();
		button.click();
		expect(post).toHaveBeenCalledTimes(1);

		resolveStart({ run_id: 'validate-once', tool_id: 'validate', status: 'succeeded', queued_at: 100, output: '', log_path: null });
		dispose();
	});
});

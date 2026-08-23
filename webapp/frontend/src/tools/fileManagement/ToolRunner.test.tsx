import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '~/lib/api';
import { setActiveRuns } from '~/store/appStore';
import ToolRunner from './ToolRunner';

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

afterEach(() => {
	setActiveRuns([]);
	vi.restoreAllMocks();
	document.body.replaceChildren();
});

describe('ToolRunner', () => {
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
});

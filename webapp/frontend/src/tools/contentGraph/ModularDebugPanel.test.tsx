import { Router, Route } from '@solidjs/router';
import { render } from 'solid-js/web';
import { afterEach, expect, it, vi } from 'vitest';
import { api } from '~/lib/api';
import ModularDebugPanel from './ModularDebugPanel';

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
afterEach(() => { vi.restoreAllMocks(); document.body.replaceChildren(); });

it('previews a marker change before applying the server-held stage', async () => {
	vi.spyOn(api, 'get').mockImplementation((path) => Promise.resolve(path.includes('/unresolved') ? {
		scanned: true, unresolved_markers: [{ core_file: 'code/test.dm', line_number: 2, raw_label: 'old', line_text: '// NOVA EDIT ADDITION - old', owner: 'nova', edit_type: 'ADDITION', attribution: 'unresolved' }],
	} : { scanned: true, modules: [] }));
	const post = vi.spyOn(api, 'post').mockResolvedValue({ stage_id: 'stage-1', preview: '-old\n+new', base_revision: 'abc', paths: ['code/test.dm'] });
	const rescan = vi.fn(async () => {});
	const host = document.createElement('div'); document.body.append(host);
	const dispose = render(() => <Router><Route path="*" component={() => <ModularDebugPanel scanned refreshToken={0} onRescan={rescan} />} /></Router>, host);
	try {
		await settle(); await settle();
		const click = (text: string) => [...host.querySelectorAll('button')].find((button) => button.textContent === text)!.click();
		click('Edit label'); click('Preview change'); await settle();
		expect(post).toHaveBeenCalledTimes(1);
		expect(host.textContent).toContain('-old');
		expect(rescan).not.toHaveBeenCalled();
		click('Apply change'); await settle();
		expect(post).toHaveBeenLastCalledWith('/api/graph/markers/apply', { stage_id: 'stage-1' });
		expect(rescan).toHaveBeenCalledTimes(1);
	} finally { dispose(); }
});

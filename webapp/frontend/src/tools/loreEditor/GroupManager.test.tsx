import { render } from 'solid-js/web';
import { afterEach, expect, it, vi } from 'vitest';
import { api } from '~/lib/api';
import GroupManager from './GroupManager';

afterEach(() => { vi.restoreAllMocks(); document.body.replaceChildren(); });
it('reports unsaved group edits and refuses replacing the draft when discard is declined', async () => {
	vi.spyOn(api, 'get').mockResolvedValue({ groups: [] });
	const dirty = vi.fn();
	const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
	const host = document.createElement('div'); document.body.append(host);
	const dispose = render(() => <GroupManager onDirtyChange={dirty} />, host);
	try {
		await new Promise((resolve) => setTimeout(resolve, 0));
		const create = [...host.querySelectorAll('button')].find((button) => button.textContent === 'New group')!;
		create.click();
		const input = host.querySelector('input')!;
		input.value = 'draft-group'; input.dispatchEvent(new InputEvent('input', { bubbles: true }));
		expect(dirty).toHaveBeenLastCalledWith(true);
		create.click();
		expect(confirm).toHaveBeenCalled();
		expect(input.value).toBe('draft-group');
	} finally { dispose(); }
	 expect(dirty).toHaveBeenLastCalledWith(false);
});

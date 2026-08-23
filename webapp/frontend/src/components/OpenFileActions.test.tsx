import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '~/lib/api';
import OpenFileActions from './OpenFileActions';

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

afterEach(() => {
	vi.restoreAllMocks();
	document.body.replaceChildren();
});

describe('open file actions', () => {
	it('opens a source in the editor, Explorer, and GitHub at its exact line', async () => {
		const post = vi.spyOn(api, 'post').mockResolvedValue({ opened: true });
		vi.spyOn(api, 'get').mockResolvedValue({ url: 'https://github.com/example/repo/blob/sha/file.dm' });
		const open = vi.spyOn(window, 'open').mockReturnValue(null);
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<OpenFileActions label="Original" repository="game" path="code/items/radio.dm" line={42} />
		), host);

		for (const label of ['Editor', 'Explorer', 'GitHub']) {
			[...host.querySelectorAll('button')].find((button) => button.textContent === label)!.click();
			await settle();
		}
		expect(post).toHaveBeenNthCalledWith(1, '/api/git/open-file', {
			repository: 'game', path: 'code/items/radio.dm', target: 'editor',
		});
		expect(post).toHaveBeenNthCalledWith(2, '/api/git/open-file', {
			repository: 'game', path: 'code/items/radio.dm', target: 'explorer',
		});
		expect(open).toHaveBeenCalledWith(
			'https://github.com/example/repo/blob/sha/file.dm#L42',
			'_blank',
			'noopener',
		);
		dispose();
	});
});

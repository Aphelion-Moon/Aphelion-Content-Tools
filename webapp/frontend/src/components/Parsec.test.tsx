import { render } from 'solid-js/web';
import { afterEach, describe, expect, it } from 'vitest';
import { announceSuccess } from '~/lib/notify';
import Parsec from './Parsec';

afterEach(() => {
	document.body.replaceChildren();
});

describe('Parsec', () => {
	it('shows application announcements in the visible speech bubble', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);

		announceSuccess('Catalog refresh finished.', 'file-management');

		expect(host.textContent).toContain('Catalog refresh finished.');
		dispose();
	});
});

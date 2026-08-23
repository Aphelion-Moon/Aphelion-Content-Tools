import { Route, Router } from '@solidjs/router';
import axe from 'axe-core';
import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import AppShell from './AppShell';

afterEach(() => {
	vi.restoreAllMocks();
	document.body.replaceChildren();
});

describe('application shell accessibility', () => {
	it('provides landmarks, current navigation, and a keyboard skip link without axe violations', async () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(
			() => (
				<Router>
					<Route path="*" component={() => <AppShell><h2>Page content</h2></AppShell>} />
				</Router>
			),
			host,
		);
		expect(host.querySelector('a[href="#main-content"]')?.textContent).toContain('Skip');
		expect(host.querySelector('main#main-content')).not.toBeNull();
		expect(host.querySelector('nav[aria-label="Tools"]')).not.toBeNull();
		const accessibility = await axe.run(host, {
			rules: { 'color-contrast': { enabled: false } },
		});
		expect(accessibility.violations).toEqual([]);
		dispose();
	});
});

import axe from 'axe-core';
import { createSignal } from 'solid-js';
import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ReviewList from './ReviewList';
import type { createReviewFeed } from './reviewFeed';

afterEach(() => {
	vi.restoreAllMocks();
	document.body.replaceChildren();
});

describe('review feed accessibility', () => {
	it('labels the virtual list and exposes loading progress as status', async () => {
		const [entries] = createSignal([]);
		const feed = {
			entries,
			meta: () => null,
			loading: () => false,
			error: () => null,
			filters: () => ({ query: '', statuses: [], groups: [], sort: 'name', includeDirectional: false, includeRedundant: false }),
			setFilters: vi.fn(),
			reload: vi.fn(),
			loadMore: vi.fn(),
			matchedCount: () => 0,
			isExhausted: () => true,
		} as unknown as ReturnType<typeof createReviewFeed>;
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ReviewList feed={feed} selectedId={null} onSelect={vi.fn()} />, host);

		expect(host.querySelector('[role="listbox"]')?.getAttribute('aria-label')).toBe('Lore catalog entries');
		expect(host.querySelector('[role="status"]')).not.toBeNull();
		const accessibility = await axe.run(host, {
			rules: { region: { enabled: false }, 'color-contrast': { enabled: false } },
		});
		expect(accessibility.violations).toEqual([]);
		dispose();
	});
});

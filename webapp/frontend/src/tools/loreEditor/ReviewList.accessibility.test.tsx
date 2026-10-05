import axe from 'axe-core';
import { createSignal } from 'solid-js';
import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ReviewList from './ReviewList';
import type { createReviewFeed } from './reviewFeed';

vi.mock('@tanstack/solid-virtual', () => ({
	createVirtualizer: (options: { readonly count: number }) => ({
		getVirtualItems: () => Array.from({ length: options.count }, (_, index) => ({
			index,
			key: index,
			start: index * 62,
			size: 62,
		})),
		getTotalSize: () => options.count * 62,
	}),
}));

afterEach(() => {
	vi.restoreAllMocks();
	document.body.replaceChildren();
});

describe('review feed accessibility', () => {
	it('keeps the paging action compact while announcing its page size', () => {
		const [entries] = createSignal([]);
		const feed = {
			entries,
			loading: () => false,
			reload: vi.fn(),
			loadMore: vi.fn(),
			matchedCount: () => 200,
			isExhausted: () => false,
		} as unknown as ReturnType<typeof createReviewFeed>;
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ReviewList feed={feed} selectedId={null} onSelect={vi.fn()} />, host);
		const loadMore = host.querySelector<HTMLButtonElement>('[aria-label="Load 200 more"]')!;

		expect(loadMore.textContent).toBe('Load more');
		dispose();
	});

	it('activates a focused catalog option with Enter or Space', () => {
		const entry = {
			id: 'items.radio',
			type_path: '/obj/item/radio',
			name: 'Radio',
			status: 'unreviewed',
			groups: [],
			group_labels: [],
			issues: [],
		} as never;
		const [entries] = createSignal([entry]);
		const feed = {
			entries,
			loading: () => false,
			reload: vi.fn(),
			loadMore: vi.fn(),
			matchedCount: () => 1,
			isExhausted: () => true,
		} as unknown as ReturnType<typeof createReviewFeed>;
		const onSelect = vi.fn();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ReviewList feed={feed} selectedId={null} onSelect={onSelect} />, host);
		const option = host.querySelector<HTMLButtonElement>('[role="option"]')!;

		option.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
		option.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true, cancelable: true }));
		expect(onSelect).toHaveBeenNthCalledWith(1, entry);
		expect(onSelect).toHaveBeenNthCalledWith(2, entry);
		dispose();
	});

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

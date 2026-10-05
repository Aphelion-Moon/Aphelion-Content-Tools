import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ReviewFilters from './ReviewFilters';
import { DEFAULT_FILTERS, type createReviewFeed } from './reviewFeed';

afterEach(() => {
	vi.restoreAllMocks();
	document.body.replaceChildren();
});

function renderFilters() {
	const setFilters = vi.fn();
	const feed = {
		filters: () => DEFAULT_FILTERS,
		setFilters,
		meta: () => ({
			catalog_count: 100,
			approved_count: 12,
			matched_entry_count: 80,
			suppressed_counts: { directional: 4, redundant: 6 },
			groups: [
				{ id: 'nanotrasen', label: 'Nanotrasen' },
				{ id: 'languages', label: 'Languages' },
			],
		}),
	} as unknown as ReturnType<typeof createReviewFeed>;
	const host = document.createElement('div');
	document.body.append(host);
	const dispose = render(() => <ReviewFilters feed={feed} />, host);
	return { dispose, host, setFilters };
}

function changeCheckbox(host: HTMLElement, labelText: string, checked: boolean) {
	const input = [...host.querySelectorAll('label')]
		.find((label) => label.textContent?.includes(labelText))!
		.querySelector<HTMLInputElement>('input')!;
	input.checked = checked;
	input.dispatchEvent(new Event('change', { bubbles: true }));
}

describe('Lore review filters', () => {
	it('keeps dense filter groups in compact disclosures above the catalog', () => {
		const { dispose, host } = renderFilters();
		const disclosures = [...host.querySelectorAll('details')];
		expect(disclosures.map((details) => details.querySelector('summary')?.textContent)).toEqual([
			'Status (any)',
			'Groups (any)',
			'Visibility',
		]);
		expect(disclosures.every((details) => !details.open)).toBe(true);
		dispose();
	});

	it('updates search, sort, status, and visibility through the review feed', () => {
		const { dispose, host, setFilters } = renderFilters();
		const search = host.querySelector<HTMLInputElement>('input[type="search"]')!;
		search.value = 'radio';
		search.dispatchEvent(new InputEvent('input', { bubbles: true }));
		expect(setFilters).toHaveBeenLastCalledWith({ ...DEFAULT_FILTERS, query: 'radio' });

		const sort = host.querySelector<HTMLSelectElement>('select')!;
		expect([...sort.options].map((option) => option.value)).toEqual(['name', 'type_path', 'status', 'reviewed_at']);
		sort.value = 'reviewed_at';
		sort.dispatchEvent(new Event('change', { bubbles: true }));
		expect(setFilters).toHaveBeenLastCalledWith({ ...DEFAULT_FILTERS, sort: 'reviewed_at' });

		changeCheckbox(host, 'Needs attention', true);
		expect(setFilters).toHaveBeenLastCalledWith({ ...DEFAULT_FILTERS, statuses: ['needs-attention'] });
		changeCheckbox(host, 'Include directional', true);
		expect(setFilters).toHaveBeenLastCalledWith({ ...DEFAULT_FILTERS, includeDirectional: true });
		changeCheckbox(host, 'Include redundant', true);
		expect(setFilters).toHaveBeenLastCalledWith({ ...DEFAULT_FILTERS, includeRedundant: true });
		dispose();
	});

	it('supports individual, all, and cleared group filters plus a full reset', () => {
		const { dispose, host, setFilters } = renderFilters();
		changeCheckbox(host, 'Nanotrasen', true);
		expect(setFilters).toHaveBeenLastCalledWith({ ...DEFAULT_FILTERS, groups: ['nanotrasen'] });

		[...host.querySelectorAll('button')].find((button) => button.textContent === 'Select all')!.click();
		expect(setFilters).toHaveBeenLastCalledWith({ ...DEFAULT_FILTERS, groups: ['nanotrasen', 'languages'] });
		[...host.querySelectorAll('button')].find((button) => button.textContent === 'Clear groups')!.click();
		expect(setFilters).toHaveBeenLastCalledWith({ ...DEFAULT_FILTERS, groups: [] });
		[...host.querySelectorAll('button')].find((button) => button.textContent === 'Clear all filters')!.click();
		expect(setFilters).toHaveBeenLastCalledWith(DEFAULT_FILTERS);
		dispose();
	});
});

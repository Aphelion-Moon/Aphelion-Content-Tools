import { describe, expect, it } from 'vitest';
import { selectedOwnedPaths, toggleSelectedPath } from './commitSelection';

describe('commit selection', () => {
	it('starts empty and toggles paths explicitly', () => {
		expect(toggleSelectedPath([], 'tools/lore_editor/content/groups/items.json')).toEqual([
			'tools/lore_editor/content/groups/items.json',
		]);
		expect(
			toggleSelectedPath(['tools/lore_editor/content/groups/items.json'], 'tools/lore_editor/content/groups/items.json'),
		).toEqual([]);
	});

	it('never returns a selected path outside the owned change set', () => {
		expect(
			selectedOwnedPaths(
				['tools/lore_editor/content/groups/items.json', 'unrelated.txt'],
				[{ path: 'tools/lore_editor/content/groups/items.json' }],
			),
		).toEqual(['tools/lore_editor/content/groups/items.json']);
	});
});

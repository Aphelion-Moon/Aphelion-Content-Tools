import { describe, expect, it } from 'vitest';
import { buildGraphModel } from './model';

const raw = {
	nodes: [
		{ id: 'module:aphelion:radio', kind: 'module' as const, owner: 'aphelion' as const, module_id: 'radio', path: 'modular_aphelion/modules/radio' },
		{ id: 'core_file:code/radio.dm', kind: 'core_file' as const, path: 'code/radio.dm' },
	],
	edges: [
		{ source: 'module:aphelion:radio', target: 'core_file:code/radio.dm', relation: 'marker_edit' as const },
		{ source: 'missing', target: 'core_file:code/radio.dm', relation: 'contains' as const },
	],
};

describe('content graph model', () => {
	it('normalizes wire records, computes degree, and rejects dangling edges', () => {
		const model = buildGraphModel(raw);
		expect(model.nodes).toHaveLength(2);
		expect(model.edges).toHaveLength(1);
		expect(model.nodes.map((node) => node.degree)).toEqual([1, 1]);
		expect(model.nodeById.get('module:aphelion:radio')?.moduleId).toBe('radio');
	});

	it('produces the same positions for the same graph snapshot', () => {
		const first = buildGraphModel(raw, { seedShape: 'packed' });
		const second = buildGraphModel(raw, { seedShape: 'packed' });
		expect(first.nodes.map(({ id, x, y }) => ({ id, x, y }))).toEqual(
			second.nodes.map(({ id, x, y }) => ({ id, x, y })),
		);
	});
});

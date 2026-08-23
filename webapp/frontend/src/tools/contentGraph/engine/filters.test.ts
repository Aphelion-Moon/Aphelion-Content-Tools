import { describe, expect, it } from 'vitest';
import { applyVisibility } from './filters';
import { buildGraphModel } from './model';
import { ALL_KINDS, ALL_OWNERS, ALL_RELATIONS } from './types';

const model = buildGraphModel({
	nodes: [
		{ id: 'module:aphelion:radio', kind: 'module', owner: 'aphelion', module_id: 'radio' },
		{ id: 'module:nova:medical', kind: 'module', owner: 'nova', module_id: 'medical' },
		{ id: 'core_file:code/radio.dm', kind: 'core_file', path: 'code/radio.dm' },
	],
	edges: [
		{ source: 'module:aphelion:radio', target: 'core_file:code/radio.dm', relation: 'marker_edit' },
		{ source: 'module:nova:medical', target: 'core_file:code/radio.dm', relation: 'module_reference' },
	],
});

describe('content graph visibility filters', () => {
	it('hides nodes without changing force membership or positions', () => {
		const positions = model.nodes.map(({ id, x, y }) => ({ id, x, y }));
		const result = applyVisibility(model.nodes, model.edges, {
			kinds: new Set(ALL_KINDS),
			owners: new Set(['aphelion']),
			relations: new Set(ALL_RELATIONS),
			search: 'radio',
			degreeMin: 0,
			degreeMax: null,
		});
		expect(result.visibleNodes.map((node) => node.id).sort()).toEqual([
			'core_file:code/radio.dm',
			'module:aphelion:radio',
		]);
		expect(model.nodes.map(({ id, x, y }) => ({ id, x, y }))).toEqual(positions);
	});

	it('applies relation visibility independently from node visibility', () => {
		const result = applyVisibility(model.nodes, model.edges, {
			kinds: new Set(ALL_KINDS),
			owners: new Set(ALL_OWNERS),
			relations: new Set(['marker_edit']),
			search: '',
			degreeMin: 0,
			degreeMax: null,
		});
		expect(result.visibleNodes).toHaveLength(3);
		expect(result.visibleEdges.map((edge) => edge.relation)).toEqual(['marker_edit']);
	});
});

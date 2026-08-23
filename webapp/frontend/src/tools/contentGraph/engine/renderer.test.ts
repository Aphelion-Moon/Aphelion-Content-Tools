import { describe, expect, it } from 'vitest';
import { applyVisibility } from './filters';
import { buildGraphModel } from './model';
import { buildGraphologyGraph, renderScaleForNodeCount, syncEgoColors, syncVisibility } from './renderer';
import { ALL_KINDS, ALL_OWNERS } from './types';

describe('Content Graph renderer bridge', () => {
	it('shrinks screen-space marks for a full repository overview', () => {
		expect(renderScaleForNodeCount(3_572)).toBe(1);
		expect(renderScaleForNodeCount(30_331)).toBeCloseTo(Math.sqrt(4_000 / 30_331));
		expect(renderScaleForNodeCount(1_000_000)).toBe(0.2);
	});

	it('builds a multi graph and synchronizes visibility without recreating it', () => {
		const model = buildGraphModel({
			nodes: [
				{ id: 'a', kind: 'module', owner: 'aphelion', module_id: 'a' },
				{ id: 'b', kind: 'core_file', path: 'b.dm' },
			],
			edges: [
				{ source: 'a', target: 'b', relation: 'marker_edit' },
				{ source: 'a', target: 'b', relation: 'module_reference' },
			],
		});
		const graph = buildGraphologyGraph(model.nodes, model.edges);
		expect(graph.order).toBe(2);
		expect(graph.size).toBe(2);

		applyVisibility(model.nodes, model.edges, {
			kinds: new Set(ALL_KINDS),
			owners: new Set(ALL_OWNERS),
			relations: new Set(['marker_edit']),
			search: '',
			degreeMin: 0,
			degreeMax: null,
		});
		syncVisibility(graph, model.nodeById, new Set(['marker_edit']));
		const hidden = graph.edges().filter((edge) => graph.getEdgeAttribute(edge, 'hidden'));
		expect(hidden).toHaveLength(1);
	});

	it('applies hop-distance colors and restores base colors when ego view clears', () => {
		const model = buildGraphModel({
			nodes: [
				{ id: 'a', kind: 'module', owner: 'aphelion', module_id: 'a' },
				{ id: 'b', kind: 'core_file', path: 'b.dm' },
			],
			edges: [{ source: 'a', target: 'b', relation: 'marker_edit' }],
		});
		const graph = buildGraphologyGraph(model.nodes, model.edges);
		const base = graph.getNodeAttribute('a', 'baseColor');
		syncEgoColors(graph, new Map([['a', 0], ['b', 1]]));
		expect(graph.getNodeAttribute('a', 'color')).not.toBe(base);
		syncEgoColors(graph, null);
		expect(graph.getNodeAttribute('a', 'color')).toBe(base);
	});
});

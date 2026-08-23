import { describe, expect, it } from 'vitest';
import { buildTreeIndex, defaultScopeIds, graphForScope, subtreeIds } from './scope';
import type { RawGraph } from './types';

const graph: RawGraph = {
	nodes: [
		{ id: 'dir:.', kind: 'directory', path: '.', name: 'root' },
		{ id: 'dir:code', kind: 'directory', path: 'code', name: 'code' },
		{ id: 'file:code/a.dm', kind: 'file', path: 'code/a.dm', name: 'a.dm' },
		{ id: 'module:aphelion:test', kind: 'module', path: 'modular_aphelion/modules/test', module_id: 'test', owner: 'aphelion' },
	],
	edges: [
		{ source: 'dir:.', target: 'dir:code', relation: 'contains' },
		{ source: 'dir:code', target: 'file:code/a.dm', relation: 'contains' },
	],
};

describe('content graph scope', () => {
	it('indexes containment and collects an exact subtree', () => {
		const tree = buildTreeIndex(graph);
		expect([...subtreeIds('dir:code', tree.childrenByParent)].sort()).toEqual([
			'dir:code',
			'file:code/a.dm',
		]);
	});

	it('starts with semantic nodes and excludes edges crossing outside scope', () => {
		const scope = defaultScopeIds(graph);
		expect([...scope]).toEqual(['module:aphelion:test']);
		const scoped = graphForScope(graph, new Set(['dir:code', 'file:code/a.dm']));
		expect(scoped.nodes).toHaveLength(2);
		expect(scoped.edges).toHaveLength(1);
	});
});

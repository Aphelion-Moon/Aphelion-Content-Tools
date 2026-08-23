import { describe, expect, it } from 'vitest';
import { buildClusterAnchors, createSeededRandom, packNodesIntoGrid } from './layout';
import type { GraphNode } from './types';

function node(id: string): GraphNode {
	return {
		id,
		kind: 'file',
		owner: null,
		moduleId: null,
		path: id,
		name: id,
		corePath: null,
		hasReadme: false,
		markerCount: 0,
		fileCount: null,
		totalBytes: null,
		sizeBytes: null,
		lineCount: null,
		degree: 0,
		radius: 3,
		x: 0,
		y: 0,
		vx: 0,
		vy: 0,
		visible: true,
	};
}

describe('content graph layout', () => {
	it('places a single cluster at the origin without an infinite radius', () => {
		const anchors = buildClusterAnchors({ byKind: false, byOwner: false }, 1, 25_000);
		expect([...anchors.values()]).toEqual([{ x: 0, y: 0 }]);
	});

	it('uses an injected seeded random source for reproducible packed placement', () => {
		const first = [node('a'), node('b'), node('c')];
		const second = [node('a'), node('b'), node('c')];
		packNodesIntoGrid(first, { x: 10, y: 20 }, 1, createSeededRandom('same graph'));
		packNodesIntoGrid(second, { x: 10, y: 20 }, 1, createSeededRandom('same graph'));
		expect(first.map(({ x, y }) => ({ x, y }))).toEqual(second.map(({ x, y }) => ({ x, y })));
	});
});

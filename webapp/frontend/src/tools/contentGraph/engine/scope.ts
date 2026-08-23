import type { RawGraph, RawNode } from './types';

export interface TreeIndex {
	readonly nodeById: ReadonlyMap<string, RawNode>;
	readonly childrenByParent: ReadonlyMap<string, readonly string[]>;
	readonly parentByChild: ReadonlyMap<string, string>;
}

export function buildTreeIndex(graph: RawGraph): TreeIndex {
	const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));
	const childrenByParent = new Map<string, string[]>();
	const parentByChild = new Map<string, string>();
	for (const edge of graph.edges) {
		if (edge.relation !== 'contains' || !nodeById.has(edge.source) || !nodeById.has(edge.target)) continue;
		const children = childrenByParent.get(edge.source) ?? [];
		children.push(edge.target);
		childrenByParent.set(edge.source, children);
		parentByChild.set(edge.target, edge.source);
	}
	for (const children of childrenByParent.values()) children.sort();
	return { nodeById, childrenByParent, parentByChild };
}

export function subtreeIds(nodeId: string, childrenByParent: ReadonlyMap<string, readonly string[]>): Set<string> {
	const result = new Set<string>();
	const pending = [nodeId];
	while (pending.length > 0) {
		const current = pending.pop()!;
		if (result.has(current)) continue;
		result.add(current);
		pending.push(...(childrenByParent.get(current) ?? []));
	}
	return result;
}

export function defaultScopeIds(graph: RawGraph): Set<string> {
	return new Set(
		graph.nodes
			.filter((node) => node.kind === 'module' || node.kind === 'master_file' || node.kind === 'core_file')
			.map((node) => node.id),
	);
}

export function graphForScope(graph: RawGraph, scope: ReadonlySet<string>): RawGraph {
	return {
		nodes: graph.nodes.filter((node) => scope.has(node.id)),
		edges: graph.edges.filter((edge) => scope.has(edge.source) && scope.has(edge.target)),
	};
}

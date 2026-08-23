import { OWNED_KINDS, type FilterSettings, type GraphEdge, type GraphNode } from './types';

export interface VisibilityResult {
	readonly visibleNodes: GraphNode[];
	readonly visibleEdges: GraphEdge[];
}

function searchableText(node: GraphNode): string {
	return [node.id, node.moduleId, node.path, node.name, node.corePath]
		.filter((value): value is string => Boolean(value))
		.join(' ')
		.toLocaleLowerCase();
}

export function nodeMatchesFilters(node: GraphNode, filters: FilterSettings): boolean {
	if (!filters.kinds.has(node.kind)) return false;
	if (OWNED_KINDS.has(node.kind) && node.owner && !filters.owners.has(node.owner)) return false;
	if (node.degree < filters.degreeMin) return false;
	if (filters.degreeMax !== null && node.degree > filters.degreeMax) return false;
	const query = filters.search.trim().toLocaleLowerCase();
	return !query || searchableText(node).includes(query);
}

/**
 * Apply presentation filters without rebuilding the simulation's node membership.
 *
 * Stable positions are deliberate: checking a relation or typing a query should reveal/hide the same
 * layout, not make every remaining node jump because the physics graph was silently replaced.
 */
export function applyVisibility(
	nodes: readonly GraphNode[],
	edges: readonly GraphEdge[],
	filters: FilterSettings,
): VisibilityResult {
	for (const node of nodes) node.visible = nodeMatchesFilters(node, filters);
	return {
		visibleNodes: nodes.filter((node) => node.visible),
		visibleEdges: edges.filter((edge) => (
			filters.relations.has(edge.relation)
			&& edge.source.visible
			&& edge.target.visible
		)),
	};
}

import type { EdgeRelation, GraphEdge, GraphNode, NodeKind } from './types';

const KIND_COLORS: Record<NodeKind, string | Record<string, string>> = {
	module: { nova: '#56d4dc', aphelion: '#7bc86f' },
	master_file: '#c06bb4',
	core_file: '#e5c25b',
	directory: '#a89f90',
	file: '#8f887c',
};

const EDGE_COLORS: Record<EdgeRelation, string | Record<string, string>> = {
	master_files_mirror: 'rgba(168, 159, 144, .5)',
	marker_edit: {
		addition: 'rgba(123, 200, 111, .65)',
		removal: 'rgba(217, 95, 76, .65)',
		change: 'rgba(192, 107, 180, .75)',
		unspecified: 'rgba(168, 159, 144, .55)',
	},
	contains: 'rgba(143, 136, 124, .28)',
	module_reference: 'rgba(229, 194, 91, .6)',
	core_reference: 'rgba(224, 134, 63, .6)',
};

export const SELECTED_NODE_COLOR = '#ece5d8';

/**
 * Hop-distance tiers for ego view: brightest at the ego node, progressively dimmer outward, clamped to
 * the last tier beyond its length.
 */
const EGO_TIER_COLORS = ['#ece5d8', '#56d4dc', '#7bc86f', '#8f887c', '#5c574e'] as const;

export function nodeColor(node: GraphNode): string {
	const entry = KIND_COLORS[node.kind];
	if (typeof entry === 'string') return entry;
	return entry[node.owner ?? 'nova'] ?? entry['nova'] ?? '#8f887c';
}

export function edgeColor(edge: GraphEdge): string {
	const entry = EDGE_COLORS[edge.relation];
	if (typeof entry === 'string') return entry;
	return entry[edge.editType ?? 'unspecified'] ?? entry['unspecified']!;
}

export function egoTierColor(distance: number | undefined): string {
	if (distance === undefined) return EGO_TIER_COLORS[EGO_TIER_COLORS.length - 1]!;
	return EGO_TIER_COLORS[Math.min(distance, EGO_TIER_COLORS.length - 1)]!;
}

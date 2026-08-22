import type { EdgeRelation, GraphEdge, GraphNode, NodeKind } from './types';

const KIND_COLORS: Record<NodeKind, string | Record<string, string>> = {
	module: { nova: '#55d6ff', aphelion: '#52f0b0' },
	master_file: '#f2a9dd',
	core_file: '#d16aff',
	directory: '#8f6fae',
	file: '#6c5a82',
};

const EDGE_COLORS: Record<EdgeRelation, string | Record<string, string>> = {
	master_files_mirror: 'rgba(198, 169, 212, .5)',
	marker_edit: {
		addition: 'rgba(82, 240, 176, .65)',
		removal: 'rgba(240, 120, 120, .65)',
		change: 'rgba(242, 169, 221, .75)',
		unspecified: 'rgba(198, 169, 212, .55)',
	},
	contains: 'rgba(140, 120, 170, .28)',
	module_reference: 'rgba(255, 196, 92, .6)',
	core_reference: 'rgba(255, 148, 92, .6)',
};

export const SELECTED_NODE_COLOR = '#fff7ff';

/**
 * Hop-distance tiers for ego view: brightest at the ego node, progressively dimmer outward, clamped to
 * the last tier beyond its length.
 */
const EGO_TIER_COLORS = ['#fff7ff', '#55d6ff', '#9614d0', '#6c5a82', '#4a3f57'] as const;

export function nodeColor(node: GraphNode): string {
	const entry = KIND_COLORS[node.kind];
	if (typeof entry === 'string') return entry;
	return entry[node.owner ?? 'nova'] ?? entry['nova'] ?? '#6c5a82';
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

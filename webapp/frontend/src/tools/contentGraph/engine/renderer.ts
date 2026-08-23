import { MultiDirectedGraph } from 'graphology';
import type { Attributes } from 'graphology-types';
import { edgeColor, egoTierColor, nodeColor } from './colors';
import type { EdgeRelation, GraphEdge, GraphNode } from './types';

export interface RenderNodeAttributes extends Attributes {
	x: number;
	y: number;
	size: number;
	color: string;
	baseColor: string;
	label: string;
	hidden: boolean;
}

export interface RenderEdgeAttributes extends Attributes {
	relation: EdgeRelation;
	size: number;
	color: string;
	baseColor: string;
	hidden: boolean;
}

export type RenderGraph = MultiDirectedGraph<RenderNodeAttributes, RenderEdgeAttributes>;

const FULL_SIZE_NODE_LIMIT = 4_000;

/** Keep overview marks legible without letting 30k fixed-pixel nodes merge into solid blocks. */
export function renderScaleForNodeCount(nodeCount: number): number {
	if (nodeCount <= FULL_SIZE_NODE_LIMIT) return 1;
	return Math.max(0.2, Math.sqrt(FULL_SIZE_NODE_LIMIT / nodeCount));
}

export function nodeLabel(node: GraphNode): string {
	return node.name ?? node.moduleId ?? node.path ?? node.id;
}

export function buildGraphologyGraph(nodes: readonly GraphNode[], edges: readonly GraphEdge[]): RenderGraph {
	const graph = new MultiDirectedGraph<RenderNodeAttributes, RenderEdgeAttributes>();
	const renderScale = renderScaleForNodeCount(nodes.length);
	for (const node of nodes) {
		const color = nodeColor(node);
		graph.addNode(node.id, {
			x: node.x,
			y: node.y,
			size: node.radius * renderScale,
			color,
			baseColor: color,
			label: nodeLabel(node),
			hidden: !node.visible,
		});
	}
	for (const [index, edge] of edges.entries()) {
		const color = edgeColor(edge);
		graph.addDirectedEdgeWithKey(`edge:${index}`, edge.source.id, edge.target.id, {
			relation: edge.relation,
			size: (edge.relation === 'marker_edit' ? 1.4 : edge.relation === 'contains' ? 0.6 : 1) * renderScale,
			color,
			baseColor: color,
			hidden: !edge.source.visible || !edge.target.visible,
		});
	}
	return graph;
}

export function syncPositions(graph: RenderGraph, nodeById: ReadonlyMap<string, GraphNode>): void {
	const renderScale = renderScaleForNodeCount(graph.order);
	graph.updateEachNodeAttributes((nodeId, attributes) => {
		const node = nodeById.get(nodeId);
		if (!node) return attributes;
		return { ...attributes, x: node.x, y: node.y, size: node.radius * renderScale };
	}, { attributes: ['x', 'y', 'size'] });
}

export function syncVisibility(
	graph: RenderGraph,
	nodeById: ReadonlyMap<string, GraphNode>,
	visibleRelations: ReadonlySet<EdgeRelation>,
): void {
	graph.updateEachNodeAttributes((nodeId, attributes) => ({
		...attributes,
		hidden: !(nodeById.get(nodeId)?.visible ?? false),
	}), { attributes: ['hidden'] });
	graph.updateEachEdgeAttributes((_edgeId, attributes, _source, _target, sourceAttributes, targetAttributes) => ({
		...attributes,
		hidden: sourceAttributes.hidden || targetAttributes.hidden || !visibleRelations.has(attributes.relation),
	}), { attributes: ['hidden'] });
}

export function syncEgoColors(graph: RenderGraph, distances: ReadonlyMap<string, number> | null): void {
	graph.updateEachNodeAttributes((nodeId, attributes) => ({
		...attributes,
		color: distances ? egoTierColor(distances.get(nodeId)) : attributes.baseColor,
	}), { attributes: ['color'] });
	graph.updateEachEdgeAttributes((_edgeId, attributes, sourceId, targetId) => ({
		...attributes,
		color: distances
			? egoTierColor(Math.max(distances.get(sourceId) ?? 0, distances.get(targetId) ?? 0))
			: attributes.baseColor,
	}), { attributes: ['color'] });
}

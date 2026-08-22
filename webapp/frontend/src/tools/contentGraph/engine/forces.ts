import { clusterKey, type GroupingAxes, type Point } from './layout';
import type { ForceSettings, GraphEdge, GraphNode } from './types';

// Custom d3-force forces. Each is a factory returning a function(alpha) that mutates node.vx/vy -- the
// shape d3-force expects -- plus an `initialize` hook d3 calls when the node set changes.
//
// They read their settings live on every tick through a getter rather than capturing values once, so a
// slider drag takes effect immediately without rebuilding the simulation.

export interface ForceContext {
	readonly settings: () => ForceSettings;
	readonly axes: () => GroupingAxes;
	readonly anchors: () => ReadonlyMap<string, Point>;
	readonly focus: () => { enabled: boolean; nodeId: string | null; ringSpacing: number; distances: ReadonlyMap<string, number> };
}

interface D3Force {
	(alpha: number): void;
	initialize?: (nodes: GraphNode[]) => void;
}

/**
 * Pull nodes toward their cluster's anchor, organising the graph into visually distinct regions without
 * giving up the organic feel of force-directed layout within each region.
 */
export function createClusterForce(context: ForceContext): D3Force {
	let nodes: GraphNode[] = [];
	const force: D3Force = (alpha: number) => {
		// Focus mode is a competing organising scheme (rings by hop distance). Letting cluster pull run
		// at the same time would just fight it over where every node belongs.
		if (context.focus().enabled) return;
		const axes = context.axes();
		if (!axes.byKind && !axes.byOwner) return;
		const strength = context.settings().clusterStrength;
		if (!strength) return;
		const anchors = context.anchors();
		for (const node of nodes) {
			if (node.fx != null) continue;
			const anchor = anchors.get(clusterKey(node, axes)) ?? { x: 0, y: 0 };
			node.vx += (anchor.x - node.x) * strength * alpha;
			node.vy += (anchor.y - node.y) * strength * alpha;
		}
	};
	force.initialize = (next) => {
		nodes = next;
	};
	return force;
}

/**
 * Keep the layout roughly on screen without flattening its structure.
 *
 * Connected nodes get a uniform whole-graph translation based on how far their centroid has drifted,
 * never an individual pull toward the origin. A per-node inward pull is what previously compressed
 * tree and branching structure into a dense disc: pairwise repulsion balanced against uniform inward
 * pull always settles into a filled circle, however far a branch "wants" to extend. A rigid shift of
 * the whole layout does not fight local structure at all.
 *
 * Degree-0 nodes are the exception. Nothing else reels them back -- no link force to any neighbour --
 * so they keep their own stronger, individually targeted pull.
 */
export function createCenterPullForce(context: ForceContext): D3Force {
	let nodes: GraphNode[] = [];
	const force: D3Force = (alpha: number) => {
		const settings = context.settings();
		const strength = settings.center;
		if (!strength) return;

		let sumX = 0;
		let sumY = 0;
		let connectedCount = 0;
		for (const node of nodes) {
			if (node.degree === 0) continue;
			sumX += node.x;
			sumY += node.y;
			connectedCount += 1;
		}

		if (connectedCount > 0) {
			const dx = -(sumX / connectedCount) * strength * alpha;
			const dy = -(sumY / connectedCount) * strength * alpha;
			for (const node of nodes) {
				if (node.fx != null) continue;
				node.vx += dx;
				node.vy += dy;
			}
		}

		for (const node of nodes) {
			if (node.fx != null || node.degree !== 0) continue;
			node.vx -= node.x * strength * settings.isolatedPull * alpha;
			node.vy -= node.y * strength * settings.isolatedPull * alpha;
		}
	};
	force.initialize = (next) => {
		nodes = next;
	};
	return force;
}

/**
 * Arrange nodes in concentric rings by hop distance from the focused node.
 *
 * Hand-rolled rather than using d3's forceRadial, whose per-node radius accessor is cached at
 * initialize time and would need explicit re-triggering on every focus change. Nodes unreachable from
 * the focus land one ring beyond the farthest reached node, rather than being treated as neighbours.
 */
export function createFocusForce(context: ForceContext): D3Force {
	let nodes: GraphNode[] = [];
	const force: D3Force = (alpha: number) => {
		const focus = context.focus();
		if (!focus.enabled || !focus.nodeId) return;

		let maxDistance = 0;
		for (const value of focus.distances.values()) maxDistance = Math.max(maxDistance, value);
		const outerRadius = (maxDistance + 2) * focus.ringSpacing;

		for (const node of nodes) {
			if (node.fx != null) continue;
			const distance = focus.distances.get(node.id);
			const targetRadius = distance === undefined ? outerRadius : distance * focus.ringSpacing;
			const currentRadius = Math.hypot(node.x, node.y);
			// A node sitting exactly on the origin has no direction to be pushed along.
			if (currentRadius < 1e-6) continue;
			const pull = ((targetRadius - currentRadius) / currentRadius) * 0.15 * alpha;
			node.vx += node.x * pull;
			node.vy += node.y * pull;
		}
	};
	force.initialize = (next) => {
		nodes = next;
	};
	return force;
}

/**
 * Hop distances from one node, by breadth-first search over the full scope.
 *
 * Deliberately uses every edge rather than only currently-visible ones, so hop distance reflects real
 * topology rather than whichever relation checkboxes happen to be ticked. Unreachable nodes are simply
 * absent from the result.
 */
export function computeHopDistances(
	edges: readonly GraphEdge[],
	fromNodeId: string | null,
): Map<string, number> {
	const distances = new Map<string, number>();
	if (!fromNodeId) return distances;

	const adjacency = new Map<string, string[]>();
	const link = (a: string, b: string) => {
		let list = adjacency.get(a);
		if (!list) {
			list = [];
			adjacency.set(a, list);
		}
		list.push(b);
	};
	for (const edge of edges) {
		link(edge.source.id, edge.target.id);
		link(edge.target.id, edge.source.id);
	}

	distances.set(fromNodeId, 0);
	const queue = [fromNodeId];
	for (let head = 0; head < queue.length; head += 1) {
		const current = queue[head]!;
		const distance = distances.get(current)!;
		for (const neighbor of adjacency.get(current) ?? []) {
			if (distances.has(neighbor)) continue;
			distances.set(neighbor, distance + 1);
			queue.push(neighbor);
		}
	}
	return distances;
}

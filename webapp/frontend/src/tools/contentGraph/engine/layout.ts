import { OWNED_KINDS, ALL_KINDS } from './types';
import type { GraphNode, NodeKind, SeedShape, SpacingSettings } from './types';

// Deterministic placement maths, kept as pure functions so the layout can be reasoned about and tested
// without a canvas, a simulation, or a browser. Seeding well matters more than it sounds: starting
// close to the final arrangement means the physics settle has far less distance to cover and far fewer
// near-coincident starting points to explosively separate, which is what made large graphs slow and
// chaotic to lay out.

/** Cluster ring radius for a small graph; grows with node count via computeSpacingScale. */
export const BASE_CLUSTER_RADIUS = 650;
const SPACING_BASELINE_NODES = 400;
/** Bounds the default sqrt growth. `unlimited` bypasses it rather than raising it. */
export const MAX_SPACING_SCALE = 1000;
/** Above this many nodes, "auto" seeding switches from a settled spiral to a deterministic packed grid. */
export const LARGE_GRAPH_NODE_THRESHOLD = 4000;
const GRID_PACK_CELL_SIZE = 16;

export interface Point {
	readonly x: number;
	readonly y: number;
}

export interface GroupingAxes {
	readonly byKind: boolean;
	readonly byOwner: boolean;
}

/**
 * Which cluster a node belongs to, given the active grouping axes.
 *
 * Must stay consistent with `clusterKeys`: anchors are built from that list and looked up by this key,
 * so a mismatch silently drops nodes to the origin.
 */
export function clusterKey(node: Pick<GraphNode, 'kind' | 'owner'>, axes: GroupingAxes): string {
	const kindPart = axes.byKind ? node.kind : 'any';
	if (axes.byOwner && OWNED_KINDS.has(node.kind)) return `${kindPart}:${node.owner ?? 'nova'}`;
	return `${kindPart}:none`;
}

/** Every key `clusterKey` can produce for the active axes. */
export function clusterKeys(axes: GroupingAxes): string[] {
	const keys = new Set<string>();
	for (const kind of ALL_KINDS) {
		const kindPart = axes.byKind ? kind : 'any';
		if (axes.byOwner && OWNED_KINDS.has(kind)) {
			keys.add(`${kindPart}:nova`);
			keys.add(`${kindPart}:aphelion`);
		} else {
			keys.add(`${kindPart}:none`);
		}
	}
	return [...keys];
}

/**
 * How much wider than the small-graph baseline the layout should be.
 *
 * Enough nodes crammed onto a fixed-size ring is precisely what forces them to overlap, so auto mode
 * grows with sqrt(nodeCount).
 */
export function computeSpacingScale(nodeCount: number, spacing: SpacingSettings): number {
	if (!spacing.autoScale) return spacing.manualScale;
	const raw = Math.max(1, Math.sqrt(nodeCount / SPACING_BASELINE_NODES));
	return spacing.unlimited ? raw : Math.min(MAX_SPACING_SCALE, raw);
}

/** Side length in cells of a roughly square grid holding n nodes. */
export function packedGridCols(n: number): number {
	return Math.max(1, Math.ceil(Math.sqrt(n)));
}

/**
 * Cell size grows with sqrt of the spacing scale, not linearly.
 *
 * Per-node packing density should track actual node radii, which do not change with node count -- not
 * the multiplier used to widen the ring *between* clusters. Scaling both the same way compounds: a
 * 25,000-node cluster's footprint would grow with the square of the spacing scale.
 */
export function packedCellSize(scale: number): number {
	return GRID_PACK_CELL_SIZE * Math.sqrt(scale);
}

/** How far a cluster's packed footprint reaches from its anchor: half-diagonal of its grid. */
export function clusterFootprintRadius(n: number, scale: number): number {
	if (n <= 0) return 0;
	const cellSize = packedCellSize(scale);
	const cols = packedGridCols(n);
	const rows = Math.max(1, Math.ceil(n / cols));
	return Math.hypot(cols, rows) * cellSize * 0.5;
}

/**
 * Anchor points evenly spaced around a ring, one per cluster.
 *
 * When `maxClusterSize` is given, the radius widens so neighbouring clusters cannot overlap even when
 * one is enormous: the chord between adjacent anchors is 2*r*sin(pi/N), so solving for the radius that
 * keeps that chord comfortably wider than twice the largest footprint does it.
 */
export function buildClusterAnchors(
	axes: GroupingAxes,
	scale: number,
	maxClusterSize?: number,
): Map<string, Point> {
	const keys = clusterKeys(axes);
	let radius = BASE_CLUSTER_RADIUS * scale;
	if (maxClusterSize) {
		const footprint = clusterFootprintRadius(maxClusterSize, scale);
		const neighborGap = 2 * Math.sin(Math.PI / keys.length);
		radius = Math.max(radius, (footprint * 2.2) / neighborGap);
	}
	return new Map(
		keys.map((key, index) => {
			const angle = (index / keys.length) * Math.PI * 2;
			return [key, { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius }];
		}),
	);
}

/**
 * A centre-outward square spiral of grid offsets: (0,0), (1,0), (1,1), (0,1), (-1,1)...
 *
 * Used so the order nodes are packed in becomes their proximity to the cluster anchor.
 */
export function spiralGridOffsets(n: number): { col: number; row: number }[] {
	const offsets: { col: number; row: number }[] = [];
	let col = 0;
	let row = 0;
	let dcol = 1;
	let drow = 0;
	let segmentLength = 1;
	let segmentPassed = 0;
	let turns = 0;
	for (let i = 0; i < n; i += 1) {
		offsets.push({ col, row });
		col += dcol;
		row += drow;
		segmentPassed += 1;
		if (segmentPassed === segmentLength) {
			segmentPassed = 0;
			const nextDcol = -drow;
			const nextDrow = dcol;
			dcol = nextDcol;
			drow = nextDrow;
			turns += 1;
			if (turns % 2 === 0) segmentLength += 1;
		}
	}
	return offsets;
}

/**
 * Lay nodes into a packed grid around an anchor, avoiding overlap by construction rather than waiting
 * for repulsion to diffuse them apart.
 *
 * Filled highest-degree-first along a centre-out spiral, so the most heavily linked nodes land nearest
 * the anchor, and degree-0 nodes -- which sort to the back -- end up together in the outer ring rather
 * than scattered through the connected core. A little jitter keeps it from reading as mechanical
 * without reintroducing near-coincident starting points.
 */
export function packNodesIntoGrid(nodes: readonly GraphNode[], anchor: Point, scale: number): void {
	const cellSize = packedCellSize(scale);
	const ordered = [...nodes].sort((a, b) => b.degree - a.degree);
	const offsets = spiralGridOffsets(ordered.length);
	ordered.forEach((node, index) => {
		const offset = offsets[index]!;
		const jitter = cellSize * 0.18;
		node.x = anchor.x + offset.col * cellSize + (Math.random() - 0.5) * jitter;
		node.y = anchor.y + offset.row * cellSize + (Math.random() - 0.5) * jitter;
	});
}

/** Spawn on a small spiral within each node's own cluster, rather than one global ring. */
export function placeSpiralSeed(
	nodes: readonly GraphNode[],
	anchors: ReadonlyMap<string, Point>,
	axes: GroupingAxes,
	scale: number,
): void {
	nodes.forEach((node, index) => {
		const anchor = anchors.get(clusterKey(node, axes)) ?? { x: 0, y: 0 };
		const angle = (index / nodes.length) * Math.PI * 2 * 6;
		const radius = (60 + (index % 40) * 6) * scale;
		node.x = anchor.x + Math.cos(angle) * radius;
		node.y = anchor.y + Math.sin(angle) * radius;
	});
}

export function placePackedGridSeed(
	groups: ReadonlyMap<string, GraphNode[]>,
	anchors: ReadonlyMap<string, Point>,
	scale: number,
): void {
	for (const [key, group] of groups) {
		packNodesIntoGrid(group, anchors.get(key) ?? { x: 0, y: 0 }, scale);
	}
}

/** One packed grid at the origin, ignoring clusters -- a neutral, maximally spread start. */
export function placeGlobalGridSeed(nodes: readonly GraphNode[], scale: number): void {
	packNodesIntoGrid(nodes, { x: 0, y: 0 }, scale);
}

/** Uniform scatter within each cluster's footprint. */
export function placeRandomSeed(
	groups: ReadonlyMap<string, GraphNode[]>,
	anchors: ReadonlyMap<string, Point>,
	scale: number,
): void {
	for (const [key, group] of groups) {
		const anchor = anchors.get(key) ?? { x: 0, y: 0 };
		const footprint = clusterFootprintRadius(group.length, scale);
		for (const node of group) {
			const angle = Math.random() * Math.PI * 2;
			// sqrt of a uniform sample, because uniform radius sampling is not uniform over a disc's area
			// -- points would bunch toward the centre.
			const radius = Math.sqrt(Math.random()) * footprint;
			node.x = anchor.x + Math.cos(angle) * radius;
			node.y = anchor.y + Math.sin(angle) * radius;
		}
	}
}

/** What "auto" resolves to: spiral below the large-graph threshold, packed above it. */
export function resolveSeedShape(requested: SeedShape, nodeCount: number): Exclude<SeedShape, 'auto'> {
	if (requested !== 'auto') return requested;
	return nodeCount > LARGE_GRAPH_NODE_THRESHOLD ? 'packed' : 'spiral';
}

/** Drawn radius, from degree. Kept separate from collision radius. */
export function nodeRadius(degree: number): number {
	return 3 + Math.min(14, Math.sqrt(degree + 1) * 2.2);
}

export function groupNodesByCluster(
	nodes: readonly GraphNode[],
	axes: GroupingAxes,
): Map<string, GraphNode[]> {
	const groups = new Map<string, GraphNode[]>();
	for (const node of nodes) {
		const key = clusterKey(node, axes);
		let group = groups.get(key);
		if (!group) {
			group = [];
			groups.set(key, group);
		}
		group.push(node);
	}
	return groups;
}

export type { NodeKind };

// Domain types for the content graph.
//
// The wire shapes (RawNode/RawEdge) come from /api/graph and use snake_case, matching the Python
// scanner. They are converted once into the camelCase simulation types below, which additionally carry
// the mutable position/velocity fields d3-force writes into.

export type NodeKind = 'module' | 'master_file' | 'core_file' | 'directory' | 'file';
export type NodeOwner = 'nova' | 'aphelion';
export type EdgeRelation =
	| 'master_files_mirror'
	| 'marker_edit'
	| 'contains'
	| 'module_reference'
	| 'core_reference';
export type EditType = 'addition' | 'removal' | 'change' | 'unspecified';

export interface RawNode {
	readonly id: string;
	readonly kind: NodeKind;
	readonly owner?: NodeOwner | null;
	readonly module_id?: string | null;
	readonly path?: string | null;
	readonly name?: string | null;
	readonly core_path?: string | null;
	readonly has_readme?: boolean | null;
	readonly marker_count?: number | null;
	readonly file_count?: number | null;
	readonly total_bytes?: number | null;
	readonly size_bytes?: number | null;
	readonly line_count?: number | null;
}

export interface RawEdge {
	readonly source: string;
	readonly target: string;
	readonly relation: EdgeRelation;
	readonly edit_type?: EditType | null;
	readonly attribution?: string | null;
	readonly line_number?: number | null;
	readonly raw_label?: string | null;
	readonly original_text?: string | null;
}

export interface RawGraph {
	readonly nodes: readonly RawNode[];
	readonly edges: readonly RawEdge[];
}

/** A node in the simulation. Position and velocity are mutated in place by d3-force. */
export interface GraphNode {
	readonly id: string;
	readonly kind: NodeKind;
	readonly owner: NodeOwner | null;
	readonly moduleId: string | null;
	readonly path: string | null;
	readonly name: string | null;
	readonly corePath: string | null;
	readonly hasReadme: boolean;
	readonly markerCount: number;
	readonly fileCount: number | null;
	readonly totalBytes: number | null;
	readonly sizeBytes: number | null;
	readonly lineCount: number | null;
	degree: number;
	radius: number;
	x: number;
	y: number;
	vx: number;
	vy: number;
	/** Set by d3-force while a node is pinned or dragged; null means free to move. */
	fx?: number | null;
	fy?: number | null;
	visible: boolean;
}

export interface GraphEdge {
	readonly source: GraphNode;
	readonly target: GraphNode;
	readonly relation: EdgeRelation;
	readonly editType: EditType | null;
	readonly attribution: string | null;
	readonly lineNumber: number | null;
	readonly rawLabel: string | null;
	readonly originalText: string | null;
}

export type SeedShape = 'auto' | 'spiral' | 'packed' | 'grid' | 'random';
export type PhysicsMode = 'auto' | 'on' | 'off';

/** Per-node forces. Read live on every tick, so a slider change takes effect without a restart. */
export interface ForceSettings {
	repulsion: number;
	springLength: number;
	springStrength: number;
	center: number;
	clusterStrength: number;
	/**
	 * Extra centre-pull multiplier for degree-0 nodes. Nothing else reels an unconnected node back in --
	 * it has no link force to any neighbour -- so without this it is the one case that can drift
	 * arbitrarily far under repulsion alone.
	 */
	isolatedPull: number;
}

/** Simulation-wide tuning that is not a per-node force. */
export interface SimulationTuning {
	velocityDecay: number;
	alphaDecay: number;
	/** Resting alpha a live scope holds once settled -- the continuous slow drift. */
	ambientAlpha: number;
	/** One-shot velocity kick, to escape a lopsided local arrangement. */
	jiggleStrength: number;
	/** Barnes-Hut approximation factor; higher is faster but less accurate. */
	theta: number;
	collideEnabled: boolean;
	collidePadding: number;
	collideStrength: number;
	/**
	 * Collision-radius buffer scaling with degree, separate from a node's drawn radius -- so a hub can
	 * stay visually modest while still not being crowded or buried.
	 */
	hubCollisionBuffer: number;
	chargeByDegree: boolean;
	chargeByDegreeFactor: number;
}

export interface SpacingSettings {
	autoScale: boolean;
	manualScale: number;
	/** Bypasses the default growth ceiling entirely rather than raising it. */
	unlimited: boolean;
}

export interface FilterSettings {
	kinds: ReadonlySet<NodeKind>;
	owners: ReadonlySet<NodeOwner>;
	relations: ReadonlySet<EdgeRelation>;
	search: string;
	degreeMin: number;
	degreeMax: number | null;
}

export const ALL_KINDS: readonly NodeKind[] = ['module', 'master_file', 'core_file', 'directory', 'file'];
export const ALL_OWNERS: readonly NodeOwner[] = ['nova', 'aphelion'];
export const ALL_RELATIONS: readonly EdgeRelation[] = [
	'master_files_mirror',
	'marker_edit',
	'contains',
	'module_reference',
	'core_reference',
];

/** Kinds that carry an owner. Everything else clusters without an owner axis. */
export const OWNED_KINDS: ReadonlySet<NodeKind> = new Set<NodeKind>(['module', 'master_file']);

export const ROOT_DIR_ID = 'dir:.';

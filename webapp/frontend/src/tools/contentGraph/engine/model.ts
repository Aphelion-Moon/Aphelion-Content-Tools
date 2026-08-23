import {
	buildClusterAnchors,
	computeSpacingScale,
	createSeededRandom,
	groupNodesByCluster,
	nodeRadius,
	placeGlobalGridSeed,
	placePackedGridSeed,
	placeRandomSeed,
	placeSpiralSeed,
	resolveSeedShape,
	type GroupingAxes,
} from './layout';
import type { GraphEdge, GraphNode, RawGraph, SeedShape, SpacingSettings } from './types';

export interface GraphModel {
	readonly nodes: GraphNode[];
	readonly edges: GraphEdge[];
	readonly nodeById: ReadonlyMap<string, GraphNode>;
	readonly spacingScale: number;
	readonly seedShape: Exclude<SeedShape, 'auto'>;
}

export interface BuildGraphOptions {
	readonly axes?: GroupingAxes;
	readonly spacing?: SpacingSettings;
	readonly seedShape?: SeedShape;
	readonly seed?: string | number;
}

const DEFAULT_AXES: GroupingAxes = { byKind: true, byOwner: true };
const DEFAULT_SPACING: SpacingSettings = { autoScale: true, manualScale: 1, unlimited: false };

export function buildGraphModel(rawGraph: RawGraph, options: BuildGraphOptions = {}): GraphModel {
	const axes = options.axes ?? DEFAULT_AXES;
	const spacing = options.spacing ?? DEFAULT_SPACING;
	const nodes: GraphNode[] = [...rawGraph.nodes]
		.sort((left, right) => left.id.localeCompare(right.id))
		.map((raw) => ({
			id: raw.id,
			kind: raw.kind,
			owner: raw.owner ?? null,
			moduleId: raw.module_id ?? null,
			path: raw.path ?? null,
			name: raw.name ?? null,
			corePath: raw.core_path ?? null,
			hasReadme: raw.has_readme ?? false,
			markerCount: raw.marker_count ?? 0,
			fileCount: raw.file_count ?? null,
			totalBytes: raw.total_bytes ?? null,
			sizeBytes: raw.size_bytes ?? null,
			lineCount: raw.line_count ?? null,
			degree: 0,
			radius: 0,
			x: 0,
			y: 0,
			vx: 0,
			vy: 0,
			visible: true,
		}));
	const nodeById = new Map(nodes.map((node) => [node.id, node]));
	const edges: GraphEdge[] = [...rawGraph.edges]
		.sort((left, right) => `${left.source}\0${left.target}\0${left.relation}`.localeCompare(`${right.source}\0${right.target}\0${right.relation}`))
		.flatMap((raw) => {
			const source = nodeById.get(raw.source);
			const target = nodeById.get(raw.target);
			if (!source || !target) return [];
			source.degree += 1;
			target.degree += 1;
			return [{
				source,
				target,
				relation: raw.relation,
				editType: raw.edit_type ?? null,
				attribution: raw.attribution ?? null,
				lineNumber: raw.line_number ?? null,
				rawLabel: raw.raw_label ?? null,
				originalText: raw.original_text ?? null,
			}];
		});
	for (const node of nodes) node.radius = nodeRadius(node.degree);

	const spacingScale = computeSpacingScale(nodes.length, spacing);
	const seedShape = resolveSeedShape(options.seedShape ?? 'auto', nodes.length);
	const groups = groupNodesByCluster(nodes, axes);
	const maxClusterSize = Math.max(0, ...[...groups.values()].map((group) => group.length));
	const anchors = buildClusterAnchors(
		axes,
		spacingScale,
		seedShape === 'packed' || seedShape === 'random' ? maxClusterSize : undefined,
	);
	const random = createSeededRandom(options.seed ?? nodes.map((node) => node.id).join('\0'));
	if (seedShape === 'packed') placePackedGridSeed(groups, anchors, spacingScale, random);
	else if (seedShape === 'grid') placeGlobalGridSeed(nodes, spacingScale, random);
	else if (seedShape === 'random') placeRandomSeed(groups, anchors, spacingScale, random);
	else placeSpiralSeed(nodes, anchors, axes, spacingScale);

	return { nodes, edges, nodeById, spacingScale, seedShape };
}

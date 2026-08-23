import {
	forceCollide,
	forceLink,
	forceManyBody,
	forceSimulation,
	type ForceLink,
	type ForceManyBody,
	type Simulation,
} from 'd3-force';
import { createCenterPullForce, createClusterForce, createFocusForce, type ForceContext } from './forces';
import { LARGE_GRAPH_NODE_THRESHOLD } from './layout';
import type { ForceSettings, GraphEdge, GraphNode, PhysicsMode, SimulationTuning } from './types';

export const LIVE_PHYSICS_NODE_THRESHOLD = 1_500;
export const LARGE_SCOPE_SETTLE_TICKS = 60;

export const DEFAULT_FORCES: Readonly<ForceSettings> = {
	repulsion: 2_600,
	springLength: 70,
	springStrength: 0.02,
	center: 0.004,
	clusterStrength: 0.025,
	isolatedPull: 4,
};

export const DEFAULT_SIMULATION_TUNING: Readonly<SimulationTuning> = {
	velocityDecay: 0.4,
	alphaDecay: 0.0228,
	ambientAlpha: 0.02,
	jiggleStrength: 200,
	theta: 0.9,
	collideEnabled: true,
	collidePadding: 2,
	collideStrength: 1,
	hubCollisionBuffer: 2,
	chargeByDegree: false,
	chargeByDegreeFactor: 0.15,
};

export interface PhysicsPolicy {
	readonly runInitialSettle: boolean;
	readonly live: boolean;
	readonly settleTickLimit: number | null;
}

/**
 * Resolves the user-facing physics mode into a bounded execution policy.
 *
 * Automatic full-catalog views use the deterministic packed layout directly. At 40k+ nodes, even a
 * bounded force settle makes first paint needlessly expensive; a writer can still explicitly opt in.
 */
export function resolvePhysicsPolicy(
	mode: PhysicsMode,
	nodeCount: number,
	liveThreshold = LIVE_PHYSICS_NODE_THRESHOLD,
): PhysicsPolicy {
	if (nodeCount === 0) return { runInitialSettle: false, live: false, settleTickLimit: 0 };
	const huge = nodeCount > LARGE_GRAPH_NODE_THRESHOLD;
	const live = mode === 'on' || (mode === 'auto' && nodeCount <= liveThreshold);
	if (huge && mode !== 'on') return { runInitialSettle: false, live: false, settleTickLimit: 0 };
	return {
		runInitialSettle: true,
		live,
		settleTickLimit: huge ? LARGE_SCOPE_SETTLE_TICKS : null,
	};
}

export interface GraphSimulationContext extends ForceContext {
	readonly tuning: () => SimulationTuning;
}

export interface GraphSimulationHandle {
	readonly simulation: Simulation<GraphNode, GraphEdge>;
	readonly live: boolean;
	syncSettings(): void;
	reheat(alpha?: number): void;
	startDrag(temperature: number, repulsionMultiplier: number): void;
	endDrag(): void;
	jiggle(random?: () => number): void;
	dispose(): void;
}

export function chargeStrengthForNode(
	node: Pick<GraphNode, 'degree'>,
	settings: ForceSettings,
	tuning: SimulationTuning,
	multiplier = 1,
): number {
	const degreeWeight = tuning.chargeByDegree ? 1 + node.degree * tuning.chargeByDegreeFactor : 1;
	return -settings.repulsion * multiplier * degreeWeight;
}

function configureCharge(
	manyBody: ForceManyBody<GraphNode>,
	context: GraphSimulationContext,
	multiplier = 1,
): void {
	const settings = context.settings();
	const tuning = context.tuning();
	manyBody.strength((node) => chargeStrengthForNode(node, settings, tuning, multiplier));
	manyBody.theta(tuning.theta);
}

function configureForces(
	manyBody: ForceManyBody<GraphNode>,
	link: ForceLink<GraphNode, GraphEdge>,
	simulation: Simulation<GraphNode, GraphEdge>,
	context: GraphSimulationContext,
): void {
	const settings = context.settings();
	const tuning = context.tuning();
	configureCharge(manyBody, context);
	link.distance(settings.springLength).strength(settings.springStrength);
	simulation.velocityDecay(tuning.velocityDecay).alphaDecay(tuning.alphaDecay);
	if (tuning.collideEnabled) {
		simulation.force('collide', forceCollide<GraphNode>((node) => (
			node.radius + tuning.collidePadding + Math.sqrt(node.degree) * tuning.hubCollisionBuffer
		)).strength(tuning.collideStrength));
	} else {
		simulation.force('collide', null);
	}
}

export function startGraphSimulation(
	nodes: GraphNode[],
	edges: GraphEdge[],
	context: GraphSimulationContext,
	policy: PhysicsPolicy,
	onTick: () => void,
	onSettled?: () => void,
): GraphSimulationHandle | null {
	if (!policy.runInitialSettle) return null;
	const manyBody = forceManyBody<GraphNode>();
	const link = forceLink<GraphNode, GraphEdge>(edges).id((node) => node.id);
	const simulation = forceSimulation<GraphNode>(nodes)
		.force('charge', manyBody)
		.force('link', link)
		.force('cluster', createClusterForce(context))
		.force('centerPull', createCenterPullForce(context))
		.force('focus', createFocusForce(context));
	configureForces(manyBody, link, simulation, context);

	let disposed = false;
	let settled = false;
	let ticks = 0;
	const settle = () => {
		if (disposed || settled) return;
		settled = true;
		onSettled?.();
		if (policy.live) simulation.alphaTarget(context.tuning().ambientAlpha).restart();
	};
	simulation.on('tick', () => {
		ticks += 1;
		onTick();
		if (policy.settleTickLimit !== null && ticks >= policy.settleTickLimit) {
			simulation.stop();
			settle();
		}
	});
	simulation.on('end', settle);

	return {
		simulation,
		live: policy.live,
		syncSettings() {
			configureForces(manyBody, link, simulation, context);
		},
		reheat(alpha = 0.3) {
			simulation.alpha(Math.max(simulation.alpha(), alpha)).restart();
		},
		startDrag(temperature, repulsionMultiplier) {
			configureCharge(manyBody, context, repulsionMultiplier);
			simulation.alphaTarget(temperature).restart();
		},
		endDrag() {
			configureCharge(manyBody, context);
			simulation.alphaTarget(policy.live ? context.tuning().ambientAlpha : 0);
		},
		jiggle(random = Math.random) {
			const strength = context.tuning().jiggleStrength;
			for (const node of nodes) {
				if (node.fx != null) continue;
				node.vx += (random() - 0.5) * strength;
				node.vy += (random() - 0.5) * strength;
			}
			simulation.alpha(Math.max(simulation.alpha(), 0.5)).restart();
		},
		dispose() {
			disposed = true;
			simulation.stop();
		},
	};
}

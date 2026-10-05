import Sigma from 'sigma';
import { SELECTED_NODE_COLOR } from './colors';
import {
	buildGraphologyGraph,
	syncEgoColors,
	syncPositions,
	syncVisibility,
	type RenderEdgeAttributes,
	type RenderGraph,
	type RenderNodeAttributes,
} from './renderer';
import type { EdgeRelation, GraphEdge, GraphNode } from './types';

export interface SigmaGraphRendererOptions {
	readonly selectedNodeId: () => string | null;
	readonly allowPanWhileDragging: () => boolean;
	readonly onSelect: (nodeId: string | null, modifierHeld: boolean) => void;
	readonly onHover?: (nodeId: string | null) => void;
	readonly onDragStart?: (nodeId: string) => void;
	readonly onDragEnd?: (nodeId: string, moved: boolean) => void;
}

/** Owns Sigma's WebGL lifecycle and translates renderer events back into domain-node changes. */
export class SigmaGraphRenderer {
	readonly graph: RenderGraph;
	readonly sigma: Sigma<RenderNodeAttributes, RenderEdgeAttributes>;
	private draggingNodeId: string | null = null;
	private dragMoved = false;

	constructor(
		container: HTMLElement,
		nodes: readonly GraphNode[],
		edges: readonly GraphEdge[],
		private readonly nodeById: ReadonlyMap<string, GraphNode>,
		private readonly options: SigmaGraphRendererOptions,
	) {
		this.graph = buildGraphologyGraph(nodes, edges);
		this.sigma = new Sigma(this.graph, container, {
			hideEdgesOnMove: true,
			hideLabelsOnMove: true,
			renderEdgeLabels: false,
			defaultEdgeType: 'line',
			labelDensity: 0.12,
			labelGridCellSize: 160,
			labelRenderedSizeThreshold: 8,
			labelColor: { color: getComputedStyle(container).getPropertyValue('--text').trim() || '#ece5d8' },
			minEdgeThickness: 0.35,
			minCameraRatio: 0.02,
			maxCameraRatio: 12,
			zIndex: true,
			nodeReducer: (nodeId, attributes) => nodeId === options.selectedNodeId()
				? { ...attributes, color: SELECTED_NODE_COLOR, zIndex: 1 }
				: attributes,
		});
		this.attachEvents();
		this.fitView(false);
	}

	private attachEvents(): void {
		this.sigma.on('enterNode', ({ node }) => { if (!this.draggingNodeId) this.options.onHover?.(node); });
		this.sigma.on('leaveNode', () => this.options.onHover?.(null));
		this.sigma.on('clickNode', ({ node, event }) => {
			const original = event.original;
			this.options.onSelect(node, 'ctrlKey' in original && (original.ctrlKey || original.metaKey));
		});
		this.sigma.on('clickStage', () => this.options.onSelect(null, false));
		this.sigma.on('downNode', ({ node }) => {
			this.draggingNodeId = node;
			this.dragMoved = false;
			this.options.onHover?.(null);
			if (!this.options.allowPanWhileDragging()) this.sigma.getCamera().disable();
			this.options.onDragStart?.(node);
		});
		const mouseCaptor = this.sigma.getMouseCaptor();
		mouseCaptor.on('mousemovebody', (event) => {
			if (!this.draggingNodeId) return;
			const node = this.nodeById.get(this.draggingNodeId);
			if (!node) return;
			this.dragMoved = true;
			const position = this.sigma.viewportToGraph(event);
			node.x = position.x;
			node.y = position.y;
			node.fx = position.x;
			node.fy = position.y;
			node.vx = 0;
			node.vy = 0;
			this.graph.setNodeAttribute(node.id, 'x', position.x);
			this.graph.setNodeAttribute(node.id, 'y', position.y);
			event.preventSigmaDefault();
			event.original.preventDefault();
			event.original.stopPropagation();
		});
		mouseCaptor.on('mouseup', () => {
			const nodeId = this.draggingNodeId;
			if (nodeId) this.options.onDragEnd?.(nodeId, this.dragMoved);
			this.draggingNodeId = null;
			this.sigma.getCamera().enable();
		});
	}

	fitView(animated = true): void {
		const camera = this.sigma.getCamera();
		const target = { x: 0.5, y: 0.5, angle: 0, ratio: 1 };
		if (animated) void camera.animate(target, { duration: 350 });
		else camera.setState(target);
	}

	syncPositions(): void { syncPositions(this.graph, this.nodeById); }
	syncVisibility(relations: ReadonlySet<EdgeRelation>, egoDistances: ReadonlyMap<string, number> | null = null): void {
		syncVisibility(this.graph, this.nodeById, relations);
		syncEgoColors(this.graph, egoDistances);
	}
	refresh(): void { this.sigma.refresh(); }
	resize(): void { this.sigma.resize(); }
	destroy(): void { this.sigma.kill(); }
}

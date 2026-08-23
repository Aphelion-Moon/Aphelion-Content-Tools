import { useSearchParams } from '@solidjs/router';
import { For, Show, createEffect, createMemo, createResource, createSignal, onCleanup, onMount, type Accessor } from 'solid-js';
import { createStore } from 'solid-js/store';
import Card from '~/components/Card';
import OpenFileActions from '~/components/OpenFileActions';
import { api } from '~/lib/api';
import type { components } from '~/lib/api-schema';
import { announceError, announceSuccess } from '~/lib/notify';
import { addReference } from '~/lib/references';
import { setSelectedContext } from '~/store/appStore';
import ModularDebugPanel from './ModularDebugPanel';
import { applyVisibility } from './engine/filters';
import { computeHopDistances } from './engine/forces';
import { buildClusterAnchors, groupNodesByCluster, type GroupingAxes } from './engine/layout';
import { buildGraphModel, type GraphModel } from './engine/model';
import type { SigmaGraphRenderer } from './engine/sigmaRenderer';
import { buildTreeIndex, defaultScopeIds, graphForScope, subtreeIds, type TreeIndex } from './engine/scope';
import { DEFAULT_FORCES, DEFAULT_SIMULATION_TUNING, LIVE_PHYSICS_NODE_THRESHOLD, resolvePhysicsPolicy, startGraphSimulation, type GraphSimulationHandle } from './engine/simulation';
import { ALL_KINDS, ALL_OWNERS, ALL_RELATIONS, ROOT_DIR_ID, type EdgeRelation, type ForceSettings, type GraphNode, type NodeKind, type NodeOwner, type PhysicsMode, type RawGraph, type SeedShape, type SimulationTuning } from './engine/types';
import styles from './ContentGraph.module.css';

type GraphResponse = components['schemas']['GraphResponse'];
type ToolRun = components['schemas']['ToolRun'];

const KIND_LABELS: Record<NodeKind, string> = {
	module: 'Modules', master_file: 'Master files overrides', core_file: 'Core files with markers',
	directory: 'Directories', file: 'Other files',
};
const OWNER_LABELS: Record<NodeOwner, string> = { nova: 'Nova', aphelion: 'Aphelion' };
const RELATION_LABELS: Record<EdgeRelation, string> = {
	master_files_mirror: 'Master files mirror', marker_edit: 'Marker edit', contains: 'Repository structure',
	module_reference: 'Module reference', core_reference: 'Core file reference',
};

export default function ContentGraphPage() {
	const [searchParams, setSearchParams] = useSearchParams();
	const [scope, setScope] = createSignal<ReadonlySet<string>>(new Set());
	const [scopeReady, setScopeReady] = createSignal(false);
	const [selectedNodeId, setSelectedNodeId] = createSignal<string | null>(null);
	const [hoveredNodeId, setHoveredNodeId] = createSignal<string | null>(null);
	const [statusMessage, setStatusMessage] = createSignal('Loading graph cache…');
	const [scanOutput, setScanOutput] = createSignal('');
	const [scanBusy, setScanBusy] = createSignal(false);
	const [refreshToken, setRefreshToken] = createSignal(1);
	const [explorerQuery, setExplorerQuery] = createSignal('');
	const [nodeQuery, setNodeQuery] = createSignal('');
	const [visibleKinds, setVisibleKinds] = createSignal<ReadonlySet<NodeKind>>(new Set(ALL_KINDS));
	const [visibleOwners, setVisibleOwners] = createSignal<ReadonlySet<NodeOwner>>(new Set(ALL_OWNERS));
	const [visibleRelations, setVisibleRelations] = createSignal<ReadonlySet<EdgeRelation>>(new Set(ALL_RELATIONS));
	const [degreeMin, setDegreeMin] = createSignal(0);
	const [degreeMax, setDegreeMax] = createSignal<number | null>(null);
	const [egoNodeId, setEgoNodeId] = createSignal<string | null>(null);
	const [focusEnabled, setFocusEnabled] = createSignal(false);
	const [focusNodeId, setFocusNodeId] = createSignal<string | null>(null);
	const [focusRingSpacing, setFocusRingSpacing] = createSignal(120);
	const [physicsMode, setPhysicsMode] = createSignal<PhysicsMode>('auto');
	const [physicsThreshold, setPhysicsThreshold] = createSignal(LIVE_PHYSICS_NODE_THRESHOLD);
	const [seedShape, setSeedShape] = createSignal<SeedShape>('auto');
	const [layoutRevision, setLayoutRevision] = createSignal(0);
	const [tableLimit, setTableLimit] = createSignal(100);
	const [allowPanWhileDragging, setAllowPanWhileDragging] = createSignal(false);
	const [grouping, setGrouping] = createStore<{ byKind: boolean; byOwner: boolean }>({ byKind: true, byOwner: true });
	const [spacing, setSpacing] = createStore({ autoScale: true, manualScale: 1, unlimited: false });
	const [forceSettings, setForceSettings] = createStore<ForceSettings>({ ...DEFAULT_FORCES });
	const [tuning, setTuning] = createStore<SimulationTuning>({ ...DEFAULT_SIMULATION_TUNING });
	const [dragTuning, setDragTuning] = createStore({ temperature: 0.06, repulsionMultiplier: 1 });
	let graphContainer!: HTMLDivElement;
	let renderer: SigmaGraphRenderer | null = null;
	let simulation: GraphSimulationHandle | null = null;

	const [graphResponse, { refetch: refetchGraph }] = createResource(refreshToken, () => api.get<GraphResponse>('/api/graph'));
	const rawGraph = createMemo<RawGraph | null>(() => {
		const graph = graphResponse()?.graph;
		return graph ? { nodes: graph.nodes, edges: graph.edges } : null;
	});
	const treeIndex = createMemo<TreeIndex | null>(() => rawGraph() ? buildTreeIndex(rawGraph()!) : null);

	createEffect(() => {
		const response = graphResponse();
		const graph = rawGraph();
		if (!response) return;
		if (!response.scanned || !graph) {
			setStatusMessage('No content graph has been scanned yet.');
			setScopeReady(false);
			return;
		}
		const manifest = response.manifest;
		setStatusMessage(manifest
			? `${manifest.node_count.toLocaleString()} nodes · ${manifest.edge_count.toLocaleString()} edges · revision ${manifest.game_repo_revision.slice(0, 12)}`
			: `${graph.nodes.length.toLocaleString()} nodes · ${graph.edges.length.toLocaleString()} edges`);
		if (!scopeReady()) {
			const initial = defaultScopeIds(graph);
			const deepLinked = typeof searchParams.selected === 'string' ? searchParams.selected : null;
			if (deepLinked && graph.nodes.some((node) => node.id === deepLinked)) initial.add(deepLinked);
			setScope(initial);
			setScopeReady(true);
			if (deepLinked) setSelectedNodeId(deepLinked);
		}
	});

	const scopedGraph = createMemo<RawGraph | null>(() => {
		const graph = rawGraph();
		return graph && scopeReady() ? graphForScope(graph, scope()) : null;
	});
	const model = createMemo<GraphModel | null>(() => {
		const graph = scopedGraph();
		if (!graph) return null;
		const revision = layoutRevision();
		return buildGraphModel(graph, {
			axes: { byKind: grouping.byKind, byOwner: grouping.byOwner }, spacing: { ...spacing },
			seedShape: seedShape(), seed: `${graphResponse()?.manifest?.snapshot_sha256 ?? 'graph'}:${revision}`,
		});
	});
	const egoDistances = createMemo(() => computeHopDistances(model()?.edges ?? [], egoNodeId()));
	const focusDistances = createMemo(() => computeHopDistances(model()?.edges ?? [], focusNodeId()));
	const scopeMaxDegree = createMemo(() => Math.max(0, ...(model()?.nodes ?? []).map((node) => node.degree)));

	createEffect(() => {
		const nodeId = selectedNodeId();
		if (!nodeId) {
			setSelectedContext(null);
			return;
		}
		const node = model()?.nodeById.get(nodeId);
		if (!node) return;
		setSelectedContext({
			tool: 'graph', record_kind: 'graph_node', record_id: node.id,
			module: node.moduleId, type_path: null, groups: [],
		});
	});

	function applyFiltersToModel(current = model()): void {
		if (!current) return;
		applyVisibility(current.nodes, current.edges, {
			kinds: visibleKinds(), owners: visibleOwners(), relations: visibleRelations(), search: nodeQuery(),
			degreeMin: degreeMin(), degreeMax: degreeMax(),
		});
		if (egoNodeId()) {
			const distances = egoDistances();
			for (const node of current.nodes) node.visible = node.id === egoNodeId() || distances.has(node.id);
		}
		renderer?.syncVisibility(visibleRelations(), egoNodeId() ? egoDistances() : null);
	}

	createEffect(() => {
		model(); visibleKinds(); visibleOwners(); visibleRelations(); nodeQuery(); degreeMin(); degreeMax(); egoNodeId();
		applyFiltersToModel();
	});

	onMount(() => {
		createEffect(() => {
			const current = model();
			const mode = physicsMode();
			const threshold = physicsThreshold();
			if (!current) return;
			applyFiltersToModel(current);
			simulation?.dispose(); renderer?.destroy(); simulation = null; renderer = null;
			let cancelled = false;
			const frame = window.requestAnimationFrame(async () => {
				if (cancelled || !graphContainer.clientWidth || !graphContainer.clientHeight) return;
				const { SigmaGraphRenderer: Renderer } = await import('./engine/sigmaRenderer');
				if (cancelled) return;
				renderer = new Renderer(graphContainer, current.nodes, current.edges, current.nodeById, {
					selectedNodeId, allowPanWhileDragging, onHover: setHoveredNodeId, onSelect: selectNode,
					onDragStart: () => simulation?.startDrag(dragTuning.temperature, dragTuning.repulsionMultiplier),
					onDragEnd: (_nodeId, moved) => {
						simulation?.endDrag();
						if (moved) simulation?.reheat(dragTuning.temperature);
					},
				});
				const groups = groupNodesByCluster(current.nodes, grouping);
				const maxClusterSize = Math.max(0, ...[...groups.values()].map((group) => group.length));
				const anchors = buildClusterAnchors(grouping, current.spacingScale, maxClusterSize);
				simulation = startGraphSimulation(current.nodes, current.edges, {
					settings: () => forceSettings, tuning: () => tuning, axes: () => grouping, anchors: () => anchors,
					focus: () => ({ enabled: focusEnabled(), nodeId: focusNodeId(), ringSpacing: focusRingSpacing(), distances: focusDistances() }),
				}, resolvePhysicsPolicy(mode, current.nodes.length, threshold), () => renderer?.syncPositions());
			});
			onCleanup(() => {
				cancelled = true; window.cancelAnimationFrame(frame); simulation?.dispose(); renderer?.destroy();
				simulation = null; renderer = null;
			});
		});
	});

	function selectNode(nodeId: string | null, modifierHeld = false): void {
		setSelectedNodeId(nodeId);
		setSearchParams({ selected: nodeId ?? undefined }, { replace: true });
		if (!nodeId) {
			setEgoNodeId(null); renderer?.refresh(); return;
		}
		const node = model()?.nodeById.get(nodeId);
		if (!node) return;
		if (focusEnabled()) {
			const previous = model()?.nodeById.get(focusNodeId() ?? '');
			if (previous) { previous.fx = null; previous.fy = null; }
			node.x = 0; node.y = 0; node.fx = 0; node.fy = 0; setFocusNodeId(nodeId); simulation?.reheat();
		}
		if (modifierHeld) setEgoNodeId(nodeId);
		renderer?.refresh();
	}

	function resetScope(): void { const graph = rawGraph(); if (graph) setScope(defaultScopeIds(graph)); }
	function toggleSubtree(nodeId: string, checked: boolean): void {
		const index = treeIndex(); if (!index) return;
		const next = new Set(scope());
		for (const id of subtreeIds(nodeId, index.childrenByParent)) checked ? next.add(id) : next.delete(id);
		setScope(next);
	}
	async function pollRun(runId: string): Promise<ToolRun> {
		for (;;) {
			const run = await api.get<ToolRun>(`/api/tools/runs/${encodeURIComponent(runId)}`);
			setScanOutput(run.output);
			if (run.status !== 'queued' && run.status !== 'running') return run;
			await new Promise((resolve) => window.setTimeout(resolve, 750));
		}
	}
	async function scanContent(): Promise<void> {
		setScanBusy(true); setStatusMessage('Scanning modular content…');
		try {
			const started = await api.post<ToolRun>('/api/tools/scan-content');
			const finished = await pollRun(started.run_id);
			if (finished.status !== 'succeeded') throw new Error(finished.output || `Scan ${finished.status}.`);
			setScopeReady(false); setRefreshToken((value) => value + 1); await refetchGraph();
			announceSuccess('Content graph scan complete.', 'content-graph');
		} catch (error) {
			setStatusMessage(error instanceof Error ? error.message : String(error)); announceError(error, 'content-graph');
		} finally { setScanBusy(false); }
	}
	function updateSet<T extends string>(current: ReadonlySet<T>, value: T, checked: boolean): ReadonlySet<T> {
		const next = new Set(current); checked ? next.add(value) : next.delete(value); return next;
	}
	function syncSimulation(): void { simulation?.syncSettings(); simulation?.reheat(); }
	function resetPhysics(): void {
		setForceSettings({ ...DEFAULT_FORCES }); setTuning({ ...DEFAULT_SIMULATION_TUNING });
		setDragTuning({ temperature: 0.06, repulsionMultiplier: 1 }); setGrouping({ byKind: true, byOwner: true });
		setSpacing({ autoScale: true, manualScale: 1, unlimited: false }); setPhysicsMode('auto');
		setPhysicsThreshold(LIVE_PHYSICS_NODE_THRESHOLD); setSeedShape('auto'); setFocusEnabled(false);
		setFocusNodeId(null); setFocusRingSpacing(120); setAllowPanWhileDragging(false); setLayoutRevision((value) => value + 1);
	}

	const visibleNodes = createMemo(() => model()?.nodes.filter((node) => node.visible) ?? []);
	const selectedNode = createMemo(() => model()?.nodeById.get(selectedNodeId() ?? '') ?? null);
	const hoveredNode = createMemo(() => model()?.nodeById.get(hoveredNodeId() ?? '') ?? null);
	const policy = createMemo(() => resolvePhysicsPolicy(physicsMode(), model()?.nodes.length ?? 0, physicsThreshold()));

	return <div class={styles.page}>
		<Card eyebrow="Modular content" heading="Content Graph">
			<p class={styles.status} role="status">{graphResponse.loading ? 'Loading graph cache…' : statusMessage()}</p>
			<div class={styles.buttonRow}><button type="button" disabled={scanBusy()} onClick={() => void scanContent()}>Scan modular content</button><button type="button" disabled={graphResponse.loading} onClick={() => void refetchGraph()}>Refresh from cache</button></div>
			<Show when={scanOutput()}>{(output) => <pre class={styles.output}>{output()}</pre>}</Show>
		</Card>
		<Show when={graphResponse.error}><p class={styles.error} role="alert">{graphResponse.error?.message}</p></Show>
		<Show when={rawGraph()} fallback={<EmptyGraph onScan={scanContent} busy={scanBusy()} />}>
			<div class={styles.graphLayout}>
				<aside class={styles.explorerPanel} aria-label="Graph explorer and filters">
					<details open><summary>Visibility filters</summary>
						<FilterGroup legend="Node kinds" values={ALL_KINDS} labels={KIND_LABELS} selected={visibleKinds} onChange={(value, checked) => setVisibleKinds(updateSet(visibleKinds(), value, checked))} />
						<FilterGroup legend="Owner" values={ALL_OWNERS} labels={OWNER_LABELS} selected={visibleOwners} onChange={(value, checked) => setVisibleOwners(updateSet(visibleOwners(), value, checked))} />
						<FilterGroup legend="Edge relations" values={ALL_RELATIONS} labels={RELATION_LABELS} selected={visibleRelations} onChange={(value, checked) => setVisibleRelations(updateSet(visibleRelations(), value, checked))} />
						<fieldset><legend>Connections</legend><NumericControl label="Minimum" value={degreeMin} min={0} max={scopeMaxDegree()} step={1} onInput={setDegreeMin} /><NumericControl label="Maximum" value={() => degreeMax() ?? scopeMaxDegree()} min={0} max={scopeMaxDegree()} step={1} onInput={(value) => setDegreeMax(value >= scopeMaxDegree() ? null : value)} /></fieldset>
						<fieldset><legend>Ego view</legend><p class={styles.metadata}>Ctrl/Cmd-click a node to isolate its connected component.</p><Show when={egoNodeId()}>{(id) => <p class={styles.metadata}>Isolated around {id()}.</p>}</Show><button type="button" onClick={() => setEgoNodeId(null)}>Clear ego view</button></fieldset>
					</details>
					<h2>Explorer</h2>
					<input type="search" placeholder="Filter files and folders" value={explorerQuery()} onInput={(event) => setExplorerQuery(event.currentTarget.value)} />
					<div class={styles.buttonRow}><button type="button" onClick={resetScope}>Default</button><button type="button" onClick={() => setScope(new Set(rawGraph()!.nodes.map((node) => node.id)))}>Tick all</button><button type="button" onClick={() => setScope(new Set())}>Untick all</button></div>
					<p class={styles.metadata}>{scope().size.toLocaleString()} of {rawGraph()!.nodes.length.toLocaleString()} nodes in scope.</p>
					<Explorer index={treeIndex()!} scope={scope} query={explorerQuery} onToggle={toggleSubtree} />
				</aside>
				<section class={styles.canvasPanel} aria-label="Interactive content graph">
					<div class={styles.canvasToolbar}><input type="search" placeholder="Module id, path, or label" value={nodeQuery()} onInput={(event) => setNodeQuery(event.currentTarget.value)} /><button type="button" onClick={() => renderer?.fitView()}>Fit view</button></div>
					<Show when={hoveredNode()}>{(node) => <div class={styles.tooltip}>{nodeLabel(node())} · {node().degree} connections</div>}</Show>
					<div ref={graphContainer} class={styles.graphCanvas} data-testid="content-graph-canvas" />
					<div class={styles.canvasStatus} aria-live="polite">{visibleNodes().length.toLocaleString()} visible · {model()?.nodes.length.toLocaleString()} in scope · {policy().live ? 'live physics' : policy().runInitialSettle ? 'settle then freeze' : 'packed static layout'}</div>
				</section>
				<NodeDetails node={selectedNode()} onFocus={() => { setFocusEnabled(true); if (selectedNodeId()) selectNode(selectedNodeId()); }} onEgo={() => setEgoNodeId(selectedNodeId())} />
			</div>
			<PhysicsPanel mode={physicsMode} threshold={physicsThreshold} seed={seedShape} grouping={grouping} spacing={spacing} forces={forceSettings} tuning={tuning} dragTuning={dragTuning} focusEnabled={focusEnabled} focusRingSpacing={focusRingSpacing} allowPan={allowPanWhileDragging}
				onMode={setPhysicsMode} onThreshold={setPhysicsThreshold} onSeed={setSeedShape} onGrouping={(key, value) => setGrouping(key, value)} onSpacing={(key, value) => setSpacing(key, value)} onForce={(key, value) => { setForceSettings(key, value); syncSimulation(); }} onTuning={(key, value) => { setTuning(key, value as never); syncSimulation(); }} onDrag={(key, value) => setDragTuning(key, value)}
				onFocusEnabled={(enabled) => { setFocusEnabled(enabled); if (!enabled) setFocusNodeId(null); simulation?.reheat(); }} onFocusRingSpacing={(value) => { setFocusRingSpacing(value); simulation?.reheat(); }} onAllowPan={setAllowPanWhileDragging} onRegenerate={() => setLayoutRevision((value) => value + 1)} onReset={resetPhysics} onJiggle={() => simulation?.jiggle()} stats={`${model()?.nodes.length.toLocaleString()} nodes · ${model()?.edges.length.toLocaleString()} edges · ${model()?.seedShape} seed · ${model()?.spacingScale.toFixed(2)}× spacing`} />
			<AccessibleNodeTable nodes={visibleNodes()} limit={tableLimit} selected={selectedNodeId} onSelect={(id) => selectNode(id)} onMore={() => setTableLimit((value) => value + 100)} />
			<ModularDebugPanel scanned={Boolean(graphResponse()?.scanned)} refreshToken={refreshToken()} onRescan={scanContent} />
		</Show>
	</div>;
}

function nodeLabel(node: GraphNode): string { return node.name ?? node.moduleId ?? node.path ?? node.id; }
function EmptyGraph(props: { readonly onScan: () => Promise<void>; readonly busy: boolean }) {
	return <Card heading="No graph cache"><p class={styles.metadata}>Run the scanner once to build the local derived graph.</p><button type="button" disabled={props.busy} onClick={() => void props.onScan()}>Scan now</button></Card>;
}
function FilterGroup<T extends string>(props: { readonly legend: string; readonly values: readonly T[]; readonly labels: Record<T, string>; readonly selected: Accessor<ReadonlySet<T>>; readonly onChange: (value: T, checked: boolean) => void }) {
	return <fieldset><legend>{props.legend}</legend><For each={props.values}>{(value) => <label class={styles.checkbox}><input type="checkbox" checked={props.selected().has(value)} onChange={(event) => props.onChange(value, event.currentTarget.checked)} /><span>{props.labels[value]}</span></label>}</For></fieldset>;
}

function Explorer(props: { readonly index: TreeIndex; readonly scope: Accessor<ReadonlySet<string>>; readonly query: Accessor<string>; readonly onToggle: (nodeId: string, checked: boolean) => void }) {
	const query = () => props.query().trim().toLowerCase();
	const matches = createMemo(() => query() ? [...props.index.nodeById.values()].filter((node) => `${node.name ?? ''} ${node.path ?? ''} ${node.module_id ?? ''} ${node.id}`.toLowerCase().includes(query())).slice(0, 250) : []);
	const rootIds = () => props.index.nodeById.has(ROOT_DIR_ID) ? [ROOT_DIR_ID] : [...props.index.nodeById.keys()].filter((id) => !props.index.parentByChild.has(id)).slice(0, 100);
	return <div class={styles.explorerTree} role="tree"><Show when={query()} fallback={<For each={rootIds()}>{(id) => <ExplorerNode nodeId={id} index={props.index} scope={props.scope} onToggle={props.onToggle} depth={0} />}</For>}><p class={styles.metadata}>{matches().length === 250 ? 'First 250 matches' : `${matches().length} matches`}</p><For each={matches()}>{(node) => <label class={styles.searchMatch}><input type="checkbox" checked={props.scope().has(node.id)} onChange={(event) => props.onToggle(node.id, event.currentTarget.checked)} /><span>{node.name ?? node.module_id ?? node.path ?? node.id}</span></label>}</For></Show></div>;
}
function ExplorerNode(props: { readonly nodeId: string; readonly index: TreeIndex; readonly scope: Accessor<ReadonlySet<string>>; readonly onToggle: (nodeId: string, checked: boolean) => void; readonly depth: number }) {
	const [expanded, setExpanded] = createSignal(props.nodeId === ROOT_DIR_ID);
	const node = () => props.index.nodeById.get(props.nodeId);
	const children = () => props.index.childrenByParent.get(props.nodeId) ?? [];
	return <div role="treeitem" aria-expanded={children().length ? expanded() : undefined}><div class={styles.treeRow} style={{ 'padding-left': `${props.depth * 0.75}rem` }}><button type="button" class={styles.disclosure} disabled={!children().length} aria-label={expanded() ? 'Collapse' : 'Expand'} onClick={() => setExpanded((value) => !value)}>{children().length ? expanded() ? '−' : '+' : '·'}</button><input type="checkbox" aria-label={`Include ${node()?.name ?? props.nodeId}`} checked={props.scope().has(props.nodeId)} onChange={(event) => props.onToggle(props.nodeId, event.currentTarget.checked)} /><span title={node()?.path ?? props.nodeId}>{node()?.name ?? node()?.module_id ?? node()?.path ?? props.nodeId}</span></div><Show when={expanded()}><div role="group"><For each={children()}>{(child) => <ExplorerNode nodeId={child} index={props.index} scope={props.scope} onToggle={props.onToggle} depth={props.depth + 1} />}</For></div></Show></div>;
}

function NodeDetails(props: { readonly node: GraphNode | null; readonly onFocus: () => void; readonly onEgo: () => void }) {
	async function pin(): Promise<void> {
		if (!props.node) return;
		try { await addReference({ tool: 'graph', kind: 'graph_node', key: props.node.id, label: nodeLabel(props.node), path: props.node.path }); announceSuccess('Added graph node to shared references.', 'content-graph'); }
		catch (error) { announceError(error, 'content-graph'); }
	}
	return <aside class={styles.detailPanel} aria-label="Selected node details"><h2>Details</h2><Show when={props.node} fallback={<p class={styles.metadata}>Click a node or choose it from the accessible table.</p>}>{(node) => <><h3>{nodeLabel(node())}</h3><dl class={styles.details}><dt>Kind</dt><dd>{node().kind}</dd><dt>Owner</dt><dd>{node().owner ?? '—'}</dd><dt>Connections</dt><dd>{node().degree}</dd><dt>Path</dt><dd>{node().path ?? '—'}</dd><Show when={node().markerCount}><><dt>Markers</dt><dd>{node().markerCount}</dd></></Show></dl><div class={styles.buttonRow}><button type="button" onClick={() => void pin()}>Add to references</button><button type="button" onClick={props.onFocus}>Focus rings</button><button type="button" onClick={props.onEgo}>Ego view</button></div><Show when={node().path}>{(path) => <OpenFileActions label="File" repository="game" path={path()} />}</Show><Show when={node().corePath}>{(path) => <OpenFileActions label="Core file" repository="game" path={path()} />}</Show></>}</Show></aside>;
}
function AccessibleNodeTable(props: { readonly nodes: readonly GraphNode[]; readonly limit: Accessor<number>; readonly selected: Accessor<string | null>; readonly onSelect: (id: string) => void; readonly onMore: () => void }) {
	return <details class={styles.tableFallback}><summary>Accessible node list ({props.nodes.length.toLocaleString()} visible)</summary><div class={styles.tableScroll}><table><thead><tr><th>Node</th><th>Kind</th><th>Owner</th><th>Connections</th><th>Action</th></tr></thead><tbody><For each={props.nodes.slice(0, props.limit())}>{(node) => <tr aria-selected={props.selected() === node.id}><td>{nodeLabel(node)}</td><td>{node.kind}</td><td>{node.owner ?? '—'}</td><td>{node.degree}</td><td><button type="button" onClick={() => props.onSelect(node.id)}>Inspect</button></td></tr>}</For></tbody></table></div><Show when={props.limit() < props.nodes.length}><button type="button" onClick={props.onMore}>Show 100 more</button></Show></details>;
}
function NumericControl(props: { readonly label: string; readonly value: Accessor<number>; readonly min: number; readonly max: number; readonly step: number; readonly onInput: (value: number) => void; readonly range?: boolean }) {
	return <label class={styles.control}><span>{props.label} <output>{props.value()}</output></span><input type={props.range === false ? 'number' : 'range'} min={props.min} max={props.max} step={props.step} value={props.value()} onInput={(event) => props.onInput(Number(event.currentTarget.value))} /></label>;
}

interface PhysicsPanelProps {
	readonly mode: Accessor<PhysicsMode>; readonly threshold: Accessor<number>; readonly seed: Accessor<SeedShape>;
	readonly grouping: GroupingAxes; readonly spacing: { autoScale: boolean; manualScale: number; unlimited: boolean };
	readonly forces: ForceSettings; readonly tuning: SimulationTuning; readonly dragTuning: { temperature: number; repulsionMultiplier: number };
	readonly focusEnabled: Accessor<boolean>; readonly focusRingSpacing: Accessor<number>; readonly allowPan: Accessor<boolean>;
	readonly onMode: (value: PhysicsMode) => void; readonly onThreshold: (value: number) => void; readonly onSeed: (value: SeedShape) => void;
	readonly onGrouping: (key: keyof GroupingAxes, value: boolean) => void; readonly onSpacing: (key: 'autoScale' | 'manualScale' | 'unlimited', value: boolean | number) => void;
	readonly onForce: (key: keyof ForceSettings, value: number) => void; readonly onTuning: (key: keyof SimulationTuning, value: number | boolean) => void;
	readonly onDrag: (key: 'temperature' | 'repulsionMultiplier', value: number) => void; readonly onFocusEnabled: (value: boolean) => void; readonly onFocusRingSpacing: (value: number) => void;
	readonly onAllowPan: (value: boolean) => void; readonly onRegenerate: () => void; readonly onReset: () => void; readonly onJiggle: () => void; readonly stats: string;
}
function PhysicsPanel(props: PhysicsPanelProps) {
	const bool = (label: string, checked: boolean, change: (value: boolean) => void) => <label class={styles.checkbox}><input type="checkbox" checked={checked} onChange={(event) => change(event.currentTarget.checked)} /><span>{label}</span></label>;
	return <details class={styles.physicsPanel}><summary>Physics and layout</summary><div class={styles.buttonRow}><button type="button" onClick={props.onRegenerate}>Regenerate layout</button><button type="button" onClick={props.onReset}>Reset defaults</button></div><div class={styles.physicsGrid}>
		<fieldset><legend>Mode</legend><For each={['auto', 'on', 'off'] as const}>{(mode) => <label class={styles.checkbox}><input type="radio" name="physics-mode" value={mode} checked={props.mode() === mode} onChange={() => props.onMode(mode)} /><span>{mode === 'auto' ? 'Auto' : mode === 'on' ? 'On' : 'Off'}</span></label>}</For><NumericControl label="Live threshold" value={props.threshold} min={100} max={50000} step={100} range={false} onInput={props.onThreshold} /></fieldset>
		<fieldset><legend>Layout</legend>{bool('Group by kind', props.grouping.byKind, (value) => props.onGrouping('byKind', value))}{bool('Group by owner', props.grouping.byOwner, (value) => props.onGrouping('byOwner', value))}<NumericControl label="Group strength" value={() => props.forces.clusterStrength} min={0} max={0.08} step={0.002} onInput={(value) => props.onForce('clusterStrength', value)} />{bool('Auto-scale spacing', props.spacing.autoScale, (value) => props.onSpacing('autoScale', value))}<NumericControl label="Manual spacing" value={() => props.spacing.manualScale} min={0.5} max={1000} step={0.5} onInput={(value) => props.onSpacing('manualScale', value)} />{bool('Unlimited spacing', props.spacing.unlimited, (value) => props.onSpacing('unlimited', value))}<label class={styles.control}><span>Initial seed</span><select value={props.seed()} onChange={(event) => props.onSeed(event.currentTarget.value as SeedShape)}><option value="auto">Auto</option><option value="spiral">Spiral</option><option value="packed">Packed grid</option><option value="grid">Global grid</option><option value="random">Random scatter</option></select></label></fieldset>
		<fieldset><legend>Focus</legend>{bool('Organize around selected node', props.focusEnabled(), props.onFocusEnabled)}<NumericControl label="Ring spacing" value={props.focusRingSpacing} min={20} max={500} step={10} onInput={props.onFocusRingSpacing} /></fieldset>
		<fieldset><legend>Forces</legend><NumericControl label="Repel force" value={() => props.forces.repulsion} min={500} max={12000} step={100} onInput={(value) => props.onForce('repulsion', value)} />{bool('Weight repel by degree', props.tuning.chargeByDegree, (value) => props.onTuning('chargeByDegree', value))}<NumericControl label="Degree weight" value={() => props.tuning.chargeByDegreeFactor} min={0} max={1} step={0.05} onInput={(value) => props.onTuning('chargeByDegreeFactor', value)} /><NumericControl label="Link force" value={() => props.forces.springStrength} min={0.002} max={0.08} step={0.002} onInput={(value) => props.onForce('springStrength', value)} /><NumericControl label="Link distance" value={() => props.forces.springLength} min={20} max={200} step={5} onInput={(value) => props.onForce('springLength', value)} /><NumericControl label="Center force" value={() => props.forces.center} min={0} max={0.02} step={0.001} onInput={(value) => props.onForce('center', value)} /><NumericControl label="Isolated pull" value={() => props.forces.isolatedPull} min={1} max={15} step={0.5} onInput={(value) => props.onForce('isolatedPull', value)} /><NumericControl label="Repel approximation" value={() => props.tuning.theta} min={0.1} max={1.5} step={0.05} onInput={(value) => props.onTuning('theta', value)} /></fieldset>
		<fieldset><legend>Collision</legend>{bool('Prevent node overlap', props.tuning.collideEnabled, (value) => props.onTuning('collideEnabled', value))}<NumericControl label="Padding" value={() => props.tuning.collidePadding} min={0} max={20} step={1} onInput={(value) => props.onTuning('collidePadding', value)} /><NumericControl label="Strength" value={() => props.tuning.collideStrength} min={0} max={1} step={0.05} onInput={(value) => props.onTuning('collideStrength', value)} /><NumericControl label="Hub buffer" value={() => props.tuning.hubCollisionBuffer} min={0} max={10} step={0.5} onInput={(value) => props.onTuning('hubCollisionBuffer', value)} /></fieldset>
		<fieldset><legend>Motion</legend><NumericControl label="Friction" value={() => props.tuning.velocityDecay} min={0.05} max={0.9} step={0.05} onInput={(value) => props.onTuning('velocityDecay', value)} /><NumericControl label="Settle speed" value={() => props.tuning.alphaDecay} min={0.005} max={0.2} step={0.005} onInput={(value) => props.onTuning('alphaDecay', value)} /><NumericControl label="Ambient motion" value={() => props.tuning.ambientAlpha} min={0.005} max={0.3} step={0.005} onInput={(value) => props.onTuning('ambientAlpha', value)} /><NumericControl label="Shake strength" value={() => props.tuning.jiggleStrength} min={20} max={1000} step={20} onInput={(value) => props.onTuning('jiggleStrength', value)} /><button type="button" onClick={props.onJiggle}>Jiggle simulation</button></fieldset>
		<fieldset><legend>Dragging</legend><NumericControl label="Responsiveness" value={() => props.dragTuning.temperature} min={0.02} max={0.5} step={0.02} onInput={(value) => props.onDrag('temperature', value)} /><NumericControl label="Repel boost" value={() => props.dragTuning.repulsionMultiplier} min={1} max={6} step={0.5} onInput={(value) => props.onDrag('repulsionMultiplier', value)} />{bool('Allow camera pan while dragging', props.allowPan(), props.onAllowPan)}</fieldset>
		<fieldset><legend>Performance</legend><p class={styles.metadata}>{props.stats}</p></fieldset>
	</div></details>;
}

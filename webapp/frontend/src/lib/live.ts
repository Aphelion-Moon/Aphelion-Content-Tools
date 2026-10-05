import { api } from './api';
import { createAsyncScope } from './asyncScope';
import { setActiveRuns, setConnected, setHealth, setWorkspaceRevision, setDefinitionRuns, type DefinitionRun, type ActiveRun, type StoreHealth, type WorkspaceRevision } from '~/store/appStore';
import { reportParsec } from './parsec/coordinator';

// One live-update connection for the whole app, feeding the shared store.
//
// Pre-rewrite every widget ran its own 5-second setInterval against /api/store/health and
// /api/tools/active, so N open tool views meant N times the polling for identical data.
//
// The WebSocket endpoint is added as part of the FastAPI backend rewrite. Until it exists, this falls
// back to a single shared poll -- one timer for the whole app rather than one per widget, which is
// already the structural win; the socket then removes the latency.

const POLL_INTERVAL_MS = 5000;
const RECONNECT_DELAY_MS = 2000;

interface ActivePayload {
	readonly active_runs: readonly ActiveRun[];
}

export type LiveMessage =
	| { readonly type: 'health'; readonly data: StoreHealth }
	| { readonly type: 'active_runs'; readonly data: readonly ActiveRun[] }
	| { readonly type: 'definition_runs'; readonly data: readonly DefinitionRun[] }
	| { readonly type: 'workspace_revision'; readonly data: WorkspaceRevision | null };

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null;
}

function isWorkspaceRevision(value: unknown): value is WorkspaceRevision {
	if (!isRecord(value)) return false;
	const projection = value.projection_revision;
	const game = value.game_source;
	return typeof value.worktree_id === 'string'
		&& typeof value.branch === 'string'
		&& typeof value.head === 'string'
		&& typeof value.content_revision === 'string'
		&& (value.projection_generation_id === null || typeof value.projection_generation_id === 'string')
		&& (game === null || (isRecord(game) && typeof game.worktree_id === 'string' && typeof game.head === 'string'
			&& (game.dirty == null || typeof game.dirty === 'boolean')
			&& (game.graph_observation == null || typeof game.graph_observation === 'string')))
		&& (projection === null || (isRecord(projection)
			&& typeof projection.schema_version === 'number'
			&& typeof projection.content_revision === 'string'
			&& typeof projection.embedding_model_id === 'string'
			&& (projection.state === 'current' || projection.state === 'stale')));
}

async function pollOnce(isCurrent: () => boolean): Promise<void> {
	try {
		const [health, active, revision, definitions] = await Promise.all([
			api.get<StoreHealth>('/api/store/health'),
			api.get<ActivePayload>('/api/tools/active'),
			api.get<WorkspaceRevision | null>('/api/workspace/revision'),
			api.get<DefinitionRun[]>('/api/definitions/runs').catch(() => []),
		]);
		if (!isCurrent()) return;
		setHealth(health);
		setActiveRuns(active.active_runs ?? []);
		if (Array.isArray(definitions)) setDefinitionRuns(definitions);
		if (revision === null || isWorkspaceRevision(revision)) setWorkspaceRevision(revision);
		setConnected(true);
	} catch {
		// A failed poll means the backend is down or restarting; surface it in the shell rather than
		// throwing into an unhandled rejection. The next tick retries.
		if (isCurrent()) setConnected(false);
	}
}

function startPolling(): () => void {
	const scope = createAsyncScope();
	const isCurrent = scope.capture();
	let timer: ReturnType<typeof setTimeout> | undefined;
	const tick = async () => {
		await pollOnce(isCurrent);
		if (isCurrent()) timer = setTimeout(() => void tick(), POLL_INTERVAL_MS);
	};
	void tick();
	return () => { scope.dispose(); clearTimeout(timer); setConnected(false); };
}

function startSocket(url: string): () => void {
	let socket: WebSocket | undefined;
	let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
	let stopped = false;
	let hasConnected = false;

	const open = () => {
		if (stopped) return;
		const currentSocket = new WebSocket(url);
		socket = currentSocket;
		const isCurrent = () => !stopped && socket === currentSocket;

		currentSocket.addEventListener('open', () => {
			if (!isCurrent()) return;
			setConnected(true);
			reportParsec({
				type: 'connection',
				phase: hasConnected ? 'recovered' : 'connected',
				tool: 'live',
				dedupeKey: 'live-connection',
			});
			hasConnected = true;
		});

		currentSocket.addEventListener('message', (event: MessageEvent<string>) => {
			if (!isCurrent()) return;
			try {
				const payload = JSON.parse(event.data) as LiveMessage;
				if (payload.type === 'health') setHealth(payload.data as StoreHealth);
				else if (payload.type === 'active_runs') setActiveRuns(payload.data as readonly ActiveRun[]);
				else if (payload.type === 'definition_runs' && Array.isArray(payload.data)) setDefinitionRuns(payload.data);
				else if (payload.type === 'workspace_revision' && (payload.data === null || isWorkspaceRevision(payload.data))) setWorkspaceRevision(payload.data);
			} catch {
				// Ignore malformed frames rather than tearing down a working connection.
			}
		});

		const scheduleReconnect = () => {
			if (!isCurrent()) return;
			setConnected(false);
			reportParsec({
				type: 'connection',
				phase: 'disconnected',
				tool: 'live',
				dedupeKey: 'live-connection',
			});
			socket = undefined;
			if (stopped) return;
			reconnectTimer = setTimeout(open, RECONNECT_DELAY_MS);
		};

		currentSocket.addEventListener('close', scheduleReconnect);
		currentSocket.addEventListener('error', () => { if (isCurrent()) currentSocket.close(); });
	};

	open();

	return () => {
		stopped = true;
		setConnected(false);
		if (reconnectTimer !== undefined) clearTimeout(reconnectTimer);
		socket?.close();
	};
}

/** Begin receiving live backend state. Returns a disposer. */
export function connectLiveUpdates(): () => void {
	// The socket is the normal path. Polling remains as the fallback for environments without WebSocket
	// support, and can be forced with VITE_USE_WEBSOCKET=false to isolate socket problems during
	// development.
	const socketDisabled = import.meta.env['VITE_USE_WEBSOCKET'] === 'false';
	if (!socketDisabled && typeof WebSocket !== 'undefined') {
		const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
		return startSocket(`${protocol}//${window.location.host}/ws`);
	}
	return startPolling();
}

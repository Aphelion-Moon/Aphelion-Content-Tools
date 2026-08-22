import { api } from './api';
import { setActiveRuns, setConnected, setHealth, type ActiveRun, type StoreHealth } from '~/store/appStore';

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

async function pollOnce(): Promise<void> {
	try {
		const [health, active] = await Promise.all([
			api.get<StoreHealth>('/api/store/health'),
			api.get<ActivePayload>('/api/tools/active'),
		]);
		setHealth(health);
		setActiveRuns(active.active_runs ?? []);
		setConnected(true);
	} catch {
		// A failed poll means the backend is down or restarting; surface it in the shell rather than
		// throwing into an unhandled rejection. The next tick retries.
		setConnected(false);
	}
}

function startPolling(): () => void {
	void pollOnce();
	const timer = setInterval(() => void pollOnce(), POLL_INTERVAL_MS);
	return () => clearInterval(timer);
}

function startSocket(url: string): () => void {
	let socket: WebSocket | undefined;
	let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
	let stopped = false;

	const open = () => {
		if (stopped) return;
		socket = new WebSocket(url);

		socket.addEventListener('open', () => setConnected(true));

		socket.addEventListener('message', (event: MessageEvent<string>) => {
			try {
				const payload = JSON.parse(event.data) as { type: string; data: unknown };
				if (payload.type === 'health') setHealth(payload.data as StoreHealth);
				else if (payload.type === 'active_runs') setActiveRuns(payload.data as readonly ActiveRun[]);
			} catch {
				// Ignore malformed frames rather than tearing down a working connection.
			}
		});

		const scheduleReconnect = () => {
			setConnected(false);
			socket = undefined;
			if (stopped) return;
			reconnectTimer = setTimeout(open, RECONNECT_DELAY_MS);
		};

		socket.addEventListener('close', scheduleReconnect);
		socket.addEventListener('error', () => socket?.close());
	};

	open();

	return () => {
		stopped = true;
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

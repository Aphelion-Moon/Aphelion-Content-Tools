import { afterEach, describe, expect, it, vi } from 'vitest';
import { appState, setSelectedContext, setWorkspaceRevision } from '~/store/appStore';
import { dismissParsec } from './parsec/coordinator';
import { connectLiveUpdates } from './live';
import { api } from './api';
import * as coordinator from './parsec/coordinator';

class FakeWebSocket {
	static instances: FakeWebSocket[] = [];
	readonly listeners = new Map<string, Array<(event: Event) => void>>();

	constructor(readonly url: string) {
		FakeWebSocket.instances.push(this);
	}

	addEventListener(type: string, listener: (event: Event) => void): void {
		const listeners = this.listeners.get(type) ?? [];
		listeners.push(listener);
		this.listeners.set(type, listeners);
	}

	emit(type: string): void {
		for (const listener of this.listeners.get(type) ?? []) listener(new Event(type));
	}

	emitMessage(payload: unknown): void {
		const event = { data: JSON.stringify(payload) } as MessageEvent<string>;
		for (const listener of this.listeners.get('message') ?? []) listener(event);
	}

	close(): void {}
}

afterEach(() => {
	dismissParsec();
	FakeWebSocket.instances = [];
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
	vi.useRealTimers();
	setSelectedContext(null);
	setWorkspaceRevision(null);
});

describe('live connection Parsec feedback', () => {
	it('ignores callbacks from a disposed socket owner', () => {
		const report = vi.spyOn(coordinator, 'reportParsec').mockReturnValue(0);
		vi.stubGlobal('WebSocket', FakeWebSocket);
		const disconnect = connectLiveUpdates();
		const first = FakeWebSocket.instances[0]!;
		first.emit('open');
		disconnect();
		dismissParsec();
		report.mockClear();
		first.emit('open');
		first.emit('close');
		expect(appState.parsecFeedback).toBeNull();
		expect(report).not.toHaveBeenCalled();
		expect(appState.connected).toBe(false);
	});
	it('does not overlap slow fallback polls or apply a result after disposal', async () => {
		vi.useFakeTimers();
		vi.stubGlobal('WebSocket', undefined);
		let resolveHealth!: (value: unknown) => void;
		const get = vi.spyOn(api, 'get').mockImplementation((path: string) => path.endsWith('/health')
			? new Promise((resolve) => { resolveHealth = resolve; }) : path.endsWith('/active')
				? Promise.resolve({ active_runs: [] }) : Promise.resolve({ worktree_id: 'w', branch: 'main', head: 'h', content_revision: 'c', projection_revision: null, projection_generation_id: null, game_source: null }));
		const disconnect = connectLiveUpdates();
		await vi.advanceTimersByTimeAsync(15000);
		expect(get).toHaveBeenCalledTimes(4);
		expect(get).toHaveBeenCalledWith('/api/definitions/runs');
		disconnect();
		resolveHealth({ total_rows: 99, disk_bytes: 0, tables: {} });
		await vi.advanceTimersByTimeAsync(1);
		expect(appState.connected).toBe(false);
	});

	it('uses the revision endpoint during polling and clears stale selected context', async () => {
		vi.useFakeTimers();
		vi.stubGlobal('WebSocket', undefined);
		setWorkspaceRevision({ worktree_id: 'worktree', branch: 'main', head: 'head-1', content_revision: 'content-1', projection_revision: null, projection_generation_id: null, game_source: null });
		setSelectedContext({ tool: 'lore-editor', record_kind: 'catalog_target', record_id: '/obj/item/radio', type_path: '/obj/item/radio', groups: [], module: null });
		const get = vi.spyOn(api, 'get').mockImplementation((path: string) => {
			if (path.endsWith('/health')) return Promise.resolve({ total_rows: 0, disk_bytes: 0, tables: {}, workspace: {} });
			if (path.endsWith('/active')) return Promise.resolve({ active_runs: [] });
			return Promise.resolve({ worktree_id: 'worktree', branch: 'main', head: 'head-2', content_revision: 'content-2', projection_revision: null, projection_generation_id: null, game_source: null });
		});
		const disconnect = connectLiveUpdates();
		await vi.advanceTimersByTimeAsync(1);

		expect(get).toHaveBeenCalledWith('/api/workspace/revision');
		expect(appState.workspaceRevision?.head).toBe('head-2');
		expect(appState.selectedContext).toBeNull();
		disconnect();
	});
	it('reports initial connection, loss, and recovery without moving durable connection state', async () => {
		vi.useFakeTimers();
		vi.stubGlobal('WebSocket', FakeWebSocket);
		const disconnect = connectLiveUpdates();
		const first = FakeWebSocket.instances[0]!;

		first.emit('open');
		expect(appState.connected).toBe(true);
		expect(appState.parsecFeedback?.text).toContain('Live station link connected');

		dismissParsec();
		first.emit('close');
		expect(appState.connected).toBe(false);
		expect(appState.parsecFeedback?.text).toContain('lost the live station link');

		dismissParsec();
		await vi.advanceTimersByTimeAsync(2000);
		const second = FakeWebSocket.instances[1]!;
		second.emit('open');
		expect(appState.connected).toBe(true);
		expect(appState.parsecFeedback?.text).toContain('recovered');
		disconnect();
	});

	it('publishes workspace revisions and clears stale selected context', () => {
		setWorkspaceRevision({ worktree_id: 'worktree', branch: 'main', head: 'head-1', content_revision: 'content-1', projection_revision: null, projection_generation_id: null, game_source: null });
		setSelectedContext({
			tool: 'lore-editor',
			record_kind: 'catalog_target',
			record_id: '/obj/item/radio',
			type_path: '/obj/item/radio',
			groups: [],
			module: null,
		});
		vi.stubGlobal('WebSocket', FakeWebSocket);
		const disconnect = connectLiveUpdates();
		FakeWebSocket.instances[0]!.emitMessage({
			type: 'workspace_revision',
			data: { worktree_id: 'worktree', branch: 'main', head: 'head-2', content_revision: 'content-2', projection_revision: null, projection_generation_id: null, game_source: null },
		});

		expect(appState.workspaceRevision?.head).toBe('head-2');
		expect(appState.selectedContext).toBeNull();
		disconnect();
	});

	it('invalidates selected context when revision becomes unavailable and accepts recovery', () => {
		const revision = { worktree_id: 'worktree', branch: 'main', head: 'head', content_revision: 'content', projection_revision: null, projection_generation_id: null, game_source: null };
		setWorkspaceRevision(revision);
		setSelectedContext({ tool: 'content-graph', record_kind: 'module', record_id: 'example', groups: [] });
		vi.stubGlobal('WebSocket', FakeWebSocket);
		const disconnect = connectLiveUpdates();
		FakeWebSocket.instances[0]!.emitMessage({ type: 'workspace_revision', data: null });
		expect(appState.workspaceRevision).toBeNull();
		expect(appState.selectedContext).toBeNull();
		FakeWebSocket.instances[0]!.emitMessage({ type: 'workspace_revision', data: revision });
		expect(appState.workspaceRevision).toEqual(revision);
		expect(appState.selectedContext).toBeNull();
		disconnect();
	});

	it('invalidates selected context when game source changes at the same HEAD', () => {
		const revision = { worktree_id: 'tool', branch: 'main', head: 'tool-head', content_revision: 'content', projection_revision: null, projection_generation_id: 'generation', game_source: { worktree_id: 'game', head: 'game-head', dirty: true, graph_observation: 'before' } };
		setWorkspaceRevision(revision);
		setSelectedContext({ tool: 'content-graph', record_kind: 'module', record_id: 'example', groups: [] });
		vi.stubGlobal('WebSocket', FakeWebSocket);
		const disconnect = connectLiveUpdates();
		FakeWebSocket.instances[0]!.emitMessage({ type: 'workspace_revision', data: { ...revision, game_source: { ...revision.game_source, graph_observation: 'after' } } });
		expect(appState.workspaceRevision?.game_source?.graph_observation).toBe('after');
		expect(appState.selectedContext).toBeNull();
		disconnect();
	});

	it('ignores malformed workspace revision frames', () => {
		// The new identity fields are required: old or malformed frames cannot silently keep stale context.
		setWorkspaceRevision({ worktree_id: 'worktree', branch: 'main', head: 'head-1', content_revision: 'content-1', projection_revision: null, projection_generation_id: null, game_source: null });
		vi.stubGlobal('WebSocket', FakeWebSocket);
		const disconnect = connectLiveUpdates();
		FakeWebSocket.instances[0]!.emitMessage({ type: 'workspace_revision', data: { head: 42 } });

		expect(appState.workspaceRevision?.head).toBe('head-1');
		disconnect();
	});
});

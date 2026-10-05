import { createEffect, createRoot } from 'solid-js';
import { appState } from '~/store/appStore';
import { reportParsec } from './coordinator';
import { canEmitIdle, type IdleEligibilityContext } from './policy';
import { readIdleChatterPreference } from './settings';
import type { IdleChatterPreference, ParsecEvent } from './types';

const INTERVALS: Record<Exclude<IdleChatterPreference, 'off'>, readonly [number, number]> = {
	rare: [480_000, 720_000],
	occasional: [240_000, 420_000],
	frequent: [120_000, 240_000],
};

export interface IdleSchedulerSnapshot extends IdleEligibilityContext {
	readonly route: string;
	readonly contextKey: string;
}

export interface IdleSchedulerEnvironment<TimerHandle> {
	readonly readPreference: () => IdleChatterPreference;
	readonly readSnapshot: () => IdleSchedulerSnapshot;
	readonly random: () => number;
	readonly setTimer: (callback: () => void, delayMs: number) => TimerHandle;
	readonly clearTimer: (handle: TimerHandle) => void;
	readonly report: (event: ParsecEvent) => void;
	readonly subscribeContext: (listener: () => void) => () => void;
}

export function nextIdleDelayMs(preference: IdleChatterPreference, random = Math.random()): number | null {
	if (preference === 'off') return null;
	const [minimum, maximum] = INTERVALS[preference];
	const boundedRandom = Math.min(1, Math.max(0, random));
	return Math.min(maximum, Math.floor(minimum + boundedRandom * (maximum - minimum + 1)));
}

export function createParsecIdleScheduler<TimerHandle>(environment: IdleSchedulerEnvironment<TimerHandle>): () => void {
	let timer: TimerHandle | undefined;
	let stopped = false;
	const nextLineByRoute = new Map<string, number>();

	const schedule = (): void => {
		if (timer !== undefined) environment.clearTimer(timer);
		timer = undefined;
		if (stopped) return;
		const delayMs = nextIdleDelayMs(environment.readPreference(), environment.random());
		if (delayMs === null) return;
		timer = environment.setTimer(() => {
			timer = undefined;
			const snapshot = environment.readSnapshot();
			if (canEmitIdle(snapshot)) {
				const lineIndex = nextLineByRoute.get(snapshot.route) ?? 0;
				environment.report({
					type: 'idle',
					phase: 'contextual',
					tool: 'parsec',
					route: snapshot.route,
					lineIndex,
				});
				nextLineByRoute.set(snapshot.route, lineIndex + 1);
			}
			schedule();
		}, delayMs);
	};

	schedule();
	const unsubscribe = environment.subscribeContext(schedule);
	return () => {
		stopped = true;
		unsubscribe();
		if (timer !== undefined) environment.clearTimer(timer);
		timer = undefined;
	};
}

function editableElementFocused(): boolean {
	const active = document.activeElement;
	return active instanceof HTMLInputElement
		|| active instanceof HTMLTextAreaElement
		|| active instanceof HTMLSelectElement
		|| (active instanceof HTMLElement && active.isContentEditable);
}

function selectedContextKey(): string {
	const context = appState.selectedContext;
	if (!context) return '';
	return `${context.tool}:${context.record_kind}:${context.record_id}:${context.type_path ?? ''}`;
}

function subscribeToIdleContext(listener: () => void): () => void {
	const disposeRoot = createRoot((dispose) => {
		let initialized = false;
		createEffect(() => {
			void appState.activeRoute;
			void selectedContextKey();
			if (initialized) listener();
			initialized = true;
		});
		return dispose;
	});
	const handleBrowserContext = () => listener();
	document.addEventListener('visibilitychange', handleBrowserContext);
	document.addEventListener('focusin', handleBrowserContext);
	window.addEventListener('parsec-idle-preference-change', handleBrowserContext);
	return () => {
		disposeRoot();
		document.removeEventListener('visibilitychange', handleBrowserContext);
		document.removeEventListener('focusin', handleBrowserContext);
		window.removeEventListener('parsec-idle-preference-change', handleBrowserContext);
	};
}

export function startParsecIdleScheduler(): () => void {
	return createParsecIdleScheduler({
		readPreference: readIdleChatterPreference,
		readSnapshot: () => ({
			route: appState.activeRoute,
			contextKey: selectedContextKey(),
			documentVisible: document.visibilityState === 'visible',
			editableFocused: editableElementFocused(),
			activeRunCount: appState.activeRuns.length,
			hasFeedback: appState.parsecFeedback !== null,
			connectionNeedsAttention: !appState.connected,
		}),
		random: Math.random,
		setTimer: (callback, delayMs) => window.setTimeout(callback, delayMs),
		clearTimer: (handle) => window.clearTimeout(handle),
		report: (event) => { reportParsec(event); },
		subscribeContext: subscribeToIdleContext,
	});
}

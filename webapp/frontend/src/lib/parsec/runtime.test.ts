import { describe, expect, it, vi } from 'vitest';
import { createCompanionRuntime, type CompanionRuntimeEnvironment } from './runtime';
import type { ParsecEvent, ParsecFeedback } from './types';
import { defaultCompanionProfile, loadCompanionProfile, saveCompanionProfile } from './profile';

class MemoryStorage implements Storage {
	private readonly values = new Map<string, string>();
	get length(): number { return this.values.size; }
	clear(): void { this.values.clear(); }
	getItem(key: string): string | null { return this.values.get(key) ?? null; }
	key(index: number): string | null { return [...this.values.keys()][index] ?? null; }
	removeItem(key: string): void { this.values.delete(key); }
	setItem(key: string, value: string): void { this.values.set(key, value); }
}

function environment() {
	let feedbackListener: ((feedback: ParsecFeedback | null, event?: ParsecEvent) => void) | null = null;
	let profileListener: (() => void) | null = null;
	const cleared: number[] = [];
	const timers = new Map<number, () => void>();
	let nextTimer = 1;
	let now = 1_000;
	const tab = {
		start: vi.fn(async () => true),
		tryAcquire: vi.fn(() => true),
		isLeader: vi.fn(() => true),
		heartbeat: vi.fn(() => true),
		release: vi.fn(),
		dispose: vi.fn(),
	};
	const audio = {
		unlock: vi.fn(async () => true),
		play: vi.fn(() => true),
		canPlay: vi.fn(() => true),
		updateSettings: vi.fn(),
		status: vi.fn(() => ({ enabled: true, unlocked: true })),
		stopAll: vi.fn(),
	};
	const storage = new MemoryStorage();
	const env: CompanionRuntimeEnvironment<number> = {
		storage,
		now: () => now,
		random: { next: () => 0 },
		setTimer: (callback) => {
			const id = nextTimer++;
			timers.set(id, callback);
			return id;
		},
		clearTimer: (id) => { cleared.push(id); timers.delete(id); },
		isVisible: () => true,
		isTyping: () => false,
		tab,
		audio,
		subscribeFeedback: (listener) => {
			feedbackListener = listener;
			return () => { feedbackListener = null; };
		},
		subscribeProfile: (listener) => {
			profileListener = listener;
			return () => { profileListener = null; };
		},
	};
	return {
		env,
		storage,
		tab,
		audio,
		timers,
		cleared,
		emit: (feedback: ParsecFeedback | null, event?: ParsecEvent) => feedbackListener?.(feedback, event),
		notifyProfile: () => profileListener?.(),
		setNow: (value: number) => { now = value; },
		tickAt: (value: number) => {
			now = value;
			const [id, callback] = [...timers.entries()][0]!;
			timers.delete(id);
			callback();
		},
	};
}

const errorFeedback: ParsecFeedback = {
	id: 7,
	priority: 100,
	at: 1,
	text: '*growls in frustration.* The fetch failed.',
	kind: 'error',
	animation: 'growl',
	tool: 'lore',
	technicalDetail: 'boom',
	dedupeKey: null,
};

describe('companion browser runtime', () => {
	it('applies pickup, movement, and release in order while audio unlock is pending', async () => {
		const harness = environment();
		let finishUnlock!: (unlocked: boolean) => void;
		harness.audio.unlock.mockImplementation(() => new Promise<boolean>((resolve) => { finishUnlock = resolve; }));
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		try {
			const grabbed = runtime.directIntent({ type: 'grabbed', point: { x: 16, y: 200 } });
			expect(runtime.snapshot().activity).toBe('held');
			const moved = runtime.directIntent({ type: 'held-moved', point: { x: 560, y: 260 }, movementSpeed: 100 });
			expect(runtime.snapshot().location).toEqual({ kind: 'transition', point: { x: 560, y: 260 } });
			const released = runtime.directIntent({ type: 'released', point: { x: 560, y: 260 }, velocity: { x: 0, y: 0 } });
			expect(runtime.snapshot().activity).toBe('landing');
			finishUnlock(true);
			await Promise.all([grabbed, moved, released]);
			expect(runtime.snapshot().location).toEqual({ kind: 'roaming', point: { x: 560, y: 260 } });
		} finally {
			runtime.stop();
		}
	});

	it('keeps accepted interactions usable when profile persistence is unavailable', async () => {
		const harness = environment();
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		const publish = vi.fn();
		harness.env.onState = publish;
		vi.spyOn(harness.storage, 'setItem').mockImplementation(() => { throw new DOMException('Storage full', 'QuotaExceededError'); });
		await expect(runtime.directInteraction('pat')).resolves.toBeUndefined();
		expect(publish).toHaveBeenLastCalledWith(expect.objectContaining({ activity: 'playing', attention: { kind: 'cursor', id: 'pat' } }));
		expect(runtime.profile().familiarity.interactionSignals).toBe(1);
		await expect(runtime.directInteraction('pat')).resolves.toBeUndefined();
		expect(runtime.profile().familiarity.interactionSignals).toBe(2);
		runtime.stop();
	});

	it.each(['current', 'superseded', 'stopped'] as const)('only plays a %s clip cue after delayed audio unlock', async (status) => {
		const harness = environment();
		let finishUnlock!: (unlocked: boolean) => void;
		harness.audio.unlock.mockImplementation(() => new Promise<boolean>((resolve) => { finishUnlock = resolve; }));
		harness.audio.status.mockReturnValue({ enabled: true, unlocked: false });
		harness.env.audioCues = {
			'voice-bark': { id: 'voice-bark', src: '/bark.ogg', channel: 'voice', volume: 0.75, cooldownMs: 2_000 },
		};
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		try {
			const grabbed = runtime.directIntent({ type: 'grabbed', point: { x: 10, y: 20 } });
			[...harness.timers.values()].at(-1)!();
			expect(harness.audio.play).not.toHaveBeenCalled();
			if (status === 'superseded') runtime.dispatch({ type: 'released', point: { x: 10, y: 20 }, velocity: { x: 0, y: 0 } });
			if (status === 'stopped') runtime.stop();
			finishUnlock(true);
			await grabbed;
			expect(harness.audio.play).toHaveBeenCalledTimes(status === 'current' ? 1 : 0);
		} finally {
			runtime.stop();
		}
	});

	it('releases expired feedback without reviving a queued reaction or disturbing held and furniture states', async () => {
		const harness = environment();
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		runtime.dispatch({ type: 'grabbed', point: { x: 10, y: 10 } });
		const held = runtime.snapshot();
		harness.emit(errorFeedback);
		expect(runtime.snapshot().queuedReaction).not.toBeNull();
		harness.emit(null);
		expect(runtime.snapshot()).toMatchObject({ activity: 'held', clip: held.clip, location: held.location, feedbackDuty: 'idle', queuedReaction: null });
		runtime.dispatch({ type: 'released', point: { x: 10, y: 10 }, velocity: { x: 0, y: 0 } });
		expect(runtime.snapshot().clip).toBe('touch-release-drop');
		runtime.dispatch({ type: 'go-to-bed', mode: 'voluntary' });
		const bed = runtime.snapshot();
		harness.emit(null);
		expect(runtime.snapshot()).toMatchObject({ activity: bed.activity, clip: bed.clip, location: bed.location });
		harness.emit(errorFeedback);
		harness.emit(null);
		expect(runtime.snapshot().feedbackDuty).toBe('idle');
		expect(runtime.snapshot().attention.kind).not.toBe('feedback');
		runtime.stop();
	});

	it('keeps an active job blocking autonomy after feedback expires', async () => {
		const harness = environment();
		harness.env.isJobRunning = () => true;
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		harness.emit(errorFeedback);
		harness.emit(null);
		expect(runtime.snapshot().feedbackDuty).toBe('working');
		harness.env.isJobRunning = () => false;
		harness.tickAt(20_000);
		expect(runtime.snapshot().feedbackDuty).toBe('idle');
		runtime.stop();
	});

	it('ignores companion-origin dialogue as application duty and avoids recursive lines', async () => {
		const harness = environment();
		const line = vi.fn();
		harness.env.onLine = line;
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		runtime.dispatch({ type: 'go-to-bed', mode: 'voluntary' });
		const bed = runtime.snapshot();
		harness.emit({ ...errorFeedback, kind: 'info', animation: 'idle' }, { type: 'interaction', phase: 'companion', lineId: 'furniture.bed.voluntary', tool: 'parsec' });
		expect(runtime.snapshot()).toEqual(bed);
		expect(line).toHaveBeenCalledExactlyOnceWith('furniture.bed.voluntary', undefined);
		runtime.stop();
	});

	it('credits accepted pats and brush completion once while preserving the latest profile', async () => {
		const harness = environment();
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		const latest = loadCompanionProfile(harness.storage);
		latest.furnishings.bed.x = 0.8;
		latest.familiarity.interactionSignals = 3;
		saveCompanionProfile(harness.storage, latest);
		await runtime.directInteraction('pat');
		expect(runtime.profile().familiarity.interactionSignals).toBe(4);
		expect(runtime.snapshot().familiarity).toBe(1);
		expect(loadCompanionProfile(harness.storage).furnishings.bed.x).toBe(0.8);
		runtime.dispatch({ type: 'brush-started', point: { x: 0, y: 0 } });
		runtime.dispatch({ type: 'brush-finished', point: { x: 0, y: 0 } });
		runtime.dispatch({ type: 'brush-finished', point: { x: 0, y: 0 } });
		expect(runtime.profile().familiarity.interactionSignals).toBe(5);
		expect(runtime.profile().familiarity.discoveredReactionIds).toContain('brush.contented');
		await runtime.directInteraction('cage');
		await runtime.directInteraction('pat');
		expect(runtime.profile().familiarity.interactionSignals).toBe(5);
		runtime.stop();
		expect(createCompanionRuntime(harness.env).profile().familiarity.interactionSignals).toBe(5);
	});

	it('credits completed toys only once and rejects stale completions of restarted clips', async () => {
		const harness = environment();
		const runtime = createCompanionRuntime(harness.env);
		const point = { x: 0, y: 0 };
		const finish = () => runtime.dispatch({ type: 'clip-finished', clipId: runtime.snapshot().clip, instance: runtime.snapshot().clipInstance });
		runtime.dispatch({ type: 'treat-offered', point });
		finish();
		runtime.dispatch({ type: 'treat-moved', point });
		finish();
		expect(runtime.profile().familiarity.interactionSignals).toBe(0);
		for (const intent of [
			{ type: 'treat-placed', point },
			{ type: 'ball-thrown', point, velocity: point },
			{ type: 'tug-released', point },
		] as const) {
			const before = runtime.profile().familiarity.interactionSignals;
			runtime.dispatch(intent);
			const old = runtime.snapshot();
			runtime.dispatch(intent);
			runtime.dispatch({ type: 'clip-finished', clipId: old.clip, instance: old.clipInstance });
			expect(runtime.profile().familiarity.interactionSignals).toBe(before);
			const current = runtime.snapshot();
			runtime.dispatch({ type: 'clip-finished', clipId: 'unrelated', instance: current.clipInstance });
			finish();
			runtime.dispatch({ type: 'clip-finished', clipId: current.clip, instance: current.clipInstance });
			expect(runtime.profile().familiarity.interactionSignals).toBe(before + 1);
		}
		expect(runtime.profile().familiarity.discoveredReactionIds).toEqual(['ball.proud-return', 'tug.victory-tumble']);
		runtime.stop();
	});

	it('credits an impatient brush session released after its one-shot animation finishes', () => {
		const harness = environment();
		const profile = defaultCompanionProfile();
		profile.settings.personalityTone = 'impish';
		profile.settings.handlingReactions = 'dramatic';
		saveCompanionProfile(harness.storage, profile);
		const runtime = createCompanionRuntime(harness.env);
		const point = { x: 0, y: 0 };
		runtime.dispatch({ type: 'brush-started', point });
		expect(runtime.snapshot().clip).toBe('toy-brush-impatient');
		runtime.dispatch({ type: 'clip-finished', clipId: runtime.snapshot().clip, instance: runtime.snapshot().clipInstance });
		runtime.dispatch({ type: 'brush-finished', point });
		runtime.dispatch({ type: 'brush-finished', point });
		expect(runtime.profile().familiarity.interactionSignals).toBe(1);
		expect(runtime.snapshot().attention).toEqual({ kind: 'none', id: null });
		runtime.stop();
	});

	it('preserves pending excursions and the autonomy deadline on familiarity-only profile changes', async () => {
		const harness = environment();
		const profile = defaultCompanionProfile();
		profile.consent = 'ask-each-time';
		profile.settings.idleChatter = 'frequent';
		saveCompanionProfile(harness.storage, profile);
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		harness.setNow(15_000);
		profile.familiarity.interactionSignals = 4;
		profile.familiarity.band = 1;
		saveCompanionProfile(harness.storage, profile);
		harness.notifyProfile();
		harness.tickAt(16_000);
		expect(runtime.snapshot().pendingExcursion?.behavior).toBe('habitat-sniff');
		profile.familiarity.interactionSignals = 5;
		saveCompanionProfile(harness.storage, profile);
		harness.notifyProfile();
		expect(runtime.snapshot().pendingExcursion?.behavior).toBe('habitat-sniff');
		runtime.stop();
	});

	it('starts family cooldowns only after approval and allows the family again after expiry', async () => {
		const harness = environment();
		const profile = defaultCompanionProfile();
		profile.consent = 'ask-each-time';
		profile.settings.idleChatter = 'frequent';
		saveCompanionProfile(harness.storage, profile);
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		harness.tickAt(16_000);
		expect(runtime.snapshot().pendingExcursion?.behavior).toBe('habitat-sniff');
		runtime.dispatch({ type: 'excursion-response', allow: false });
		harness.tickAt(31_000);
		expect(runtime.snapshot().pendingExcursion?.behavior).toBe('habitat-sniff');
		runtime.dispatch({ type: 'excursion-response', allow: true });
		harness.tickAt(46_000);
		expect(runtime.snapshot().pendingExcursion?.behavior).toBe('edge-roam');
		runtime.dispatch({ type: 'excursion-response', allow: true });
		harness.tickAt(92_000);
		expect(runtime.snapshot().pendingExcursion?.behavior).toBe('perch-watch');
		runtime.stop();
	});

	it('defers a habitat-only setting change until the held actor settles', async () => {
		const harness = environment();
		const profile = defaultCompanionProfile();
		profile.consent = 'allowed';
		saveCompanionProfile(harness.storage, profile);
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		runtime.dispatch({ type: 'grabbed', point: { x: 100, y: 100 } });
		profile.consent = 'habitat-only';
		saveCompanionProfile(harness.storage, profile);
		harness.notifyProfile();
		expect(runtime.snapshot().activity).toBe('held');
		runtime.dispatch({ type: 'released', point: { x: 100, y: 100 }, velocity: { x: 0, y: 0 } });
		runtime.dispatch({ type: 'motion-settled', point: { x: 100, y: 100 } });
		expect(runtime.snapshot().location.kind).toBe('habitat');
		runtime.stop();
	});
	it.each(['consent', 'presence'] as const)('recalls an excursion when habitat-only %s is saved', async (setting) => {
		const harness = environment();
		const profile = defaultCompanionProfile();
		profile.consent = 'allowed';
		saveCompanionProfile(harness.storage, profile);
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		runtime.dispatch({ type: 'autonomous-tick', now: 200_000, behavior: 'edge-roam' });
		expect(runtime.snapshot().location.kind).toBe('perch');
		if (setting === 'consent') profile.consent = 'habitat-only';
		else profile.settings.presence = 'habitat-only';
		saveCompanionProfile(harness.storage, profile);
		harness.notifyProfile();
		expect(runtime.snapshot().location.kind).toBe('habitat');
		runtime.stop();
	});

	it('starts one leader-owned schedule and preserves accepted feedback animation intent', async () => {
		const harness = environment();
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		expect(harness.tab.start).toHaveBeenCalledOnce();
		expect(harness.timers.size).toBe(1);

		harness.emit(errorFeedback);
		expect(runtime.snapshot().feedbackDuty).toBe('error');
		expect(runtime.snapshot().attention).toEqual({ kind: 'feedback', id: '7' });
		expect(runtime.snapshot().clip).toBe('tool-growl');

		harness.emit({ ...errorFeedback, id: 8, kind: 'info', animation: 'search' });
		expect(runtime.snapshot().feedbackDuty).toBe('working');
		expect(runtime.snapshot().clip).toBe('search-sniff');

		harness.emit({ ...errorFeedback, id: 9, kind: 'warning', animation: 'anxious' });
		expect(runtime.snapshot().feedbackDuty).toBe('warning');
		expect(runtime.snapshot().clip).toBe('feedback-warning-alert');
	});

	it('runs the weighted scheduler and dispatches its selected intrusive behavior', async () => {
		const harness = environment();
		const intrusive = defaultCompanionProfile();
		intrusive.consent = 'allowed';
		intrusive.settings.presence = 'intrusive';
		saveCompanionProfile(harness.storage, intrusive);
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		harness.setNow(200_000);
		const ownershipTick = [...harness.timers.values()][0]!;
		ownershipTick();
		expect(runtime.snapshot().clip).toBe('intrusive-cursor-stalk');
	});

	it('unlocks audio on direct interaction and disposes every owned adapter', async () => {
		const harness = environment();
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		await runtime.directInteraction('pat');
		expect(harness.audio.unlock).toHaveBeenCalledOnce();
		runtime.stop();
		expect(harness.timers.size).toBe(0);
		expect(new Set(harness.cleared).size).toBe(harness.cleared.length);
		expect(harness.audio.stopAll).toHaveBeenCalledOnce();
		expect(harness.tab.dispose).toHaveBeenCalledOnce();
	});

	it('plays authored clip cues at their frame-relative delay after audio unlock', async () => {
		const harness = environment();
		harness.env.audioCues = {
			'voice-bark': { id: 'voice-bark', src: '/bark.ogg', channel: 'voice', volume: 0.75, cooldownMs: 2_000 },
		};
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		await runtime.directInteraction('pat');
		harness.emit({ ...errorFeedback, id: 10, kind: 'success', animation: 'happy' });
		expect(harness.audio.play).not.toHaveBeenCalled();
		const cueTimer = [...harness.timers.values()].at(-1)!;
		cueTimer();
		expect(harness.audio.play).toHaveBeenCalledWith(
			harness.env.audioCues['voice-bark'],
			expect.objectContaining({ visible: true, leader: true }),
		);
	});

	it('maps Bed and Cage primary actions to furniture state, with Cage becoming explicit release', async () => {
		const harness = environment();
		const runtime = createCompanionRuntime(harness.env);
		const observed: string[] = [];
		const unsubscribe = runtime.subscribeState((state) => observed.push(state.location.kind));
		await runtime.start();
		await runtime.directInteraction('bed');
		expect(runtime.snapshot().location).toEqual({ kind: 'bed', mode: 'voluntary' });
		await runtime.directInteraction('cage');
		expect(runtime.snapshot().location).toEqual({ kind: 'cage', closed: true });
		await runtime.directInteraction('cage');
		expect(runtime.snapshot().location).toEqual({ kind: 'habitat' });
		expect(observed).toContain('bed');
		expect(observed).toContain('cage');
		unsubscribe();
	});

	it('routes the six play controls through typed interaction intents', async () => {
		const harness = environment();
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		await runtime.directInteraction('ball');
		expect(runtime.snapshot().attention).toEqual({ kind: 'toy', id: 'ball' });
		await runtime.directInteraction('brush');
		expect(runtime.snapshot().attention).toEqual({ kind: 'cursor', id: 'brush' });
		await runtime.directInteraction('whistle');
		expect(runtime.snapshot().location).toEqual({ kind: 'habitat' });
	});

	it('applies unified profile changes without restarting the runtime', async () => {
		const harness = environment();
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		const next = defaultCompanionProfile();
		next.settings.presence = 'intrusive';
		next.settings.audio.master = 0.8;
		saveCompanionProfile(harness.storage, next);
		harness.notifyProfile();
		expect(runtime.snapshot().settings.presence).toBe('intrusive');
		expect(harness.audio.updateSettings).toHaveBeenLastCalledWith(next.settings.audio);
	});

	it('is idempotent across repeated starts and stops', async () => {
		const harness = environment();
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		await runtime.start();
		expect(harness.tab.start).toHaveBeenCalledOnce();
		runtime.stop();
		runtime.stop();
		expect(harness.tab.dispose).toHaveBeenCalledOnce();
	});

	it('stops legacy idle chatter immediately when tab ownership is lost', async () => {
		const harness = environment();
		const stopIdle = vi.fn();
		harness.env.startIdleChatter = vi.fn(() => stopIdle);
		const runtime = createCompanionRuntime(harness.env);
		await runtime.start();
		expect(harness.env.startIdleChatter).toHaveBeenCalledOnce();
		harness.tab.heartbeat.mockReturnValue(false);
		harness.tab.tryAcquire.mockReturnValue(false);
		const ownershipTick = [...harness.timers.values()][0]!;
		ownershipTick();
		expect(stopIdle).toHaveBeenCalledOnce();
		runtime.stop();
	});
});

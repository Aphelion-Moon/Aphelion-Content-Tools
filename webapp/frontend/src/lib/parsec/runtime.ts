import { isJobRunning, setParsecState } from '~/store/appStore';
import { coreFallbackManifest } from '~/assets/parsec/manifest.v1';
import { startParsecIdleScheduler } from './idle';
import { audioCuesFromManifest, createCompanionAudioBus, createHowlerPlayer, type CompanionAudioBus, type CompanionAudioCue } from './audio';
import { initialCompanionState, reduceCompanion } from './companionReducer';
import { chooseBehavior, cooldownForBehavior, familiarityAfterInteraction, nextBehaviorDelay, type FamiliarityInteraction, type RandomSource, type SchedulerContext } from './companionScheduler';
import type { AutonomousBehavior } from './companionTypes';
import type { CompanionEffect, CompanionIntent, CompanionState, ReviewedCompanionLineId } from './companionTypes';
import { COMPANION_PROFILE_KEY, loadCompanionProfile, saveCompanionProfile, type CompanionProfileV1 } from './profile';
import { createTabCoordinator, type CompanionTabCoordinator, type TabCoordinatorEnvironment } from './tabCoordinator';
import { reportCompanionLine, subscribeParsecFeedback, type ParsecFeedbackListener } from './coordinator';
import type { ParsecFeedback } from './types';
import { resolveState } from '../parsecEngine';
import { beginToolInteraction, type InteractiveToolId } from './interactions';

const OWNERSHIP_POLL_MS = 3_000;

export interface CompanionRuntimeEnvironment<TimerHandle = ReturnType<typeof setTimeout>> {
	storage: Storage;
	now: () => number;
	random: RandomSource;
	setTimer: (callback: () => void, delayMs: number) => TimerHandle;
	clearTimer: (handle: TimerHandle) => void;
	isVisible: () => boolean;
	isTyping: () => boolean;
	isJobRunning?: () => boolean;
	tab: CompanionTabCoordinator;
	audio: CompanionAudioBus;
	subscribeFeedback: (listener: ParsecFeedbackListener) => () => void;
	subscribeProfile?: (listener: () => void) => () => void;
	audioCues?: Readonly<Record<string, CompanionAudioCue>>;
	onState?: (state: CompanionState) => void;
	onLine?: (lineId: ReviewedCompanionLineId, eventId?: string) => void;
	onInvitation?: () => void;
	startIdleChatter?: () => () => void;
}

export interface CompanionRuntime {
	start(): Promise<void>;
	stop(): void;
	snapshot(): CompanionState;
	dispatch(intent: CompanionIntent): void;
	directInteraction(action: Extract<CompanionIntent, { type: 'direct-interaction' }>['action']): Promise<void>;
	directIntent(intent: CompanionIntent): Promise<void>;
	profile(): CompanionProfileV1;
	subscribeState(listener: (state: CompanionState) => void): () => void;
}

function dutyForFeedback(feedback: ParsecFeedback): Extract<CompanionIntent, { type: 'feedback' }>['duty'] {
	if (feedback.kind === 'error') return 'error';
	if (feedback.kind === 'warning') return 'warning';
	if (feedback.kind === 'success') return 'success';
	return ['working', 'search', 'fetch', 'pant'].includes(feedback.animation) ? 'working' : 'idle';
}

export function createCompanionRuntime<TimerHandle>(
	environment: CompanionRuntimeEnvironment<TimerHandle>,
): CompanionRuntime {
	let profile = loadCompanionProfile(environment.storage);
	let state = initialCompanionState({
		consent: profile.consent,
		familiarity: profile.familiarity.band,
		settings: profile.settings,
	});
	let started = false;
	let stopped = false;
	let timer: TimerHandle | null = null;
	let nextAutonomousAt = Number.POSITIVE_INFINITY;
	let recentBehaviors: AutonomousBehavior[] = [];
	const cooldowns: SchedulerContext['cooldowns'] = {};
	let pendingFamiliarity: { instance: number; kind: FamiliarityInteraction['kind'] } | null = null;
	let recallWhenSettled = false;
	let workingAfterFeedback = false;
	let unsubscribeFeedback: (() => void) | null = null;
	let unsubscribeProfile: (() => void) | null = null;
	let stopIdleChatter: (() => void) | null = null;
	let pendingAudioUnlock: Promise<boolean> | null = null;
	const cueTimers = new Set<TimerHandle>();
	const stateListeners = new Set<(state: CompanionState) => void>();

	function publishState(): void {
		environment.onState?.(state);
		for (const listener of stateListeners) listener(state);
	}

	function audioContext() {
		return {
			visible: environment.isVisible(),
			typing: environment.isTyping(),
			leader: environment.tab.isLeader(),
		};
	}

	function updateProfile(patch: Partial<Pick<CompanionProfileV1, 'consent' | 'settings'>>): void {
		const latest = loadCompanionProfile(environment.storage);
		profile = {
			...latest,
			...patch,
			settings: patch.settings ?? latest.settings,
		};
		saveCompanionProfile(environment.storage, profile);
	}

	function unlockAudio(): Promise<boolean> {
		if (pendingAudioUnlock) return pendingAudioUnlock;
		const pending = environment.audio.unlock().catch(() => false);
		pendingAudioUnlock = pending;
		void pending.then(() => { if (pendingAudioUnlock === pending) pendingAudioUnlock = null; });
		return pending;
	}

	function playSound(soundId: string): void {
		const cue = environment.audioCues?.[soundId];
		if (!cue) return;
		if (pendingAudioUnlock && !environment.audio.status().unlocked) {
			const instance = state.clipInstance;
			void pendingAudioUnlock.then((unlocked) => {
				if (unlocked && !stopped && state.clipInstance === instance) environment.audio.play(cue, audioContext());
			});
		} else environment.audio.play(cue, audioContext());
	}

	function clearCueTimers(): void {
		for (const cueTimer of cueTimers) environment.clearTimer(cueTimer);
		cueTimers.clear();
	}

	function executeEffect(effect: CompanionEffect): void {
		switch (effect.type) {
			case 'play-sound': {
				playSound(effect.soundId);
				break;
			}
			case 'play-clip': {
				clearCueTimers();
				const clip = coreFallbackManifest.clips[effect.clipId];
				if (!clip) break;
				for (const cue of clip.soundCues) {
					const delayMs = clip.durationsMs.slice(0, cue.frame).reduce((total, duration) => total + duration, 0);
					if (delayMs === 0) {
						playSound(cue.soundId);
						continue;
					}
					let cueTimer: TimerHandle;
					cueTimer = environment.setTimer(() => {
						cueTimers.delete(cueTimer);
						if (state.clip === effect.clipId) playSound(cue.soundId);
					}, delayMs);
					cueTimers.add(cueTimer);
				}
				break;
			}
			case 'append-companion-line':
				environment.onLine?.(effect.lineId, effect.eventId);
				break;
			case 'update-profile':
				updateProfile(effect.patch);
				break;
			case 'request-invitation':
				environment.onInvitation?.();
				break;
			case 'schedule-intent':
			case 'cancel-schedule':
			case 'move-to':
				break;
		}
	}

	function dispatch(intent: CompanionIntent): void {
		if (stopped || (intent.type === 'clip-finished' && intent.instance !== state.clipInstance)) return;
		const previous = state;
		const transition = reduceCompanion(previous, intent);
		state = transition.state;
		const playsClip = transition.effects.some((effect) => effect.type === 'play-clip');
		const completedInteraction = intent.type === 'clip-finished' && intent.clipId === previous.clip
			&& state !== previous && pendingFamiliarity?.instance === previous.clipInstance ? pendingFamiliarity.kind : null;
		if (playsClip || state.clip !== previous.clip) {
			state = { ...state, clipInstance: previous.clipInstance + 1 };
			pendingFamiliarity = null;
		}
		if (playsClip) {
			const kind = intent.type === 'ball-thrown' ? 'ball-returned'
				: intent.type === 'tug-released' ? 'tug-finished'
					: intent.type === 'treat-placed' ? 'treat' : null;
			if (kind) pendingFamiliarity = { kind, instance: state.clipInstance };
		}
		const interaction = completedInteraction ?? (playsClip && intent.type === 'pat-started' ? 'pat'
			: playsClip && intent.type === 'brush-finished' ? 'brush' : null);
		if (interaction) {
			const latest = loadCompanionProfile(environment.storage);
			const familiarity = latest.familiarity.interactionSignals >= profile.familiarity.interactionSignals ? latest.familiarity : profile.familiarity;
			profile = { ...latest, familiarity: familiarityAfterInteraction(familiarity, { kind: interaction, at: environment.now() }) };
			state = { ...state, familiarity: profile.familiarity.band };
			try { saveCompanionProfile(environment.storage, profile); } catch {
				// Optional familiarity remains in memory; storage failure must not interrupt a gesture.
			}
		}
		const autonomous = intent.type === 'autonomous-tick' ? intent
			: intent.type === 'excursion-response' && intent.allow ? previous.pendingExcursion : null;
		if (autonomous && transition.effects.some((effect) => effect.type === 'move-to')) {
			const behavior = autonomous.behavior ?? 'edge-roam';
			const cooldown = cooldownForBehavior(behavior);
			cooldowns[cooldown.family] = environment.now() + cooldown.cooldownMs;
			recentBehaviors = [...recentBehaviors, behavior].slice(-2);
		}
		for (const effect of transition.effects) executeEffect(effect);
		if (recallWhenSettled && intent.type === 'motion-settled') {
			recallWhenSettled = false;
			const recall = reduceCompanion(state, { type: 'recall-requested' });
			state = recall.state;
			for (const effect of recall.effects) executeEffect(effect);
		}
		if (!['transition', 'roaming'].includes(state.location.kind)) recallWhenSettled = false;
		publishState();
	}

	function setNextAutonomousTime(): void {
		nextAutonomousAt = environment.now() + nextBehaviorDelay(state.settings, environment.random);
	}

	function syncIdleChatterOwnership(leader: boolean): void {
		if (leader && stopIdleChatter === null) {
			stopIdleChatter = environment.startIdleChatter?.() ?? null;
			return;
		}
		if (!leader && stopIdleChatter !== null) {
			stopIdleChatter();
			stopIdleChatter = null;
		}
	}

	function armOwnershipTimer(): void {
		if (stopped || timer !== null) return;
		timer = environment.setTimer(() => {
			timer = null;
			let leader = environment.tab.heartbeat();
			if (!leader && environment.isVisible()) leader = environment.tab.tryAcquire();
			syncIdleChatterOwnership(leader);
			if (workingAfterFeedback && !environment.isJobRunning?.()) {
				workingAfterFeedback = false;
				dispatch({ type: 'feedback-cleared', working: false });
			}
			if (leader && environment.now() >= nextAutonomousAt && !environment.isJobRunning?.()) {
				const now = environment.now();
				const behavior = chooseBehavior({
					state,
					visible: environment.isVisible(),
					typing: environment.isTyping(),
					playInitiated: profile.familiarity.interactionSignals > 0,
					now,
					cooldowns,
					recentBehaviors,
				}, environment.random);
				if (behavior) {
					dispatch({ type: 'autonomous-tick', now, behavior });
				}
				setNextAutonomousTime();
			}
			armOwnershipTimer();
		}, OWNERSHIP_POLL_MS);
	}

	return {
		async start(): Promise<void> {
			if (started || stopped) return;
			started = true;
			const leader = await environment.tab.start();
			setNextAutonomousTime();
			unsubscribeFeedback = environment.subscribeFeedback((feedback, event) => {
				if (event?.type === 'interaction' && event.phase === 'companion') return;
				if (!feedback) {
					workingAfterFeedback = environment.isJobRunning?.() ?? false;
					dispatch({ type: 'feedback-cleared', working: workingAfterFeedback });
					return;
				}
				workingAfterFeedback = false;
				dispatch({
					type: 'feedback',
					duty: dutyForFeedback(feedback),
					eventId: String(feedback.id),
					animation: feedback.animation,
				});
			});
			unsubscribeProfile = environment.subscribeProfile?.(() => {
				profile = loadCompanionProfile(environment.storage);
				const settingsChanged = state.consent !== profile.consent || JSON.stringify(state.settings) !== JSON.stringify(profile.settings);
				state = {
					...state,
					consent: profile.consent,
					pendingExcursion: settingsChanged ? null : state.pendingExcursion,
					familiarity: profile.familiarity.band,
					settings: profile.settings,
				};
				environment.audio.updateSettings(profile.settings.audio);
				recallWhenSettled = (state.consent === 'habitat-only' || state.settings.presence === 'habitat-only')
					&& state.location.kind === 'transition';
				if (settingsChanged) setNextAutonomousTime();
				if ((state.consent === 'habitat-only' || state.settings.presence === 'habitat-only')
					&& (state.location.kind === 'perch' || state.location.kind === 'roaming')) {
					dispatch({ type: 'recall-requested' });
					return;
				}
				publishState();
			}) ?? null;
			syncIdleChatterOwnership(leader);
			armOwnershipTimer();
		},
		stop(): void {
			if (stopped) return;
			stopped = true;
			if (timer !== null) environment.clearTimer(timer);
			timer = null;
			clearCueTimers();
			unsubscribeFeedback?.();
			unsubscribeFeedback = null;
			unsubscribeProfile?.();
			unsubscribeProfile = null;
			stopIdleChatter?.();
			stopIdleChatter = null;
			environment.audio.stopAll();
			environment.tab.dispose();
		},
		snapshot: () => state,
		dispatch,
		async directInteraction(action): Promise<void> {
			environment.tab.tryAcquire();
			await environment.audio.unlock();
			dispatch({ type: 'direct-interaction', action });
			if ((['pat', 'ball', 'tug', 'brush', 'treat', 'whistle'] as const).includes(action as InteractiveToolId)) {
				const interaction = beginToolInteraction(
					action as InteractiveToolId,
					state,
					{ point: { x: 0, y: 0 }, at: environment.now() },
				);
				for (const intent of interaction.intents) dispatch(intent);
			}
			if (action === 'bed') {
				dispatch({ type: 'go-to-bed', mode: 'voluntary' });
			} else if (action === 'cage') {
				if (state.location.kind === 'cage' && state.location.closed) {
					dispatch({ type: 'release-cage' });
				} else {
					dispatch({ type: 'go-to-cage' });
					dispatch({ type: 'set-cage-latch', closed: true });
				}
			}
		},
		async directIntent(intent): Promise<void> {
			environment.tab.tryAcquire();
			const unlocked = unlockAudio();
			// Pointer and animation state must advance in event order, even if audio is still suspended.
			dispatch(intent);
			await unlocked;
		},
		profile: () => profile,
		subscribeState(listener): () => void {
			stateListeners.add(listener);
			return () => stateListeners.delete(listener);
		},
	};
}

function browserTabEnvironment(): TabCoordinatorEnvironment {
	const channel = typeof BroadcastChannel === 'function' ? new BroadcastChannel('aphelion-parsec-tabs') : undefined;
	const locks = navigator.locks ? {
		request: async (
			name: string,
			options: { ifAvailable: true; mode: 'exclusive' },
			callback: (lock: { name: string } | null) => Promise<void>,
		) => navigator.locks.request(name, options, (lock) => callback(lock ? { name: lock.name } : null)),
	} : undefined;
	return {
		tabId: crypto.randomUUID(),
		storage: window.localStorage,
		now: Date.now,
		isVisible: () => document.visibilityState === 'visible',
		...(channel ? { channel } : {}),
		...(locks ? { locks } : {}),
	};
}

function browserIsTyping(): boolean {
	const active = document.activeElement;
	return active instanceof HTMLInputElement
		|| active instanceof HTMLTextAreaElement
		|| (active instanceof HTMLElement && active.isContentEditable);
}

let browserRuntime: CompanionRuntime | null = null;

export function startBrowserCompanionRuntime(): () => void {
	if (browserRuntime) return () => undefined;
	const tab = createTabCoordinator(browserTabEnvironment());
	const profile = loadCompanionProfile();
	const audio = createCompanionAudioBus(createHowlerPlayer(), profile.settings.audio);
	const audioCues = audioCuesFromManifest(coreFallbackManifest);
	browserRuntime = createCompanionRuntime({
		storage: window.localStorage,
		now: Date.now,
		random: { next: Math.random },
		setTimer: (callback, delayMs) => setTimeout(callback, delayMs),
		clearTimer: (handle) => clearTimeout(handle),
		isVisible: () => document.visibilityState === 'visible',
		isTyping: browserIsTyping,
		isJobRunning,
		tab,
		audio,
		audioCues,
		subscribeFeedback: subscribeParsecFeedback,
		onLine: reportCompanionLine,
		subscribeProfile: (listener) => {
			const onStorage = (event: StorageEvent) => {
				if (event.storageArea === window.localStorage && (event.key === COMPANION_PROFILE_KEY || event.key === null)) listener();
			};
			window.addEventListener('parsec-profile-change', listener);
			window.addEventListener('storage', onStorage);
			return () => {
				window.removeEventListener('parsec-profile-change', listener);
				window.removeEventListener('storage', onStorage);
			};
		},
		onInvitation: () => window.dispatchEvent(new Event('parsec-invitation-request')),
		onState: (nextState) => setParsecState(resolveState(nextState.clip)),
		startIdleChatter: startParsecIdleScheduler,
	});
	void browserRuntime.start();
	return () => {
		browserRuntime?.stop();
		browserRuntime = null;
	};
}

export async function interactWithBrowserCompanion(
	action: Extract<CompanionIntent, { type: 'direct-interaction' }>['action'],
): Promise<void> {
	await browserRuntime?.directInteraction(action);
}

export async function dispatchBrowserCompanionIntent(intent: CompanionIntent): Promise<void> {
	await browserRuntime?.directIntent(intent);
}

export function browserCompanionSnapshot(): CompanionState | null {
	return browserRuntime?.snapshot() ?? null;
}

export function subscribeBrowserCompanionState(listener: (state: CompanionState) => void): () => void {
	return browserRuntime?.subscribeState(listener) ?? (() => undefined);
}

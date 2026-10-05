import { Howl, Howler } from 'howler';
import type { ParsecAssetManifest } from './assets';
import type { CompanionAudioSettings } from './companionTypes';

export type CompanionAudioChannel = 'voice' | 'effect' | 'alert' | 'rare-idle';

export interface CompanionAudioCue {
	id: string;
	src: string;
	channel: CompanionAudioChannel;
	volume: number;
	cooldownMs: number;
}

export interface AudioPlaybackHandle {
	stop(): void;
	onEnd?(callback: () => void): void;
}

export interface AudioPlayerPort {
	unlock(): Promise<boolean>;
	play(cue: CompanionAudioCue, volume: number): AudioPlaybackHandle;
	stopAll(): void;
}

export interface CompanionAudioContext {
	visible: boolean;
	typing: boolean;
	leader: boolean;
}

export interface CompanionAudioBus {
	unlock(): Promise<boolean>;
	canPlay(cue: CompanionAudioCue, context: CompanionAudioContext): boolean;
	play(cue: CompanionAudioCue, context: CompanionAudioContext): boolean;
	updateSettings(settings: CompanionAudioSettings): void;
	status(): { enabled: boolean; unlocked: boolean };
	stopAll(): void;
}

export function audioCuesFromManifest(manifest: ParsecAssetManifest): Record<string, CompanionAudioCue> {
	return Object.fromEntries(Object.values(manifest.sounds).flatMap((sound) => {
		if (!sound.src) return [];
		const channel: CompanionAudioChannel = sound.channel === 'toys'
			? 'effect'
			: sound.channel === 'radio' ? 'alert' : sound.channel;
		return [[sound.id, {
			id: sound.id,
			src: sound.src,
			channel,
			volume: sound.authoredVolume,
			cooldownMs: sound.cooldownMs,
		} satisfies CompanionAudioCue]];
	}));
}

function channelVolume(channel: CompanionAudioChannel, settings: CompanionAudioSettings): number {
	if (channel === 'voice') return settings.voice;
	if (channel === 'effect') return settings.effects;
	if (channel === 'alert') return settings.alerts;
	return settings.rareIdle;
}

export function createCompanionAudioBus(
	player: AudioPlayerPort,
	initialSettings: CompanionAudioSettings,
	now: () => number = Date.now,
): CompanionAudioBus {
	let settings = { ...initialSettings };
	let unlocked = false;
	const lastPlayedAt = new Map<string, number>();
	const ordinaryHandles = new Set<AudioPlaybackHandle>();
	const alertHandles = new Set<AudioPlaybackHandle>();

	function removeHandle(handle: AudioPlaybackHandle, collection: Set<AudioPlaybackHandle>): void {
		collection.delete(handle);
	}

	function canPlay(cue: CompanionAudioCue, context: CompanionAudioContext): boolean {
		if (!settings.enabled || !unlocked || !context.visible || !context.leader) return false;
		if (cue.channel === 'rare-idle' && context.typing) return false;
		const previous = lastPlayedAt.get(cue.id);
		if (previous !== undefined && now() - previous < cue.cooldownMs) return false;
		if (cue.channel === 'alert') return alertHandles.size < 1;
		return ordinaryHandles.size < 2;
	}

	return {
		async unlock(): Promise<boolean> {
			if (unlocked) return true;
			try {
				unlocked = await player.unlock();
			} catch {
				unlocked = false;
			}
			return unlocked;
		},
		canPlay,
		play(cue, context): boolean {
			if (!canPlay(cue, context)) return false;
			const volume = Math.min(1, Math.max(0, settings.master * channelVolume(cue.channel, settings) * cue.volume));
			const handle = player.play(cue, volume);
			const collection = cue.channel === 'alert' ? alertHandles : ordinaryHandles;
			collection.add(handle);
			handle.onEnd?.(() => removeHandle(handle, collection));
			lastPlayedAt.set(cue.id, now());
			return true;
		},
		updateSettings(nextSettings): void {
			settings = { ...nextSettings };
			if (!settings.enabled) player.stopAll();
		},
		status: () => ({ enabled: settings.enabled, unlocked }),
		stopAll(): void {
			player.stopAll();
			ordinaryHandles.clear();
			alertHandles.clear();
		},
	};
}

/** Howler-backed lazy player. Audio files are instantiated only when their cue is first used. */
export function createHowlerPlayer(): AudioPlayerPort {
	const sounds = new Map<string, Howl>();
	return {
		async unlock(): Promise<boolean> {
			try {
				if (Howler.ctx?.state === 'suspended') await Howler.ctx.resume();
				return Howler.ctx?.state !== 'suspended';
			} catch {
				return false;
			}
		},
		play(cue, volume): AudioPlaybackHandle {
			let sound = sounds.get(cue.id);
			if (!sound) {
				sound = new Howl({ src: [cue.src], preload: false });
				sounds.set(cue.id, sound);
			}
			sound.volume(volume);
			const playbackId = sound.play();
			return {
				stop: () => sound?.stop(playbackId),
				onEnd: (callback) => { sound?.once('end', callback, playbackId); },
			};
		},
		stopAll(): void {
			for (const sound of sounds.values()) sound.stop();
		},
	};
}

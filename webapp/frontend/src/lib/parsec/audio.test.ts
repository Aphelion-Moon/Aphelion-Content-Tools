import { describe, expect, it } from 'vitest';
import { coreFallbackManifest } from '~/assets/parsec/manifest.v1';
import { audioCuesFromManifest, createCompanionAudioBus, type AudioPlayerPort, type CompanionAudioCue } from './audio';
import { DEFAULT_COMPANION_SETTINGS } from './companionTypes';

function cue(overrides: Partial<CompanionAudioCue> = {}): CompanionAudioCue {
	return {
		id: 'bark',
		src: '/bark.ogg',
		channel: 'voice',
		volume: 0.5,
		cooldownMs: 0,
		...overrides,
	};
}

function player() {
	const plays: Array<{ id: string; volume: number }> = [];
	const port: AudioPlayerPort = {
		unlock: async () => true,
		play: (audioCue, volume) => {
			plays.push({ id: audioCue.id, volume });
			return { stop: () => undefined };
		},
		stopAll: () => undefined,
	};
	return { port, plays };
}

const allowed = { visible: true, typing: false, leader: true };

describe('companion audio policy', () => {
	it('builds every prepared manifest sound into the runtime channel contract', () => {
		const cues = audioCuesFromManifest(coreFallbackManifest);
		expect(Object.keys(cues)).toHaveLength(8);
		expect(cues['voice-bark']).toMatchObject({ channel: 'voice', volume: 0.75, cooldownMs: 2_000 });
		expect(cues['toy-squeak']?.channel).toBe('effect');
		expect(cues['radio-alert']?.channel).toBe('alert');
		expect(cues['rare-idle']?.channel).toBe('rare-idle');
	});
	it('unlocks after direct interaction and applies master, channel, and cue volume', async () => {
		const fake = player();
		const bus = createCompanionAudioBus(fake.port, DEFAULT_COMPANION_SETTINGS.audio, () => 100);
		expect(bus.play(cue(), allowed)).toBe(false);
		expect(await bus.unlock()).toBe(true);
		expect(bus.play(cue(), allowed)).toBe(true);
		expect(fake.plays.at(-1)?.volume).toBeCloseTo(0.15);
	});

	it('suppresses rare idle audio while hidden, typing, muted, or not tab leader', async () => {
		const fake = player();
		const bus = createCompanionAudioBus(fake.port, DEFAULT_COMPANION_SETTINGS.audio, () => 100);
		await bus.unlock();
		const idleCue = cue({ id: 'idle-snuffle', channel: 'rare-idle' });
		for (const context of [
			{ ...allowed, visible: false },
			{ ...allowed, typing: true },
			{ ...allowed, leader: false },
		]) expect(bus.canPlay(idleCue, context)).toBe(false);

		bus.updateSettings({ ...DEFAULT_COMPANION_SETTINGS.audio, enabled: false });
		expect(bus.canPlay(idleCue, allowed)).toBe(false);
	});

	it('enforces per-cue cooldowns and keeps alert playback available while typing', async () => {
		let now = 100;
		const fake = player();
		const bus = createCompanionAudioBus(fake.port, DEFAULT_COMPANION_SETTINGS.audio, () => now);
		await bus.unlock();
		const bark = cue({ cooldownMs: 500 });
		expect(bus.play(bark, allowed)).toBe(true);
		expect(bus.play(bark, allowed)).toBe(false);
		now += 501;
		expect(bus.play(bark, allowed)).toBe(true);
		expect(bus.canPlay(cue({ id: 'alert', channel: 'alert' }), { ...allowed, typing: true })).toBe(true);
	});

	it('stays enabled but locked when browser audio unlock is rejected', async () => {
		const fake = player();
		fake.port.unlock = async () => false;
		const bus = createCompanionAudioBus(fake.port, DEFAULT_COMPANION_SETTINGS.audio, () => 0);
		expect(await bus.unlock()).toBe(false);
		expect(bus.status()).toEqual({ enabled: true, unlocked: false });
	});
});

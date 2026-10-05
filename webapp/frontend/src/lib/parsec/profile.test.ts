import { describe, expect, it } from 'vitest';
import {
	COMPANION_PROFILE_KEY,
	defaultCompanionProfile,
	exportCompanionProfile,
	importCompanionProfile,
	loadCompanionProfile,
	saveCompanionProfile,
} from './profile';

class MemoryStorage implements Storage {
	private readonly values = new Map<string, string>();

	get length(): number { return this.values.size; }
	clear(): void { this.values.clear(); }
	getItem(key: string): string | null { return this.values.get(key) ?? null; }
	key(index: number): string | null { return [...this.values.keys()][index] ?? null; }
	removeItem(key: string): void { this.values.delete(key); }
	setItem(key: string, value: string): void { this.values.set(key, value); }
}

describe('companion profile persistence', () => {
	it('does not restart idle chatter when only familiarity is saved', () => {
		window.localStorage.clear();
		const profile = defaultCompanionProfile();
		saveCompanionProfile(window.localStorage, profile);
		let idleChanges = 0;
		const listener = () => { idleChanges += 1; };
		window.addEventListener('parsec-idle-preference-change', listener);
		try {
			profile.familiarity.interactionSignals = 1;
			saveCompanionProfile(window.localStorage, profile);
			expect(idleChanges).toBe(0);
			profile.settings.idleChatter = 'off';
			saveCompanionProfile(window.localStorage, profile);
			expect(idleChanges).toBe(1);
		} finally {
			window.removeEventListener('parsec-idle-preference-change', listener);
			window.localStorage.clear();
		}
	});

	it('defaults to uninvited, rare chatter, edge-biased presence, and approved audio levels', () => {
		const profile = loadCompanionProfile(new MemoryStorage());
		expect(profile.consent).toBe('unconfigured');
		expect(profile.settings.idleChatter).toBe('rare');
		expect(profile.settings.presence).toBe('edge-biased');
		expect(profile.settings.audio.enabled).toBe(true);
		expect(profile.settings.audio.master).toBe(0.3);
		expect(profile.settings.audio.rareIdle).toBe(0.2);
	});

	it('migrates legacy idle and motion settings once into the unified profile', () => {
		const storage = new MemoryStorage();
		storage.setItem('aphelion-parsec-idle-chatter', 'frequent');
		storage.setItem('aphelion-parsec-reduced-motion-override', 'reduce');
		const migrated = loadCompanionProfile(storage);
		expect(migrated.settings.idleChatter).toBe('frequent');
		expect(migrated.settings.motion).toBe('reduce');
		expect(storage.getItem('aphelion-parsec-idle-chatter')).toBeNull();
		expect(storage.getItem('aphelion-parsec-reduced-motion-override')).toBeNull();

		storage.setItem('aphelion-parsec-idle-chatter', 'off');
		expect(loadCompanionProfile(storage).settings.idleChatter).toBe('frequent');
	});

	it('quarantines corrupt source text before restoring defaults', () => {
		const storage = new MemoryStorage();
		storage.setItem(COMPANION_PROFILE_KEY, '{broken');
		const restored = loadCompanionProfile(storage, () => 1234);
		expect(restored).toEqual(defaultCompanionProfile());
		expect(storage.getItem('aphelion-parsec-profile-corrupt-1234')).toBe('{broken');
		expect(storage.getItem(COMPANION_PROFILE_KEY)).toContain('"schemaVersion":1');
	});

	it('migrates stored, imported, and legacy follow-system motion to animate', () => {
		const storage = new MemoryStorage();
		const profile = defaultCompanionProfile();
		const source = JSON.stringify({ ...profile, settings: { ...profile.settings, motion: 'follow-system' } });
		storage.setItem(COMPANION_PROFILE_KEY, source);
		expect(loadCompanionProfile(storage).settings.motion).toBe('animate');
		const imported = importCompanionProfile(source);
		expect(imported.ok && imported.profile.settings.motion).toBe('animate');
		storage.clear();
		storage.setItem('aphelion-parsec-reduced-motion-override', 'follow-system');
		expect(loadCompanionProfile(storage).settings.motion).toBe('animate');
	});

	it('round-trips profile export separately from activity history and clamps imported positions and volumes', () => {
		const source = defaultCompanionProfile();
		const exported = exportCompanionProfile(source);
		const document = JSON.parse(exported) as Record<string, unknown>;
		expect(document).not.toHaveProperty('activityHistory');
		expect(document).not.toHaveProperty('journal');
		const settings = document.settings as Record<string, unknown>;
		settings.audio = { ...(settings.audio as object), master: 4, rareIdle: -1 };
		document.furnishings = {
			bed: { x: -5, y: 3, anchor: 'app-edge' },
			cage: { x: 2, y: -2, anchor: 'habitat' },
		};

		const imported = importCompanionProfile(JSON.stringify(document));
		expect(imported.ok).toBe(true);
		if (!imported.ok) return;
		expect(imported.profile.settings.audio.master).toBe(1);
		expect(imported.profile.settings.audio.rareIdle).toBe(0);
		expect(imported.profile.furnishings.bed).toEqual({ x: 0, y: 1, anchor: 'app-edge' });
		expect(imported.profile.furnishings.cage).toEqual({ x: 1, y: 0, anchor: 'habitat' });
	});

	it('saves a valid profile document under one stable key', () => {
		const storage = new MemoryStorage();
		const profile = defaultCompanionProfile();
		saveCompanionProfile(storage, profile);
		expect(JSON.parse(storage.getItem(COMPANION_PROFILE_KEY)!)).toEqual(profile);
	});
});

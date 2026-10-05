import {
	DEFAULT_COMPANION_SETTINGS,
	type CompanionSettings,
	type ExcursionConsent,
	type FamiliarityBand,
} from './companionTypes';
import type { FamiliarityProfile } from './companionScheduler';

export const COMPANION_PROFILE_KEY = 'aphelion-parsec-profile';

const LEGACY_KEYS = {
	idleChatter: 'aphelion-parsec-idle-chatter',
	motion: 'aphelion-parsec-reduced-motion-override',
	logMode: 'aphelion-parsec-log-mode',
	activityRetention: 'aphelion-parsec-activity-retention',
} as const;

export interface NormalizedFurniturePosition {
	x: number;
	y: number;
	anchor: 'habitat' | 'app-edge';
}

export interface CompanionProfileV1 {
	schemaVersion: 1;
	consent: ExcursionConsent;
	settings: CompanionSettings;
	familiarity: FamiliarityProfile;
	furnishings: {
		bed: NormalizedFurniturePosition;
		cage: NormalizedFurniturePosition;
	};
}

export type CompanionProfileImport =
	| { ok: true; profile: CompanionProfileV1 }
	| { ok: false; error: string };

export function defaultCompanionProfile(): CompanionProfileV1 {
	return {
		schemaVersion: 1,
		consent: 'unconfigured',
		settings: {
			...DEFAULT_COMPANION_SETTINGS,
			audio: { ...DEFAULT_COMPANION_SETTINGS.audio },
		},
		familiarity: {
			band: 0,
			preferences: [],
			discoveredReactionIds: [],
			interactionSignals: 0,
		},
		furnishings: {
			bed: { x: 0.18, y: 0.76, anchor: 'habitat' },
			cage: { x: 0.72, y: 0.72, anchor: 'habitat' },
		},
	};
}

function record(value: unknown): Record<string, unknown> | null {
	return typeof value === 'object' && value !== null && !Array.isArray(value)
		? value as Record<string, unknown>
		: null;
}

function enumValue<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
	return typeof value === 'string' && (allowed as readonly string[]).includes(value) ? value as T : fallback;
}

function finiteNumber(value: unknown, fallback: number): number {
	return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function normalized(value: unknown, fallback: number): number {
	return Math.min(1, Math.max(0, finiteNumber(value, fallback)));
}

function booleanValue(value: unknown, fallback: boolean): boolean {
	return typeof value === 'boolean' ? value : fallback;
}

function retention(value: unknown, fallback: CompanionSettings['activityRetention']): CompanionSettings['activityRetention'] {
	return value === 7 || value === 30 || value === 90 || value === 365 || value === 'manual' ? value : fallback;
}

function sanitizeSettings(value: unknown, defaults: CompanionSettings): CompanionSettings {
	const source = record(value) ?? {};
	const audio = record(source.audio) ?? {};
	return {
		presence: enumValue(source.presence, ['habitat-only', 'edge-biased', 'intrusive'], defaults.presence),
		idleChatter: enumValue(source.idleChatter, ['off', 'rare', 'occasional', 'frequent'], defaults.idleChatter),
		motion: enumValue(source.motion, ['animate', 'reduce'], defaults.motion),
		logMode: enumValue(source.logMode, ['compact', 'collapsed', 'expanded'], defaults.logMode),
		activityRetention: retention(source.activityRetention, defaults.activityRetention),
		personalityTone: enumValue(source.personalityTone, ['warm', 'playful-flirtatious', 'impish'], defaults.personalityTone),
		handlingPhysics: enumValue(source.handlingPhysics, ['carry-only', 'gentle-momentum', 'full-tossing'], defaults.handlingPhysics),
		handlingReactions: enumValue(source.handlingReactions, ['subdued', 'expressive', 'dramatic'], defaults.handlingReactions),
		feedbackPersonality: booleanValue(source.feedbackPersonality, defaults.feedbackPersonality),
		reducedDistraction: booleanValue(source.reducedDistraction, defaults.reducedDistraction),
		audio: {
			enabled: booleanValue(audio.enabled, defaults.audio.enabled),
			master: normalized(audio.master, defaults.audio.master),
			voice: normalized(audio.voice, defaults.audio.voice),
			effects: normalized(audio.effects, defaults.audio.effects),
			alerts: normalized(audio.alerts, defaults.audio.alerts),
			rareIdle: normalized(audio.rareIdle, defaults.audio.rareIdle),
		},
	};
}

function sanitizeFurniture(value: unknown, fallback: NormalizedFurniturePosition): NormalizedFurniturePosition {
	const source = record(value) ?? {};
	return {
		x: normalized(source.x, fallback.x),
		y: normalized(source.y, fallback.y),
		anchor: enumValue(source.anchor, ['habitat', 'app-edge'], fallback.anchor),
	};
}

function strings(value: unknown): string[] {
	if (!Array.isArray(value)) return [];
	return [...new Set(value.filter((entry): entry is string => typeof entry === 'string').slice(0, 128))];
}

function sanitizeProfile(value: unknown): CompanionProfileV1 | null {
	const source = record(value);
	if (!source || source.schemaVersion !== 1) return null;
	const defaults = defaultCompanionProfile();
	const familiarity = record(source.familiarity) ?? {};
	const furnishings = record(source.furnishings) ?? {};
	const bandValue = finiteNumber(familiarity.band, defaults.familiarity.band);
	const band = Math.min(3, Math.max(0, Math.trunc(bandValue))) as FamiliarityBand;
	return {
		schemaVersion: 1,
		consent: enumValue(source.consent, ['unconfigured', 'allowed', 'ask-each-time', 'habitat-only'], defaults.consent),
		settings: sanitizeSettings(source.settings, defaults.settings),
		familiarity: {
			band,
			preferences: strings(familiarity.preferences),
			discoveredReactionIds: strings(familiarity.discoveredReactionIds),
			interactionSignals: Math.min(255, Math.max(0, Math.trunc(finiteNumber(familiarity.interactionSignals, 0)))),
		},
		furnishings: {
			bed: sanitizeFurniture(furnishings.bed, defaults.furnishings.bed),
			cage: sanitizeFurniture(furnishings.cage, defaults.furnishings.cage),
		},
	};
}

function migrateLegacy(storage: Storage, profile: CompanionProfileV1): CompanionProfileV1 {
	const settings = { ...profile.settings };
	const idle = storage.getItem(LEGACY_KEYS.idleChatter);
	settings.idleChatter = enumValue(idle, ['off', 'rare', 'occasional', 'frequent'], settings.idleChatter);
	const motion = storage.getItem(LEGACY_KEYS.motion);
	settings.motion = enumValue(motion, ['animate', 'reduce'], settings.motion);
	const logMode = storage.getItem(LEGACY_KEYS.logMode);
	settings.logMode = enumValue(logMode, ['compact', 'collapsed', 'expanded'], settings.logMode);
	const retentionSource = storage.getItem(LEGACY_KEYS.activityRetention);
	settings.activityRetention = retention(
		retentionSource === 'manual' ? retentionSource : Number(retentionSource),
		settings.activityRetention,
	);
	for (const key of Object.values(LEGACY_KEYS)) storage.removeItem(key);
	return { ...profile, settings };
}

export function saveCompanionProfile(storage: Storage, profile: CompanionProfileV1): void {
	let previous: CompanionProfileV1 | null = null;
	try { previous = sanitizeProfile(JSON.parse(storage.getItem(COMPANION_PROFILE_KEY) ?? 'null')); } catch { /* A repaired profile replaces invalid storage. */ }
	storage.setItem(COMPANION_PROFILE_KEY, JSON.stringify(profile));
	if (typeof window !== 'undefined' && storage === window.localStorage) {
		window.dispatchEvent(new Event('parsec-profile-change'));
		if (previous?.settings.idleChatter !== profile.settings.idleChatter) window.dispatchEvent(new Event('parsec-idle-preference-change'));
		if (previous?.settings.logMode !== profile.settings.logMode) window.dispatchEvent(new Event('parsec-log-mode-change'));
	}
}

export function loadCompanionProfile(
	storage: Storage = window.localStorage,
	now: () => number = Date.now,
): CompanionProfileV1 {
	const defaults = defaultCompanionProfile();
	try {
		const source = storage.getItem(COMPANION_PROFILE_KEY);
		if (source === null) {
			const migrated = migrateLegacy(storage, defaults);
			saveCompanionProfile(storage, migrated);
			return migrated;
		}
		try {
			const parsed = sanitizeProfile(JSON.parse(source));
			if (parsed) return parsed;
		} catch {
			// Quarantine below with the original text intact.
		}
		storage.setItem(`aphelion-parsec-profile-corrupt-${now()}`, source);
		saveCompanionProfile(storage, defaults);
		return defaults;
	} catch {
		return defaults;
	}
}

export function exportCompanionProfile(profile: CompanionProfileV1): string {
	return JSON.stringify(profile, null, 2);
}

export function importCompanionProfile(source: string): CompanionProfileImport {
	try {
		const profile = sanitizeProfile(JSON.parse(source));
		return profile ? { ok: true, profile } : { ok: false, error: 'Unsupported or invalid Parsec profile.' };
	} catch {
		return { ok: false, error: 'The Parsec profile is not valid JSON.' };
	}
}

import type { ActivityRetentionDays } from './journalTypes';
import type { IdleChatterPreference, ParsecLogMode } from './types';
import { loadCompanionProfile, saveCompanionProfile } from './profile';

export function readIdleChatterPreference(): IdleChatterPreference {
	return loadCompanionProfile().settings.idleChatter;
}

export function writeIdleChatterPreference(preference: IdleChatterPreference): void {
	try {
		const profile = loadCompanionProfile();
		saveCompanionProfile(window.localStorage, {
			...profile,
			settings: { ...profile.settings, idleChatter: preference },
		});
	} catch {
		// A local preference is not important enough to create recursive feedback about storage.
	}
}

export function readParsecLogMode(): ParsecLogMode {
	return loadCompanionProfile().settings.logMode;
}

export function writeParsecLogMode(mode: ParsecLogMode): void {
	try {
		const profile = loadCompanionProfile();
		saveCompanionProfile(window.localStorage, {
			...profile,
			settings: { ...profile.settings, logMode: mode },
		});
	} catch {
		// Feedback preferences cannot report storage failures through the feedback system they configure.
	}
}

export function readActivityRetention(): ActivityRetentionDays {
	return loadCompanionProfile().settings.activityRetention;
}

export function writeActivityRetention(retention: ActivityRetentionDays): void {
	try {
		const profile = loadCompanionProfile();
		saveCompanionProfile(window.localStorage, {
			...profile,
			settings: { ...profile.settings, activityRetention: retention },
		});
	} catch {
		// The journal retains its current safe default when local preferences are unavailable.
	}
}

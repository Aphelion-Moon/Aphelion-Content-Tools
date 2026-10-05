// Parsec's sprite engine, as pure data + pure functions.
//
// Structurally inspired by oneko.js (github.com/adryd325/oneko.js, MIT): a requestAnimationFrame loop
// throttled to a low frame rate, stepping through a named state's sprite-sheet coordinates. Rewritten
// for this use case -- she is confined to a small container rather than chasing the cursor, and her
// state is driven by job status and app events rather than cursor proximity.
//
// Artwork: regenerated Parsec frames converted with PortalRabbit; see the Parsec asset register.

import { coreFallbackManifest } from '~/assets/parsec/manifest.v1';
import { resolveClip } from './parsec/assets';
import { loadCompanionProfile, saveCompanionProfile } from './parsec/profile';

export const CELL_WIDTH = 72;
export const CELL_HEIGHT = 51;
export const FRAME_INTERVAL_MS = 150; // ~6-7fps; plenty for blocky pixel art
export const PATROL_SPEED_PX_PER_TICK = 2;

export const REACTION_DURATION_MS = 900;
export const TWERK_DURATION_MS = 1800; // longer than a normal reaction -- let the joke land
export const TWERK_CLICK_THRESHOLD = 6;
export const TWERK_WINDOW_MS = 3000;

export interface Frame {
	readonly x: number;
	readonly y: number;
}

function row(index: number, columns: number): readonly Frame[] {
	return Array.from({ length: columns }, (_, column) => ({
		x: column * CELL_WIDTH,
		y: index * CELL_HEIGHT,
	}));
}

/**
 * Row 0 is a sitting-idle loop: a consistent seated posture where only the tail moves. An earlier
 * standing+tail-curl row was used here and turned out to be a non-loopable sit-down/stand-up
 * transition -- cycling it looked like she kept standing up and sitting back down. That row now lives
 * on as `twerking` (row 3), a hidden reaction, rather than being discarded.
 */
export const FRAME_SETS = {
	idle: row(0, 4),
	working: row(1, 6),
	happy: row(2, 2),
	twerking: row(3, 3),
} as const;

export type ParsecState = keyof typeof FRAME_SETS;

export function resolveState(state: string): ParsecState {
	if (state in FRAME_SETS) return state as ParsecState;
	let clip = resolveClip(state, coreFallbackManifest);
	const visited = new Set<string>();
	while (clip.fallback && !visited.has(clip.id)) {
		visited.add(clip.id);
		const fallback = coreFallbackManifest.clips[clip.fallback];
		if (!fallback) break;
		clip = fallback;
	}
	const legacyState = Object.entries(coreFallbackManifest.legacyStates)
		.find(([, clipId]) => clipId === clip.id)?.[0];
	return legacyState && legacyState in FRAME_SETS ? legacyState as ParsecState : 'idle';
}

export function nextFrameIndex(frameIndex: number, frameCount: number): number {
	return (frameIndex + 1) % frameCount;
}

export interface PatrolState {
	readonly x: number;
	readonly direction: 1 | -1;
}

/** Walk one step, reversing exactly at either wall. */
export function advancePatrol(
	state: PatrolState & { readonly maxX: number; readonly speed: number },
): PatrolState {
	if (state.maxX <= 0) return { x: 0, direction: state.direction };
	const next = state.x + state.direction * state.speed;
	if (next >= state.maxX) return { x: state.maxX, direction: -1 };
	if (next <= 0) return { x: 0, direction: 1 };
	return { x: next, direction: state.direction };
}

/** Centre a speech-balloon tail on Parsec while keeping it clear of the stage corners. */
export function clampBalloonAnchor(spriteLeft: number, stageWidth: number, spriteWidth: number): number {
	const cornerMargin = 18;
	const centred = spriteLeft + spriteWidth / 2;
	const maximum = Math.max(cornerMargin, stageWidth - cornerMargin);
	return Math.min(maximum, Math.max(cornerMargin, centred));
}

/**
 * Whether enough rapid pats have landed to trigger the hidden reaction.
 *
 * Returns the retained timestamps so the caller stays stateless about the window.
 */
export function registerPat(
	timestamps: readonly number[],
	now: number,
): { readonly timestamps: readonly number[]; readonly reaction: 'happy' | 'twerking' } {
	const recent = timestamps.filter((stamp) => now - stamp < TWERK_WINDOW_MS);
	recent.push(now);
	if (recent.length >= TWERK_CLICK_THRESHOLD) return { timestamps: [], reaction: 'twerking' };
	return { timestamps: recent, reaction: 'happy' };
}

export type MotionPreference = 'animate' | 'reduce';

export function readMotionPreference(): MotionPreference {
	return loadCompanionProfile().settings.motion;
}

export function writeMotionPreference(preference: MotionPreference): void {
	try {
		const profile = loadCompanionProfile();
		saveCompanionProfile(window.localStorage, {
			...profile,
			settings: { ...profile.settings, motion: preference },
		});
	} catch {
		// Not persisting a preference is not worth surfacing an error for.
	}
}

/**
 * Only Parsec's explicit in-app preference reduces motion. System animation suppression and older
 * follow-system preferences never stop her animation or change her handling physics.
 */
export function prefersReducedMotion(preference: MotionPreference | 'follow-system' = readMotionPreference()): boolean {
	return preference === 'reduce';
}

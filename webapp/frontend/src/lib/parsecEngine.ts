// Parsec's sprite engine, as pure data + pure functions.
//
// Structurally inspired by oneko.js (github.com/adryd325/oneko.js, MIT): a requestAnimationFrame loop
// throttled to a low frame rate, stepping through a named state's sprite-sheet coordinates. Rewritten
// for this use case -- she is confined to a small container rather than chasing the cursor, and her
// state is driven by job status and app events rather than cursor proximity.
//
// Artwork: cropped and repacked from "Husky Sprites" (opengameart.org/content/husky-sprites), CC0.

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
	return state in FRAME_SETS ? (state as ParsecState) : 'idle';
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

const REDUCED_MOTION_KEY = 'aphelion-parsec-reduced-motion-override';

export type MotionPreference = 'animate' | 'follow-system' | 'reduce';

export function readMotionPreference(): MotionPreference {
	try {
		const stored = window.localStorage.getItem(REDUCED_MOTION_KEY);
		if (stored === 'reduce' || stored === 'follow-system') return stored;
	} catch {
		// Storage disabled; fall through to the default.
	}
	return 'animate';
}

export function writeMotionPreference(preference: MotionPreference): void {
	try {
		if (preference === 'animate') window.localStorage.removeItem(REDUCED_MOTION_KEY);
		else window.localStorage.setItem(REDUCED_MOTION_KEY, preference);
	} catch {
		// Not persisting a preference is not worth surfacing an error for.
	}
}

/**
 * Whether to hold still.
 *
 * Defaults to animating regardless of the OS setting. She is a small sprite fully confined to her own
 * box, not the large-scale motion `prefers-reduced-motion` exists to guard against, and that setting is
 * commonly on for unrelated reasons -- on Windows, Settings > Ease of Access > Display > "Show
 * animations in Windows" maps straight to it, which left her looking frozen for most people. Anyone who
 * does want her still can choose "Always reduce motion" explicitly.
 */
export function prefersReducedMotion(preference: MotionPreference = readMotionPreference()): boolean {
	if (preference === 'reduce') return true;
	if (preference === 'follow-system') {
		return (
			typeof window !== 'undefined' &&
			typeof window.matchMedia === 'function' &&
			window.matchMedia('(prefers-reduced-motion: reduce)').matches
		);
	}
	return false;
}

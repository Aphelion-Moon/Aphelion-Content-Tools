import { describe, expect, it } from 'vitest';
import {
	CELL_HEIGHT,
	CELL_WIDTH,
	FRAME_SETS,
	TWERK_CLICK_THRESHOLD,
	TWERK_WINDOW_MS,
	advancePatrol,
	clampBalloonAnchor,
	nextFrameIndex,
	prefersReducedMotion,
	registerPat,
	resolveState,
} from './parsecEngine';

// The engine is tested as pure functions because requestAnimationFrame cannot be relied on to verify
// it: an automated browser pane that is not compositing never fires rAF at all (measured: 0 callbacks
// in 2 seconds, document.hidden true). The frame maths has to be checkable without it.

describe('frame sets', () => {
	it('gives each state its own sprite-sheet row', () => {
		const rows = Object.values(FRAME_SETS).map((frames) => frames[0]!.y);
		expect(new Set(rows).size).toBe(Object.keys(FRAME_SETS).length);
	});

	it('spaces columns evenly by CELL_WIDTH from zero', () => {
		for (const frames of Object.values(FRAME_SETS)) {
			frames.forEach((frame, index) => expect(frame.x).toBe(index * CELL_WIDTH));
		}
	});

	it('puts twerking on row 3, where the mis-picked idle animation was rehomed', () => {
		expect(FRAME_SETS.twerking[0]!.y).toBe(CELL_HEIGHT * 3);
		expect(FRAME_SETS.twerking).toHaveLength(3);
	});

	it('gives idle four frames, the loopable sitting pose', () => {
		expect(FRAME_SETS.idle).toHaveLength(4);
		expect(FRAME_SETS.idle[0]!.y).toBe(0);
	});
});

describe('resolveState', () => {
	it('passes through every known state', () => {
		for (const name of Object.keys(FRAME_SETS)) expect(resolveState(name)).toBe(name);
	});

	it('falls back to idle for anything unrecognised', () => {
		expect(resolveState('dancing')).toBe('idle');
		expect(resolveState('')).toBe('idle');
	});

	it('maps requested action animations to deliberate core-sheet fallbacks', () => {
		expect(resolveState('search')).toBe('working');
		expect(resolveState('fetch')).toBe('working');
		expect(resolveState('pant')).toBe('idle');
		expect(resolveState('anxious')).toBe('idle');
		expect(resolveState('confused')).toBe('idle');
		expect(resolveState('growl')).toBe('idle');
	});
});

describe('nextFrameIndex', () => {
	it('advances and wraps back to zero', () => {
		expect(nextFrameIndex(0, 4)).toBe(1);
		expect(nextFrameIndex(3, 4)).toBe(0);
	});
});

describe('advancePatrol', () => {
	it('walks right and reverses exactly at the right wall', () => {
		let state = advancePatrol({ x: 0, direction: 1, maxX: 10, speed: 4 });
		expect(state).toEqual({ x: 4, direction: 1 });
		state = advancePatrol({ ...state, maxX: 10, speed: 4 });
		expect(state).toEqual({ x: 8, direction: 1 });
		// 8 + 4 overshoots, so it clamps to the wall and turns around.
		state = advancePatrol({ ...state, maxX: 10, speed: 4 });
		expect(state).toEqual({ x: 10, direction: -1 });
	});

	it('walks left and reverses exactly at the left wall', () => {
		const state = advancePatrol({ x: 2, direction: -1, maxX: 10, speed: 4 });
		expect(state).toEqual({ x: 0, direction: 1 });
	});

	it('stays put when the box is too narrow to patrol', () => {
		expect(advancePatrol({ x: 0, direction: 1, maxX: 0, speed: 4 })).toEqual({ x: 0, direction: 1 });
	});
});

describe('balloon anchor', () => {
	it('centres on the sprite and clamps the tail away from both stage corners', () => {
		expect(clampBalloonAnchor(0, 240, 72)).toBe(36);
		expect(clampBalloonAnchor(230, 240, 72)).toBe(222);
	});
});

describe('registerPat', () => {
	it('returns happy for an ordinary pat and keeps the timestamp', () => {
		const result = registerPat([], 1000);
		expect(result.reaction).toBe('happy');
		expect(result.timestamps).toHaveLength(1);
	});

	it('triggers twerking once enough pats land inside the window, then resets', () => {
		let timestamps: readonly number[] = [];
		let reaction = 'happy';
		for (let i = 0; i < TWERK_CLICK_THRESHOLD; i += 1) {
			const result = registerPat(timestamps, 1000 + i * 10);
			timestamps = result.timestamps;
			reaction = result.reaction;
		}
		expect(reaction).toBe('twerking');
		expect(timestamps).toHaveLength(0);
	});

	it('does not trigger when the pats are spread beyond the window', () => {
		let timestamps: readonly number[] = [];
		for (let i = 0; i < TWERK_CLICK_THRESHOLD + 2; i += 1) {
			const result = registerPat(timestamps, i * (TWERK_WINDOW_MS + 100));
			timestamps = result.timestamps;
			expect(result.reaction).toBe('happy');
		}
	});
});

describe('prefersReducedMotion', () => {
	it('animates by default, ignoring the OS setting', () => {
		expect(prefersReducedMotion('animate')).toBe(false);
	});

	it('always reduces when explicitly asked to', () => {
		expect(prefersReducedMotion('reduce')).toBe(true);
	});

	it('ignores system animation suppression for an older follow-system preference', () => {
		const original = window.matchMedia;
		window.matchMedia = ((): MediaQueryList => ({ matches: true }) as MediaQueryList) as typeof window.matchMedia;
		try {
			expect(prefersReducedMotion('follow-system')).toBe(false);
		} finally {
			window.matchMedia = original;
		}
	});
});

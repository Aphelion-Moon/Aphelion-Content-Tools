import { describe, expect, it } from 'vitest';
import { coreFallbackManifest } from '~/assets/parsec/manifest.v1';
import { FRAME_SETS } from '../parsecEngine';
import {
	resolveClip,
	validateParsecManifest,
	type ParsecAssetManifest,
} from './assets';

function cloneManifest(): ParsecAssetManifest {
	return structuredClone(coreFallbackManifest);
}

describe('Parsec asset manifest validation', () => {
	it('preserves brush playback and audio with dedicated character frames', () => {
		const brush = coreFallbackManifest.clips['toy-brush-content']!;
		expect(brush.loopMode).toBe('loop');
		expect(brush.soundCues).toContainEqual({ frame: 1, soundId: 'toy-brush' });
		expect(coreFallbackManifest.clips['touch-pat-soft']!.soundCues).toEqual([]);
	});

	it('freezes Parsec eye colors using anatomical laterality', () => {
		expect(coreFallbackManifest.identityPalette).toEqual({
			leftEye: '#FBD436',
			rightEye: '#FF3CC8',
			laterality: 'anatomical',
		});
	});

	it('freezes the approved creative clip and planned unique-frame budgets', () => {
		const clips = Object.values(coreFallbackManifest.clips).filter((clip) => clip.requiredForCreativeSprint);
		const plannedUniqueFrames = clips.reduce((total, clip) => total + clip.plannedUniqueFrames, 0);
		expect(clips).toHaveLength(60);
		expect(plannedUniqueFrames).toBe(293);
	});

	it('publishes dedicated regenerated actor and effect clips', () => {
		const coreIds = [
			'core-idle-seated', 'core-idle-standing', 'core-idle-sniff', 'core-idle-scratch',
			'core-idle-yawn', 'core-idle-pant', 'core-look-cursor', 'core-walk-cardinal',
			'core-walk-diagonal', 'core-return-home',
		];
		const feedbackIds = [
			'search-sniff', 'fetch-dig', 'feedback-working-focus', 'feedback-success-wag',
			'feedback-success-proud', 'feedback-warning-alert', 'error-anxious',
			'empty-confused', 'tool-growl', 'reconnect-pant',
		];
		const touchIds = [
			'touch-pat-soft', 'touch-pat-delighted', 'touch-nose-lick', 'touch-scruff-calm',
			'touch-scruff-playful', 'touch-scruff-pout', 'touch-release-drop',
			'touch-release-toss', 'touch-landing-bounce', 'touch-landing-recover',
		];
		const toyIds = [
			'toy-ball-ready', 'toy-ball-chase', 'toy-ball-retrieve', 'toy-ball-refuse',
			'toy-tug-grip', 'toy-tug-pull', 'toy-tug-win', 'toy-tug-tumble',
			'toy-brush-content', 'toy-brush-impatient', 'toy-treat-accept', 'toy-whistle-recall',
		];
		const habitatIds = [
			'habitat-bed-approach', 'habitat-bed-lie-down', 'habitat-bed-sleep', 'habitat-bed-timeout-pout',
			'habitat-cage-enter', 'habitat-cage-open-idle', 'habitat-cage-latched-pout', 'habitat-cage-release',
		];
		const intrusiveIds = [
			'intrusive-cursor-stalk', 'intrusive-cursor-pounce', 'intrusive-loiter',
			'intrusive-demand-attention', 'intrusive-zoomies',
		];
		const effectIds = [
			'effect-hearts', 'effect-station-alert', 'effect-scent-trail',
			'effect-radio-ping', 'effect-dust-landing',
		];

		expect(coreFallbackManifest.sheets['parsec-core']).toMatchObject({
			width: 768,
			height: 768,
			frameWidth: 96,
			frameHeight: 96,
		});
		expect(coreFallbackManifest.sheets['parsec-feedback']).toMatchObject({
			width: 672,
			height: 672,
			frameWidth: 96,
			frameHeight: 96,
		});
		expect(coreFallbackManifest.sheets['parsec-touch']).toMatchObject({
			width: 672,
			height: 672,
			frameWidth: 96,
			frameHeight: 96,
		});
		expect(coreFallbackManifest.sheets['parsec-toys']).toMatchObject({
			width: 768,
			height: 768,
			frameWidth: 96,
			frameHeight: 96,
		});
		expect(coreFallbackManifest.sheets['parsec-habitat']).toMatchObject({
			width: 672,
			height: 576,
			frameWidth: 96,
			frameHeight: 96,
		});
		expect(coreFallbackManifest.sheets['parsec-intrusive']).toMatchObject({
			width: 576,
			height: 480,
			frameWidth: 96,
			frameHeight: 96,
		});
		expect(coreFallbackManifest.sheets['parsec-effects']).toMatchObject({
			width: 480,
			height: 384,
			frameWidth: 96,
			frameHeight: 96,
		});
		expect(coreIds.reduce((total, id) => total + coreFallbackManifest.clips[id]!.frames.length, 0)).toBe(59);
		expect(feedbackIds.reduce((total, id) => total + coreFallbackManifest.clips[id]!.frames.length, 0)).toBe(46);
		expect(touchIds.reduce((total, id) => total + coreFallbackManifest.clips[id]!.frames.length, 0)).toBe(48);
		expect(toyIds.reduce((total, id) => total + coreFallbackManifest.clips[id]!.frames.length, 0)).toBe(59);
		expect(habitatIds.reduce((total, id) => total + coreFallbackManifest.clips[id]!.frames.length, 0)).toBe(37);
		expect(intrusiveIds.reduce((total, id) => total + coreFallbackManifest.clips[id]!.frames.length, 0)).toBe(27);
		expect(effectIds.reduce((total, id) => total + coreFallbackManifest.clips[id]!.frames.length, 0)).toBe(17);
		for (const id of [...coreIds, ...feedbackIds, ...touchIds, ...toyIds, ...habitatIds, ...intrusiveIds, ...effectIds]) {
			const clip = coreFallbackManifest.clips[id]!;
			expect(clip.creativeStatus).toBe('accepted');
			expect(clip.visualReview).toBeDefined();
			expect(clip.frames).toHaveLength(clip.plannedUniqueFrames);
			expect(clip.frames.every((frameId) => frameId.startsWith(`${clip.atlas}/`))).toBe(true);
		}
		expect(coreFallbackManifest.clips['touch-pat-soft']).toMatchObject({
			creativeStatus: 'accepted',
			atlas: 'parsec-touch',
			fallback: 'happy-reaction',
		});
		expect(coreFallbackManifest.clips['core-idle-seated']!.durationsMs).toEqual([2600, 800, 120, 900]);
		expect(coreFallbackManifest.clips['search-sniff']!.durationsMs).toEqual([150, 150, 180, 150, 240]);
		expect(coreFallbackManifest.clips['touch-release-toss']!.durationsMs).toEqual([80, 80, 90, 100, 120, 220]);
		expect(coreFallbackManifest.clips['toy-tug-win']!.durationsMs).toEqual([90, 100, 120, 180, 320]);
		expect(coreFallbackManifest.clips['habitat-bed-sleep']!.durationsMs).toEqual([360, 360, 180, 360, 520]);
		expect(coreFallbackManifest.clips['intrusive-cursor-pounce']!.durationsMs).toEqual([80, 80, 90, 100, 140, 260]);
		expect(coreFallbackManifest.clips['effect-station-alert']!.durationsMs).toEqual([120, 180, 360]);
		expect(coreFallbackManifest.clips['core-walk-cardinal']!.defaultDirection).toBe('east');
		expect(coreFallbackManifest.clips['core-walk-cardinal']!.directionVariants).toEqual({
			north: {
				frames: [
					'parsec-core/core-walk-cardinal/d0/f0',
					'parsec-core/core-walk-cardinal/d0/f1',
					'parsec-core/core-walk-cardinal/d0/f2',
				],
				durationsMs: [120, 120, 120],
				reducedMotionFrame: 'parsec-core/core-walk-cardinal/d0/f0',
			},
			east: {
				frames: [
					'parsec-core/core-walk-cardinal/d1/f0',
					'parsec-core/core-walk-cardinal/d1/f1',
					'parsec-core/core-walk-cardinal/d1/f2',
				],
				durationsMs: [120, 120, 120],
				reducedMotionFrame: 'parsec-core/core-walk-cardinal/d1/f0',
			},
			south: {
				frames: [
					'parsec-core/core-walk-cardinal/d2/f0',
					'parsec-core/core-walk-cardinal/d2/f1',
					'parsec-core/core-walk-cardinal/d2/f2',
				],
				durationsMs: [120, 120, 120],
				reducedMotionFrame: 'parsec-core/core-walk-cardinal/d2/f0',
			},
			west: {
				frames: [
					'parsec-core/core-walk-cardinal/d3/f0',
					'parsec-core/core-walk-cardinal/d3/f1',
					'parsec-core/core-walk-cardinal/d3/f2',
				],
				durationsMs: [120, 120, 120],
				reducedMotionFrame: 'parsec-core/core-walk-cardinal/d3/f0',
			},
		});
	});

	it('publishes every approved SS13 habitat and toy object from the real object atlas', () => {
		expect(coreFallbackManifest.sheets['ss13-objects']).toMatchObject({
			width: 384,
			height: 288,
			frameWidth: 96,
			frameHeight: 96,
			provenanceId: 'ss13-rift-objects',
		});
		for (const id of [
			'dogbed', 'cage-open', 'cage-closed', 'cage-locked', 'cage-occupied',
			'tennis-ball', 'hairbrush', 'toy-mouse', 'carp-plush', 'toolbox', 'tug-rope',
		]) {
			expect(coreFallbackManifest.objects[id]).toMatchObject({
				frameId: `ss13-objects/${id}/d0/f0`,
				provenanceId: 'ss13-rift-objects',
			});
			expect(coreFallbackManifest.frames[`ss13-objects/${id}/d0/f0`]).toMatchObject({
				sheetId: 'ss13-objects',
				width: 96,
				height: 96,
			});
		}
	});

	it('publishes all eight exact-copy audio cues with runtime policy and provenance', () => {
		for (const id of [
			'voice-bark', 'voice-growl', 'toy-squeak', 'toy-brush',
			'toy-whistle', 'toy-handling', 'radio-alert', 'rare-idle',
		]) {
			expect(coreFallbackManifest.sounds[id]).toMatchObject({
				provenanceId: 'ss13-rift-audio',
				fallback: 'silent',
			});
			expect(coreFallbackManifest.sounds[id]!.src).toMatch(/\.ogg$/);
			expect(coreFallbackManifest.sounds[id]!.authoredVolume).toBeGreaterThan(0);
			expect(coreFallbackManifest.sounds[id]!.cooldownMs).toBeGreaterThanOrEqual(0);
		}
	});

	it('gives every required clip anchors, a reduced-motion frame, and an existing fallback', () => {
		const requiredClips = Object.values(coreFallbackManifest.clips).filter((clip) => clip.requiredForCreativeSprint);
		for (const clip of requiredClips) {
			expect(clip.fallback).not.toBeNull();
			expect(coreFallbackManifest.clips[clip.fallback!]).toBeDefined();
			expect(clip.frames).toContain(clip.reducedMotionFrame);
			for (const frameId of clip.frames) {
				const frame = coreFallbackManifest.frames[frameId]!;
				for (const anchor of clip.requiredAnchors) expect(frame.anchors[anchor]).toBeDefined();
			}
		}
	});

	it('rejects a looping clip with no frames or valid reduced-motion representative', () => {
		const manifest = cloneManifest();
		manifest.clips['seated-idle'] = {
			...manifest.clips['seated-idle']!,
			frames: [],
			reducedMotionFrame: 'missing-frame',
		};

		expect(validateParsecManifest(manifest)).toEqual(expect.arrayContaining([
			'clips.seated-idle.frames must contain at least one frame',
			'clips.seated-idle.reducedMotionFrame must reference one of its frames',
		]));
	});

	it('rejects out-of-bounds frames, missing provenance, and cyclic aliases', () => {
		const manifest = cloneManifest();
		manifest.frames['idle-0'] = { ...manifest.frames['idle-0']!, x: 500 };
		manifest.sheets.core = { ...manifest.sheets.core!, provenanceId: 'missing-source' };
		manifest.aliases.a = 'b';
		manifest.aliases.b = 'a';

		const errors = validateParsecManifest(manifest);
		expect(errors).toContain('frames.idle-0 extends beyond sheets.core width');
		expect(errors).toContain('sheets.core.provenanceId references missing-source');
		expect(errors).toContain('aliases.a contains a fallback cycle');
	});

	it('rejects incomplete directional playback variants', () => {
		const manifest = cloneManifest();
		const walk = manifest.clips['core-walk-cardinal']!;
		manifest.clips['core-walk-cardinal'] = {
			...walk,
			defaultDirection: 'missing',
			directionVariants: {
				...walk.directionVariants,
				east: {
					...walk.directionVariants!.east!,
					durationsMs: [],
				},
			},
		};

		const errors = validateParsecManifest(manifest);
		expect(errors).toContain('clips.core-walk-cardinal.defaultDirection references missing');
		expect(errors).toContain('clips.core-walk-cardinal.directionVariants.east durations must match its frame count');
	});
});

describe('Parsec asset fallback resolution', () => {
	it('resolves accepted feedback clips directly while retaining an unknown-state fallback', () => {
		expect(resolveClip('search-sniff', coreFallbackManifest).id).toBe('search-sniff');
		expect(resolveClip('fetch-dig', coreFallbackManifest).id).toBe('fetch-dig');
		expect(resolveClip('error-anxious', coreFallbackManifest).id).toBe('error-anxious');
		expect(resolveClip('unknown', coreFallbackManifest).id).toBe('seated-idle');
	});

	it('preserves every current sprite-sheet coordinate through the manifest', () => {
		for (const [state, frames] of Object.entries(FRAME_SETS)) {
			const clipId = coreFallbackManifest.legacyStates[state]!;
			const clip = resolveClip(clipId, coreFallbackManifest);
			expect(clip.frames.map((frameId) => {
				const frame = coreFallbackManifest.frames[frameId]!;
				return { x: frame.x, y: frame.y };
			})).toEqual(frames);
		}
	});
});

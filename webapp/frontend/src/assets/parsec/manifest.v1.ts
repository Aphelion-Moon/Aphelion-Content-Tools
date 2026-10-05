import spriteUrl from '../parsec.png';
import coreAtlasCoordinates from './parsec-core.json';
import coreAtlasAnchors from './parsec-core.anchors.json';
import coreAtlasUrl from './parsec-core.png';
import feedbackAtlasCoordinates from './parsec-feedback.json';
import feedbackAtlasAnchors from './parsec-feedback.anchors.json';
import feedbackAtlasUrl from './parsec-feedback.png';
import touchAtlasCoordinates from './parsec-touch.json';
import touchAtlasAnchors from './parsec-touch.anchors.json';
import touchAtlasUrl from './parsec-touch.png';
import toyAtlasCoordinates from './parsec-toys.json';
import toyAtlasAnchors from './parsec-toys.anchors.json';
import toyAtlasUrl from './parsec-toys.png';
import habitatAtlasCoordinates from './parsec-habitat.json';
import habitatAtlasAnchors from './parsec-habitat.anchors.json';
import habitatAtlasUrl from './parsec-habitat.png';
import intrusiveAtlasCoordinates from './parsec-intrusive.json';
import intrusiveAtlasAnchors from './parsec-intrusive.anchors.json';
import intrusiveAtlasUrl from './parsec-intrusive.png';
import effectsAtlasCoordinates from './parsec-effects.json';
import effectsAtlasAnchors from './parsec-effects.anchors.json';
import effectsAtlasUrl from './parsec-effects.png';
import ss13ObjectCoordinates from './ss13-objects.json';
import ss13ObjectAtlasUrl from './ss13-objects.png';
import visualReviewInventory from './parsec-visual-reviews.v1.json';
import voiceBarkUrl from './audio/voice-bark.ogg';
import voiceGrowlUrl from './audio/voice-growl.ogg';
import toySqueakUrl from './audio/toy-squeak.ogg';
import toyBrushUrl from './audio/toy-brush.ogg';
import toyWhistleUrl from './audio/toy-whistle.ogg';
import toyHandlingUrl from './audio/toy-handling.ogg';
import radioAlertUrl from './audio/radio-alert.ogg';
import rareIdleUrl from './audio/rare-idle.ogg';
import type {
	ParsecAnimationClip,
	ParsecAssetManifest,
	ParsecSpriteFrame,
} from '~/lib/parsec/assets';

const CELL_WIDTH = 72;
const CELL_HEIGHT = 51;
const FRAME_DURATION_MS = 150;

function frame(id: string, column: number, row: number): ParsecSpriteFrame {
	return {
		id,
		sheetId: 'core',
		x: column * CELL_WIDTH,
		y: row * CELL_HEIGHT,
		width: CELL_WIDTH,
		height: CELL_HEIGHT,
		anchors: {
			feet: { x: 36, y: 49 },
			face: { x: 36, y: 15 },
			scruff: { x: 36, y: 12 },
			mouth: { x: 42, y: 18 },
			interaction: { x: 36, y: 24 },
			toy: { x: 44, y: 28 },
			effect: { x: 36, y: 8 },
			shadow: { x: 36, y: 48 },
		},
	};
}

function clip(id: string, frameIds: string[], loopMode: ParsecAnimationClip['loopMode']): ParsecAnimationClip {
	return {
		id,
		atlas: 'core',
		frames: frameIds,
		durationsMs: frameIds.map(() => FRAME_DURATION_MS),
		loopMode,
		interruptible: true,
		reducedMotionFrame: frameIds[0]!,
		requiredAnchors: ['feet', 'face'],
		requiredForCreativeSprint: false,
		plannedUniqueFrames: frameIds.length,
		creativeStatus: 'accepted',
		soundCues: [],
		fallback: null,
	};
}

interface CreativeClipSpec {
	id: string;
	atlas: string;
	plannedUniqueFrames: number;
	fallback: keyof typeof baseClips;
	loopMode: ParsecAnimationClip['loopMode'];
	requiredAnchors: string[];
}

interface AtlasCoordinate {
	x: number;
	y: number;
	width: number;
	height: number;
}

interface AcceptedCreativeClipSpec {
	id: string;
	atlas: 'parsec-core' | 'parsec-feedback' | 'parsec-touch' | 'parsec-toys' | 'parsec-habitat' | 'parsec-intrusive' | 'parsec-effects';
	directions: number;
	framesPerDirection: number;
	durationsMs: number[];
	reducedMotionIndex: number;
	soundCues: ParsecAnimationClip['soundCues'];
	directionNames?: string[];
	defaultDirection?: string;
}

const productionCoordinates: Record<string, Record<string, AtlasCoordinate>> = {
	'parsec-core': coreAtlasCoordinates,
	'parsec-feedback': feedbackAtlasCoordinates,
	'parsec-touch': touchAtlasCoordinates,
	'parsec-toys': toyAtlasCoordinates,
	'parsec-habitat': habitatAtlasCoordinates,
	'parsec-intrusive': intrusiveAtlasCoordinates,
	'parsec-effects': effectsAtlasCoordinates,
};

const productionAnchors: Record<string, ParsecSpriteFrame['anchors']> = {
	...coreAtlasAnchors,
	...feedbackAtlasAnchors,
	...touchAtlasAnchors,
	...toyAtlasAnchors,
	...habitatAtlasAnchors,
	...intrusiveAtlasAnchors,
	...effectsAtlasAnchors,
};

const productionFrames = Object.fromEntries(Object.entries(productionCoordinates).flatMap(([sheetId, coordinates]) => (
	Object.entries(coordinates).map(([id, coordinate]) => [id, {
		id,
		sheetId,
		...coordinate,
		anchors: productionAnchors[id]!,
	} satisfies ParsecSpriteFrame] as const)
)));

const ss13ObjectFrames = Object.fromEntries(Object.entries(ss13ObjectCoordinates).map(([id, coordinate]) => [id, {
	id,
	sheetId: 'ss13-objects',
	...coordinate,
	anchors: {},
} satisfies ParsecSpriteFrame] as const));

function repeatedDuration(durationMs: number, frameCount: number): number[] {
	return Array.from({ length: frameCount }, () => durationMs);
}

function acceptedFrameIds(spec: AcceptedCreativeClipSpec): string[] {
	return Array.from({ length: spec.directions }, (_, direction) => (
		Array.from({ length: spec.framesPerDirection }, (_unused, frameIndex) => (
			`${spec.atlas}/${spec.id}/d${direction}/f${frameIndex}`
		))
	)).flat();
}

function directionVariants(spec: AcceptedCreativeClipSpec, frameIds: string[]) {
	if (!spec.directionNames) return {};
	return Object.fromEntries(spec.directionNames.map((direction, index) => {
		const start = index * spec.framesPerDirection;
		const frames = frameIds.slice(start, start + spec.framesPerDirection);
		return [direction, {
			frames,
			durationsMs: spec.durationsMs.slice(start, start + spec.framesPerDirection),
			reducedMotionFrame: frames[0]!,
		}];
	}));
}

const frames = Object.fromEntries([
	...Array.from({ length: 4 }, (_, index) => [`idle-${index}`, frame(`idle-${index}`, index, 0)] as const),
	...Array.from({ length: 6 }, (_, index) => [`working-${index}`, frame(`working-${index}`, index, 1)] as const),
	...Array.from({ length: 2 }, (_, index) => [`happy-${index}`, frame(`happy-${index}`, index, 2)] as const),
	...Array.from({ length: 3 }, (_, index) => [`twerking-${index}`, frame(`twerking-${index}`, index, 3)] as const),
]);

const baseClips = {
	'seated-idle': clip('seated-idle', ['idle-0', 'idle-1', 'idle-2', 'idle-3'], 'loop'),
	'working-patrol': clip('working-patrol', ['working-0', 'working-1', 'working-2', 'working-3', 'working-4', 'working-5'], 'loop'),
	'happy-reaction': clip('happy-reaction', ['happy-0', 'happy-1'], 'loop'),
	'twerking-reaction': clip('twerking-reaction', ['twerking-0', 'twerking-1', 'twerking-2'], 'loop'),
};

const creativeClipSpecs: CreativeClipSpec[] = [
	{ id: 'core-idle-seated', atlas: 'parsec-core', plannedUniqueFrames: 4, fallback: 'seated-idle', loopMode: 'loop', requiredAnchors: ['feet', 'face', 'scruff'] },
	{ id: 'core-idle-standing', atlas: 'parsec-core', plannedUniqueFrames: 4, fallback: 'seated-idle', loopMode: 'loop', requiredAnchors: ['feet', 'face', 'scruff'] },
	{ id: 'core-idle-sniff', atlas: 'parsec-core', plannedUniqueFrames: 4, fallback: 'working-patrol', loopMode: 'loop', requiredAnchors: ['feet', 'face', 'mouth'] },
	{ id: 'core-idle-scratch', atlas: 'parsec-core', plannedUniqueFrames: 5, fallback: 'seated-idle', loopMode: 'once', requiredAnchors: ['feet', 'face'] },
	{ id: 'core-idle-yawn', atlas: 'parsec-core', plannedUniqueFrames: 5, fallback: 'seated-idle', loopMode: 'once', requiredAnchors: ['feet', 'face', 'mouth'] },
	{ id: 'core-idle-pant', atlas: 'parsec-core', plannedUniqueFrames: 4, fallback: 'seated-idle', loopMode: 'loop', requiredAnchors: ['feet', 'face', 'mouth'] },
	{ id: 'core-look-cursor', atlas: 'parsec-core', plannedUniqueFrames: 4, fallback: 'seated-idle', loopMode: 'hold', requiredAnchors: ['feet', 'face'] },
	{ id: 'core-walk-cardinal', atlas: 'parsec-core', plannedUniqueFrames: 12, fallback: 'working-patrol', loopMode: 'loop', requiredAnchors: ['feet', 'face'] },
	{ id: 'core-walk-diagonal', atlas: 'parsec-core', plannedUniqueFrames: 12, fallback: 'working-patrol', loopMode: 'loop', requiredAnchors: ['feet', 'face'] },
	{ id: 'core-return-home', atlas: 'parsec-core', plannedUniqueFrames: 5, fallback: 'working-patrol', loopMode: 'once', requiredAnchors: ['feet', 'face'] },
	{ id: 'search-sniff', atlas: 'parsec-feedback', plannedUniqueFrames: 5, fallback: 'working-patrol', loopMode: 'loop', requiredAnchors: ['feet', 'face', 'mouth', 'effect'] },
	{ id: 'fetch-dig', atlas: 'parsec-feedback', plannedUniqueFrames: 6, fallback: 'working-patrol', loopMode: 'loop', requiredAnchors: ['feet', 'face', 'interaction', 'effect'] },
	{ id: 'feedback-working-focus', atlas: 'parsec-feedback', plannedUniqueFrames: 4, fallback: 'working-patrol', loopMode: 'loop', requiredAnchors: ['feet', 'face'] },
	{ id: 'feedback-success-wag', atlas: 'parsec-feedback', plannedUniqueFrames: 5, fallback: 'happy-reaction', loopMode: 'once', requiredAnchors: ['feet', 'face', 'effect'] },
	{ id: 'feedback-success-proud', atlas: 'parsec-feedback', plannedUniqueFrames: 4, fallback: 'happy-reaction', loopMode: 'hold', requiredAnchors: ['feet', 'face'] },
	{ id: 'feedback-warning-alert', atlas: 'parsec-feedback', plannedUniqueFrames: 4, fallback: 'seated-idle', loopMode: 'once', requiredAnchors: ['feet', 'face', 'effect'] },
	{ id: 'error-anxious', atlas: 'parsec-feedback', plannedUniqueFrames: 5, fallback: 'seated-idle', loopMode: 'loop', requiredAnchors: ['feet', 'face'] },
	{ id: 'empty-confused', atlas: 'parsec-feedback', plannedUniqueFrames: 4, fallback: 'seated-idle', loopMode: 'once', requiredAnchors: ['feet', 'face'] },
	{ id: 'tool-growl', atlas: 'parsec-feedback', plannedUniqueFrames: 5, fallback: 'seated-idle', loopMode: 'once', requiredAnchors: ['feet', 'face', 'mouth'] },
	{ id: 'reconnect-pant', atlas: 'parsec-feedback', plannedUniqueFrames: 4, fallback: 'seated-idle', loopMode: 'loop', requiredAnchors: ['feet', 'face', 'mouth'] },
	{ id: 'touch-pat-soft', atlas: 'parsec-touch', plannedUniqueFrames: 4, fallback: 'happy-reaction', loopMode: 'once', requiredAnchors: ['feet', 'face', 'interaction'] },
	{ id: 'touch-pat-delighted', atlas: 'parsec-touch', plannedUniqueFrames: 5, fallback: 'happy-reaction', loopMode: 'once', requiredAnchors: ['feet', 'face', 'interaction', 'effect'] },
	{ id: 'touch-nose-lick', atlas: 'parsec-touch', plannedUniqueFrames: 5, fallback: 'happy-reaction', loopMode: 'once', requiredAnchors: ['feet', 'face', 'mouth', 'interaction'] },
	{ id: 'touch-scruff-calm', atlas: 'parsec-touch', plannedUniqueFrames: 4, fallback: 'seated-idle', loopMode: 'hold', requiredAnchors: ['face', 'scruff'] },
	{ id: 'touch-scruff-playful', atlas: 'parsec-touch', plannedUniqueFrames: 5, fallback: 'happy-reaction', loopMode: 'loop', requiredAnchors: ['face', 'scruff'] },
	{ id: 'touch-scruff-pout', atlas: 'parsec-touch', plannedUniqueFrames: 5, fallback: 'seated-idle', loopMode: 'loop', requiredAnchors: ['face', 'scruff'] },
	{ id: 'touch-release-drop', atlas: 'parsec-touch', plannedUniqueFrames: 4, fallback: 'working-patrol', loopMode: 'once', requiredAnchors: ['feet', 'face', 'scruff'] },
	{ id: 'touch-release-toss', atlas: 'parsec-touch', plannedUniqueFrames: 6, fallback: 'working-patrol', loopMode: 'once', requiredAnchors: ['feet', 'face', 'scruff'] },
	{ id: 'touch-landing-bounce', atlas: 'parsec-touch', plannedUniqueFrames: 6, fallback: 'working-patrol', loopMode: 'once', requiredAnchors: ['feet', 'face', 'effect'] },
	{ id: 'touch-landing-recover', atlas: 'parsec-touch', plannedUniqueFrames: 4, fallback: 'seated-idle', loopMode: 'once', requiredAnchors: ['feet', 'face'] },
	{ id: 'toy-ball-ready', atlas: 'parsec-toys', plannedUniqueFrames: 4, fallback: 'seated-idle', loopMode: 'hold', requiredAnchors: ['feet', 'face', 'mouth', 'toy'] },
	{ id: 'toy-ball-chase', atlas: 'parsec-toys', plannedUniqueFrames: 6, fallback: 'working-patrol', loopMode: 'loop', requiredAnchors: ['feet', 'face', 'toy'] },
	{ id: 'toy-ball-retrieve', atlas: 'parsec-toys', plannedUniqueFrames: 6, fallback: 'working-patrol', loopMode: 'once', requiredAnchors: ['feet', 'face', 'mouth', 'toy'] },
	{ id: 'toy-ball-refuse', atlas: 'parsec-toys', plannedUniqueFrames: 4, fallback: 'seated-idle', loopMode: 'once', requiredAnchors: ['feet', 'face', 'toy'] },
	{ id: 'toy-tug-grip', atlas: 'parsec-toys', plannedUniqueFrames: 4, fallback: 'seated-idle', loopMode: 'hold', requiredAnchors: ['feet', 'face', 'mouth', 'toy'] },
	{ id: 'toy-tug-pull', atlas: 'parsec-toys', plannedUniqueFrames: 6, fallback: 'working-patrol', loopMode: 'loop', requiredAnchors: ['feet', 'face', 'mouth', 'toy'] },
	{ id: 'toy-tug-win', atlas: 'parsec-toys', plannedUniqueFrames: 5, fallback: 'happy-reaction', loopMode: 'once', requiredAnchors: ['feet', 'face', 'mouth', 'toy'] },
	{ id: 'toy-tug-tumble', atlas: 'parsec-toys', plannedUniqueFrames: 5, fallback: 'twerking-reaction', loopMode: 'once', requiredAnchors: ['feet', 'face', 'toy'] },
	{ id: 'toy-brush-content', atlas: 'parsec-toys', plannedUniqueFrames: 5, fallback: 'happy-reaction', loopMode: 'loop', requiredAnchors: ['feet', 'face', 'interaction'] },
	{ id: 'toy-brush-impatient', atlas: 'parsec-toys', plannedUniqueFrames: 4, fallback: 'seated-idle', loopMode: 'once', requiredAnchors: ['feet', 'face', 'interaction'] },
	{ id: 'toy-treat-accept', atlas: 'parsec-toys', plannedUniqueFrames: 5, fallback: 'happy-reaction', loopMode: 'once', requiredAnchors: ['feet', 'face', 'mouth', 'toy'] },
	{ id: 'toy-whistle-recall', atlas: 'parsec-toys', plannedUniqueFrames: 5, fallback: 'working-patrol', loopMode: 'once', requiredAnchors: ['feet', 'face', 'effect'] },
	{ id: 'habitat-bed-approach', atlas: 'parsec-habitat', plannedUniqueFrames: 4, fallback: 'working-patrol', loopMode: 'once', requiredAnchors: ['feet', 'face', 'interaction'] },
	{ id: 'habitat-bed-lie-down', atlas: 'parsec-habitat', plannedUniqueFrames: 5, fallback: 'seated-idle', loopMode: 'once', requiredAnchors: ['feet', 'face', 'interaction'] },
	{ id: 'habitat-bed-sleep', atlas: 'parsec-habitat', plannedUniqueFrames: 5, fallback: 'seated-idle', loopMode: 'loop', requiredAnchors: ['feet', 'face', 'effect'] },
	{ id: 'habitat-bed-timeout-pout', atlas: 'parsec-habitat', plannedUniqueFrames: 4, fallback: 'seated-idle', loopMode: 'loop', requiredAnchors: ['feet', 'face'] },
	{ id: 'habitat-cage-enter', atlas: 'parsec-habitat', plannedUniqueFrames: 5, fallback: 'working-patrol', loopMode: 'once', requiredAnchors: ['feet', 'face', 'interaction'] },
	{ id: 'habitat-cage-open-idle', atlas: 'parsec-habitat', plannedUniqueFrames: 4, fallback: 'seated-idle', loopMode: 'loop', requiredAnchors: ['feet', 'face'] },
	{ id: 'habitat-cage-latched-pout', atlas: 'parsec-habitat', plannedUniqueFrames: 5, fallback: 'seated-idle', loopMode: 'loop', requiredAnchors: ['feet', 'face'] },
	{ id: 'habitat-cage-release', atlas: 'parsec-habitat', plannedUniqueFrames: 5, fallback: 'happy-reaction', loopMode: 'once', requiredAnchors: ['feet', 'face', 'interaction'] },
	{ id: 'intrusive-cursor-stalk', atlas: 'parsec-intrusive', plannedUniqueFrames: 5, fallback: 'working-patrol', loopMode: 'loop', requiredAnchors: ['feet', 'face'] },
	{ id: 'intrusive-cursor-pounce', atlas: 'parsec-intrusive', plannedUniqueFrames: 6, fallback: 'working-patrol', loopMode: 'once', requiredAnchors: ['feet', 'face', 'interaction'] },
	{ id: 'intrusive-loiter', atlas: 'parsec-intrusive', plannedUniqueFrames: 4, fallback: 'seated-idle', loopMode: 'loop', requiredAnchors: ['feet', 'face'] },
	{ id: 'intrusive-demand-attention', atlas: 'parsec-intrusive', plannedUniqueFrames: 5, fallback: 'happy-reaction', loopMode: 'once', requiredAnchors: ['feet', 'face', 'effect'] },
	{ id: 'intrusive-zoomies', atlas: 'parsec-intrusive', plannedUniqueFrames: 7, fallback: 'twerking-reaction', loopMode: 'loop', requiredAnchors: ['feet', 'face', 'effect'] },
	{ id: 'effect-hearts', atlas: 'parsec-effects', plannedUniqueFrames: 3, fallback: 'happy-reaction', loopMode: 'once', requiredAnchors: ['effect'] },
	{ id: 'effect-station-alert', atlas: 'parsec-effects', plannedUniqueFrames: 3, fallback: 'seated-idle', loopMode: 'once', requiredAnchors: ['effect'] },
	{ id: 'effect-scent-trail', atlas: 'parsec-effects', plannedUniqueFrames: 4, fallback: 'working-patrol', loopMode: 'loop', requiredAnchors: ['effect'] },
	{ id: 'effect-radio-ping', atlas: 'parsec-effects', plannedUniqueFrames: 3, fallback: 'seated-idle', loopMode: 'once', requiredAnchors: ['effect'] },
	{ id: 'effect-dust-landing', atlas: 'parsec-effects', plannedUniqueFrames: 4, fallback: 'working-patrol', loopMode: 'once', requiredAnchors: ['feet', 'effect'] },
];

const acceptedCreativeClipSpecs: AcceptedCreativeClipSpec[] = [
	{ id: 'core-idle-seated', atlas: 'parsec-core', directions: 1, framesPerDirection: 4, durationsMs: [2600, 800, 120, 900], reducedMotionIndex: 0, soundCues: [] },
	{ id: 'core-idle-standing', atlas: 'parsec-core', directions: 1, framesPerDirection: 4, durationsMs: repeatedDuration(260, 4), reducedMotionIndex: 0, soundCues: [] },
	{ id: 'core-idle-sniff', atlas: 'parsec-core', directions: 1, framesPerDirection: 4, durationsMs: [180, 180, 240, 300], reducedMotionIndex: 0, soundCues: [{ frame: 1, soundId: 'rare-idle' }] },
	{ id: 'core-idle-scratch', atlas: 'parsec-core', directions: 1, framesPerDirection: 5, durationsMs: [140, 120, 120, 160, 320], reducedMotionIndex: 4, soundCues: [{ frame: 1, soundId: 'rare-idle' }] },
	{ id: 'core-idle-yawn', atlas: 'parsec-core', directions: 1, framesPerDirection: 5, durationsMs: [180, 180, 260, 220, 420], reducedMotionIndex: 4, soundCues: [{ frame: 2, soundId: 'rare-idle' }] },
	{ id: 'core-idle-pant', atlas: 'parsec-core', directions: 1, framesPerDirection: 4, durationsMs: repeatedDuration(220, 4), reducedMotionIndex: 0, soundCues: [] },
	{ id: 'core-look-cursor', atlas: 'parsec-core', directions: 1, framesPerDirection: 4, durationsMs: [180, 180, 180, 360], reducedMotionIndex: 3, soundCues: [] },
	{ id: 'core-walk-cardinal', atlas: 'parsec-core', directions: 4, framesPerDirection: 3, durationsMs: repeatedDuration(120, 12), reducedMotionIndex: 0, soundCues: [], directionNames: ['north', 'east', 'south', 'west'], defaultDirection: 'east' },
	{ id: 'core-walk-diagonal', atlas: 'parsec-core', directions: 4, framesPerDirection: 3, durationsMs: repeatedDuration(120, 12), reducedMotionIndex: 0, soundCues: [], directionNames: ['north-east', 'south-east', 'south-west', 'north-west'], defaultDirection: 'south-east' },
	{ id: 'core-return-home', atlas: 'parsec-core', directions: 1, framesPerDirection: 5, durationsMs: [120, 120, 120, 160, 260], reducedMotionIndex: 4, soundCues: [{ frame: 0, soundId: 'toy-whistle' }] },
	{ id: 'search-sniff', atlas: 'parsec-feedback', directions: 1, framesPerDirection: 5, durationsMs: [150, 150, 180, 150, 240], reducedMotionIndex: 2, soundCues: [] },
	{ id: 'fetch-dig', atlas: 'parsec-feedback', directions: 1, framesPerDirection: 6, durationsMs: repeatedDuration(110, 6), reducedMotionIndex: 0, soundCues: [] },
	{ id: 'feedback-working-focus', atlas: 'parsec-feedback', directions: 1, framesPerDirection: 4, durationsMs: repeatedDuration(220, 4), reducedMotionIndex: 0, soundCues: [] },
	{ id: 'feedback-success-wag', atlas: 'parsec-feedback', directions: 1, framesPerDirection: 5, durationsMs: [120, 100, 100, 120, 300], reducedMotionIndex: 4, soundCues: [{ frame: 2, soundId: 'voice-bark' }] },
	{ id: 'feedback-success-proud', atlas: 'parsec-feedback', directions: 1, framesPerDirection: 4, durationsMs: [160, 160, 220, 420], reducedMotionIndex: 3, soundCues: [] },
	{ id: 'feedback-warning-alert', atlas: 'parsec-feedback', directions: 1, framesPerDirection: 4, durationsMs: [120, 140, 220, 360], reducedMotionIndex: 3, soundCues: [{ frame: 1, soundId: 'radio-alert' }] },
	{ id: 'error-anxious', atlas: 'parsec-feedback', directions: 1, framesPerDirection: 5, durationsMs: [160, 180, 220, 220, 360], reducedMotionIndex: 3, soundCues: [{ frame: 1, soundId: 'voice-growl' }] },
	{ id: 'empty-confused', atlas: 'parsec-feedback', directions: 1, framesPerDirection: 4, durationsMs: [180, 220, 220, 420], reducedMotionIndex: 2, soundCues: [] },
	{ id: 'tool-growl', atlas: 'parsec-feedback', directions: 1, framesPerDirection: 5, durationsMs: [140, 140, 180, 180, 320], reducedMotionIndex: 4, soundCues: [{ frame: 2, soundId: 'voice-growl' }] },
	{ id: 'reconnect-pant', atlas: 'parsec-feedback', directions: 1, framesPerDirection: 4, durationsMs: repeatedDuration(200, 4), reducedMotionIndex: 0, soundCues: [] },
	{ id: 'touch-pat-soft', atlas: 'parsec-touch', directions: 1, framesPerDirection: 4, durationsMs: [140, 140, 180, 320], reducedMotionIndex: 3, soundCues: [] },
	{ id: 'touch-pat-delighted', atlas: 'parsec-touch', directions: 1, framesPerDirection: 5, durationsMs: [110, 110, 140, 180, 320], reducedMotionIndex: 4, soundCues: [{ frame: 2, soundId: 'voice-bark' }] },
	{ id: 'touch-nose-lick', atlas: 'parsec-touch', directions: 1, framesPerDirection: 5, durationsMs: [120, 140, 180, 160, 320], reducedMotionIndex: 4, soundCues: [] },
	{ id: 'touch-scruff-calm', atlas: 'parsec-touch', directions: 1, framesPerDirection: 4, durationsMs: repeatedDuration(180, 4), reducedMotionIndex: 0, soundCues: [] },
	{ id: 'touch-scruff-playful', atlas: 'parsec-touch', directions: 1, framesPerDirection: 5, durationsMs: repeatedDuration(130, 5), reducedMotionIndex: 0, soundCues: [{ frame: 2, soundId: 'voice-bark' }] },
	{ id: 'touch-scruff-pout', atlas: 'parsec-touch', directions: 1, framesPerDirection: 5, durationsMs: repeatedDuration(180, 5), reducedMotionIndex: 0, soundCues: [{ frame: 1, soundId: 'voice-growl' }] },
	{ id: 'touch-release-drop', atlas: 'parsec-touch', directions: 1, framesPerDirection: 4, durationsMs: [90, 110, 140, 260], reducedMotionIndex: 3, soundCues: [{ frame: 2, soundId: 'toy-handling' }] },
	{ id: 'touch-release-toss', atlas: 'parsec-touch', directions: 1, framesPerDirection: 6, durationsMs: [80, 80, 90, 100, 120, 220], reducedMotionIndex: 5, soundCues: [] },
	{ id: 'touch-landing-bounce', atlas: 'parsec-touch', directions: 1, framesPerDirection: 6, durationsMs: [70, 80, 90, 100, 140, 260], reducedMotionIndex: 5, soundCues: [{ frame: 0, soundId: 'toy-handling' }] },
	{ id: 'touch-landing-recover', atlas: 'parsec-touch', directions: 1, framesPerDirection: 4, durationsMs: [100, 120, 160, 300], reducedMotionIndex: 3, soundCues: [] },
	{ id: 'toy-ball-ready', atlas: 'parsec-toys', directions: 1, framesPerDirection: 4, durationsMs: [160, 140, 140, 320], reducedMotionIndex: 3, soundCues: [{ frame: 1, soundId: 'toy-squeak' }] },
	{ id: 'toy-ball-chase', atlas: 'parsec-toys', directions: 1, framesPerDirection: 6, durationsMs: repeatedDuration(90, 6), reducedMotionIndex: 0, soundCues: [] },
	{ id: 'toy-ball-retrieve', atlas: 'parsec-toys', directions: 1, framesPerDirection: 6, durationsMs: repeatedDuration(110, 6), reducedMotionIndex: 5, soundCues: [{ frame: 4, soundId: 'toy-squeak' }] },
	{ id: 'toy-ball-refuse', atlas: 'parsec-toys', directions: 1, framesPerDirection: 4, durationsMs: [180, 180, 220, 420], reducedMotionIndex: 3, soundCues: [] },
	{ id: 'toy-tug-grip', atlas: 'parsec-toys', directions: 1, framesPerDirection: 4, durationsMs: [130, 130, 180, 260], reducedMotionIndex: 3, soundCues: [{ frame: 0, soundId: 'toy-handling' }] },
	{ id: 'toy-tug-pull', atlas: 'parsec-toys', directions: 1, framesPerDirection: 6, durationsMs: repeatedDuration(100, 6), reducedMotionIndex: 0, soundCues: [] },
	{ id: 'toy-tug-win', atlas: 'parsec-toys', directions: 1, framesPerDirection: 5, durationsMs: [90, 100, 120, 180, 320], reducedMotionIndex: 4, soundCues: [{ frame: 2, soundId: 'voice-bark' }] },
	{ id: 'toy-tug-tumble', atlas: 'parsec-toys', directions: 1, framesPerDirection: 5, durationsMs: [80, 90, 100, 160, 320], reducedMotionIndex: 4, soundCues: [{ frame: 2, soundId: 'toy-handling' }] },
	{ id: 'toy-brush-content', atlas: 'parsec-toys', directions: 1, framesPerDirection: 5, durationsMs: repeatedDuration(160, 5), reducedMotionIndex: 0, soundCues: [{ frame: 1, soundId: 'toy-brush' }] },
	{ id: 'toy-brush-impatient', atlas: 'parsec-toys', directions: 1, framesPerDirection: 4, durationsMs: [140, 180, 220, 360], reducedMotionIndex: 3, soundCues: [{ frame: 1, soundId: 'voice-growl' }] },
	{ id: 'toy-treat-accept', atlas: 'parsec-toys', directions: 1, framesPerDirection: 5, durationsMs: [110, 120, 140, 180, 320], reducedMotionIndex: 4, soundCues: [] },
	{ id: 'toy-whistle-recall', atlas: 'parsec-toys', directions: 1, framesPerDirection: 5, durationsMs: [100, 120, 140, 180, 280], reducedMotionIndex: 4, soundCues: [{ frame: 0, soundId: 'toy-whistle' }] },
	{ id: 'habitat-bed-approach', atlas: 'parsec-habitat', directions: 1, framesPerDirection: 4, durationsMs: [120, 120, 160, 260], reducedMotionIndex: 3, soundCues: [] },
	{ id: 'habitat-bed-lie-down', atlas: 'parsec-habitat', directions: 1, framesPerDirection: 5, durationsMs: [120, 140, 160, 200, 360], reducedMotionIndex: 4, soundCues: [{ frame: 2, soundId: 'toy-handling' }] },
	{ id: 'habitat-bed-sleep', atlas: 'parsec-habitat', directions: 1, framesPerDirection: 5, durationsMs: [360, 360, 180, 360, 520], reducedMotionIndex: 0, soundCues: [{ frame: 2, soundId: 'rare-idle' }] },
	{ id: 'habitat-bed-timeout-pout', atlas: 'parsec-habitat', directions: 1, framesPerDirection: 4, durationsMs: repeatedDuration(260, 4), reducedMotionIndex: 0, soundCues: [{ frame: 1, soundId: 'voice-growl' }] },
	{ id: 'habitat-cage-enter', atlas: 'parsec-habitat', directions: 1, framesPerDirection: 5, durationsMs: [110, 120, 140, 180, 300], reducedMotionIndex: 4, soundCues: [{ frame: 3, soundId: 'toy-handling' }] },
	{ id: 'habitat-cage-open-idle', atlas: 'parsec-habitat', directions: 1, framesPerDirection: 4, durationsMs: repeatedDuration(280, 4), reducedMotionIndex: 0, soundCues: [] },
	{ id: 'habitat-cage-latched-pout', atlas: 'parsec-habitat', directions: 1, framesPerDirection: 5, durationsMs: repeatedDuration(220, 5), reducedMotionIndex: 0, soundCues: [{ frame: 2, soundId: 'voice-growl' }] },
	{ id: 'habitat-cage-release', atlas: 'parsec-habitat', directions: 1, framesPerDirection: 5, durationsMs: [110, 120, 140, 180, 300], reducedMotionIndex: 4, soundCues: [{ frame: 2, soundId: 'voice-bark' }] },
	{ id: 'intrusive-cursor-stalk', atlas: 'parsec-intrusive', directions: 1, framesPerDirection: 5, durationsMs: repeatedDuration(120, 5), reducedMotionIndex: 0, soundCues: [] },
	{ id: 'intrusive-cursor-pounce', atlas: 'parsec-intrusive', directions: 1, framesPerDirection: 6, durationsMs: [80, 80, 90, 100, 140, 260], reducedMotionIndex: 5, soundCues: [{ frame: 2, soundId: 'voice-bark' }] },
	{ id: 'intrusive-loiter', atlas: 'parsec-intrusive', directions: 1, framesPerDirection: 4, durationsMs: repeatedDuration(300, 4), reducedMotionIndex: 0, soundCues: [] },
	{ id: 'intrusive-demand-attention', atlas: 'parsec-intrusive', directions: 1, framesPerDirection: 5, durationsMs: [130, 130, 160, 220, 360], reducedMotionIndex: 4, soundCues: [{ frame: 1, soundId: 'voice-bark' }] },
	{ id: 'intrusive-zoomies', atlas: 'parsec-intrusive', directions: 1, framesPerDirection: 7, durationsMs: repeatedDuration(80, 7), reducedMotionIndex: 0, soundCues: [{ frame: 0, soundId: 'rare-idle' }] },
	{ id: 'effect-hearts', atlas: 'parsec-effects', directions: 1, framesPerDirection: 3, durationsMs: [140, 180, 300], reducedMotionIndex: 2, soundCues: [] },
	{ id: 'effect-station-alert', atlas: 'parsec-effects', directions: 1, framesPerDirection: 3, durationsMs: [120, 180, 360], reducedMotionIndex: 2, soundCues: [{ frame: 0, soundId: 'radio-alert' }] },
	{ id: 'effect-scent-trail', atlas: 'parsec-effects', directions: 1, framesPerDirection: 4, durationsMs: repeatedDuration(160, 4), reducedMotionIndex: 0, soundCues: [] },
	{ id: 'effect-radio-ping', atlas: 'parsec-effects', directions: 1, framesPerDirection: 3, durationsMs: [120, 160, 320], reducedMotionIndex: 2, soundCues: [{ frame: 0, soundId: 'radio-alert' }] },
	{ id: 'effect-dust-landing', atlas: 'parsec-effects', directions: 1, framesPerDirection: 4, durationsMs: [80, 100, 140, 260], reducedMotionIndex: 3, soundCues: [{ frame: 0, soundId: 'toy-handling' }] },
];

const creativeClips = Object.fromEntries(creativeClipSpecs.map((spec) => {
	const fallback = baseClips[spec.fallback];
	return [spec.id, {
		...fallback,
		id: spec.id,
		atlas: spec.atlas,
		loopMode: spec.loopMode,
		requiredAnchors: spec.requiredAnchors,
		requiredForCreativeSprint: true,
		plannedUniqueFrames: spec.plannedUniqueFrames,
		creativeStatus: 'fallback' as const,
		fallback: spec.fallback,
	}];
}));

const creativeSpecsById = Object.fromEntries(creativeClipSpecs.map((spec) => [spec.id, spec]));

type ProductionVisualReview = {
	status: 'accepted' | 'coherent-reuse';
	reason: string;
	target?: string;
};

const productionVisualReviews = visualReviewInventory.clips as Record<string, ProductionVisualReview>;
const acceptedCreativeClips = Object.fromEntries(acceptedCreativeClipSpecs.map((acceptedSpec) => {
	const spec = creativeSpecsById[acceptedSpec.id]!;
	const frameIds = acceptedFrameIds(acceptedSpec);
	const directional = acceptedSpec.defaultDirection ? {
		directionVariants: directionVariants(acceptedSpec, frameIds),
		defaultDirection: acceptedSpec.defaultDirection,
	} : {};
	return [acceptedSpec.id, {
		id: acceptedSpec.id,
		atlas: acceptedSpec.atlas,
		frames: frameIds,
		durationsMs: acceptedSpec.durationsMs,
		loopMode: spec.loopMode,
		interruptible: true,
		reducedMotionFrame: frameIds[acceptedSpec.reducedMotionIndex]!,
		requiredAnchors: spec.requiredAnchors,
		requiredForCreativeSprint: true,
		plannedUniqueFrames: spec.plannedUniqueFrames,
		creativeStatus: 'accepted' as const,
		visualReview: productionVisualReviews[acceptedSpec.id]!,
		soundCues: acceptedSpec.soundCues,
		fallback: spec.fallback,
		...directional,
	} satisfies ParsecAnimationClip];
}));
const coherentReuseCreativeClips = Object.fromEntries(Object.entries(productionVisualReviews).flatMap(([id, review]) => {
	if (review.status !== 'coherent-reuse' || !review.target) return [];
	const target = acceptedCreativeClips[review.target] as ParsecAnimationClip | undefined;
	const spec = creativeSpecsById[id];
	if (!target || !spec) return [];
	return [[id, {
		...target,
		id,
		loopMode: spec.loopMode,
		soundCues: acceptedCreativeClips[id]!.soundCues,
		requiredAnchors: spec.requiredAnchors,
		requiredForCreativeSprint: true,
		creativeStatus: 'coherent-reuse' as const,
		visualReview: review,
		fallback: review.target,
	} satisfies ParsecAnimationClip]];
}));

export const coreFallbackManifest: ParsecAssetManifest = {
	schemaVersion: 1,
	logicalCanvas: { width: 96, height: 96 },
	identityPalette: {
		leftEye: '#FBD436',
		rightEye: '#FF3CC8',
		laterality: 'anatomical',
	},
	provenance: {
		'core-husky': {
			id: 'core-husky',
			source: 'https://opengameart.org/content/husky-sprites',
			license: 'CC0-1.0',
			author: null,
			adaptation: 'Historical character reference; the current fallback is derived from regenerated core artwork.',
		},
		'parsec-generated-core': {
			id: 'parsec-generated-core',
			source: 'references/parsec-asset-register.md#parsec-core-max-production',
			license: 'Project-owned generated asset',
			author: 'OpenAI ImageGen with project-directed review',
			adaptation: 'Shared character reference, 512px HD frames, PortalRabbit Grid Artist conversion, identity-preserving runtime preparation, and deterministic atlas packing. Includes the compact fallback sheet.',
		},
		'parsec-generated-feedback': {
			id: 'parsec-generated-feedback',
			source: 'references/parsec-asset-register.md#parsec-feedback-max-production',
			license: 'Project-owned generated asset',
			author: 'OpenAI ImageGen with project-directed review',
			adaptation: 'Shared character reference, 512px HD frames, PortalRabbit Grid Artist conversion, identity-preserving runtime preparation, and deterministic atlas packing.',
		},
		'parsec-generated-touch': {
			id: 'parsec-generated-touch',
			source: 'references/parsec-asset-register.md#parsec-touch-max-production',
			license: 'Project-owned generated asset',
			author: 'OpenAI ImageGen with project-directed review',
			adaptation: 'Shared character reference, 512px HD frames, PortalRabbit Grid Artist conversion, identity-preserving runtime preparation, and deterministic atlas packing.',
		},
		'parsec-generated-toys': {
			id: 'parsec-generated-toys',
			source: 'references/parsec-asset-register.md#parsec-toys-max-production',
			license: 'Project-owned generated asset',
			author: 'OpenAI ImageGen with project-directed review',
			adaptation: 'Shared character reference, 512px HD frames, PortalRabbit Grid Artist conversion, identity-preserving runtime preparation, and deterministic atlas packing. SS13 toy objects remain separate anchor-attached assets.',
		},
		'parsec-generated-habitat': {
			id: 'parsec-generated-habitat',
			source: 'references/parsec-asset-register.md#parsec-habitat-max-production',
			license: 'Project-owned generated asset',
			author: 'OpenAI ImageGen with project-directed review',
			adaptation: 'Actor-only bed and cage motion regenerated from the shared character reference, converted with PortalRabbit Grid Artist, and deterministically packed. SS13 furniture remains separate anchor-attached art.',
		},
		'parsec-generated-intrusive': {
			id: 'parsec-generated-intrusive',
			source: 'references/parsec-asset-register.md#parsec-intrusive-max-production',
			license: 'Project-owned generated asset',
			author: 'OpenAI ImageGen with project-directed review',
			adaptation: 'Actor-only cursor stalking, pounce, loiter, attention, and zoomies regenerated from the shared character reference, converted with PortalRabbit Grid Artist, and deterministically packed.',
		},
		'parsec-effects-production': {
			id: 'parsec-effects-production',
			source: 'references/parsec-asset-register.md#parsec-effects-production',
			license: 'Mixed: CC-BY-SA-3.0 repository assets and project-owned derived frames',
			author: null,
			adaptation: 'HD reinterpretations of the registered heart, telegraph, sonar, scent, and dust motifs, converted with PortalRabbit Grid Artist and fitted to their existing runtime envelopes.',
		},
		'ss13-rift-objects': {
			id: 'ss13-rift-objects',
			source: 'references/parsec-asset-register.md#ss13-object-production',
			license: 'CC-BY-SA-3.0 unless a registered source states otherwise',
			author: null,
			adaptation: 'Exact DMI frames extracted from Meridian-Rift revision df0fb67eae69497be39e1dfc7f618f3d7964d3d5, centered without resampling on transparent 96x96 cells, and deterministically packed.',
		},
		'ss13-rift-audio': {
			id: 'ss13-rift-audio',
			source: 'references/parsec-asset-register.md#parsec-audio-production',
			license: 'Mixed registered SS13 and Nova source licenses',
			author: null,
			adaptation: 'Exact-copy OGG runtime pack from registered Meridian-Rift sources; no trim, gain, layering, or transcoding.',
		},
	},
	sheets: {
		core: {
			id: 'core',
			src: spriteUrl,
			width: 432,
			height: 204,
			frameWidth: CELL_WIDTH,
			frameHeight: CELL_HEIGHT,
			provenanceId: 'parsec-generated-core',
		},
		'parsec-core': {
			id: 'parsec-core',
			src: coreAtlasUrl,
			width: 768,
			height: 768,
			frameWidth: 96,
			frameHeight: 96,
			provenanceId: 'parsec-generated-core',
		},
		'parsec-feedback': {
			id: 'parsec-feedback',
			src: feedbackAtlasUrl,
			width: 672,
			height: 672,
			frameWidth: 96,
			frameHeight: 96,
			provenanceId: 'parsec-generated-feedback',
		},
		'parsec-touch': {
			id: 'parsec-touch',
			src: touchAtlasUrl,
			width: 672,
			height: 672,
			frameWidth: 96,
			frameHeight: 96,
			provenanceId: 'parsec-generated-touch',
		},
		'parsec-toys': {
			id: 'parsec-toys',
			src: toyAtlasUrl,
			width: 768,
			height: 768,
			frameWidth: 96,
			frameHeight: 96,
			provenanceId: 'parsec-generated-toys',
		},
		'parsec-habitat': {
			id: 'parsec-habitat',
			src: habitatAtlasUrl,
			width: 672,
			height: 576,
			frameWidth: 96,
			frameHeight: 96,
			provenanceId: 'parsec-generated-habitat',
		},
		'parsec-intrusive': {
			id: 'parsec-intrusive',
			src: intrusiveAtlasUrl,
			width: 576,
			height: 480,
			frameWidth: 96,
			frameHeight: 96,
			provenanceId: 'parsec-generated-intrusive',
		},
		'parsec-effects': {
			id: 'parsec-effects',
			src: effectsAtlasUrl,
			width: 480,
			height: 384,
			frameWidth: 96,
			frameHeight: 96,
			provenanceId: 'parsec-effects-production',
		},
		'ss13-objects': {
			id: 'ss13-objects',
			src: ss13ObjectAtlasUrl,
			width: 384,
			height: 288,
			frameWidth: 96,
			frameHeight: 96,
			provenanceId: 'ss13-rift-objects',
		},
	},
	frames: {
		...frames,
		...productionFrames,
		...ss13ObjectFrames,
	},
	clips: {
		...baseClips,
		...creativeClips,
		...acceptedCreativeClips,
		...coherentReuseCreativeClips,
	},
	aliases: {
		search: 'search-sniff',
		fetch: 'fetch-dig',
		anxious: 'error-anxious',
		confused: 'empty-confused',
		growl: 'tool-growl',
		pant: 'reconnect-pant',
	},
	legacyStates: {
		idle: 'seated-idle',
		working: 'working-patrol',
		happy: 'happy-reaction',
		twerking: 'twerking-reaction',
	},
	defaultClip: 'seated-idle',
	objects: Object.fromEntries([
		['dogbed', 'ss13-dogbed', 'BED', 'ss13-objects/dogbed/d0/f0', 'ss13-rift-objects'],
		['cage-open', 'ss13-carrier-open', 'OPEN CAGE', 'ss13-objects/cage-open/d0/f0', 'ss13-rift-objects'],
		['cage-closed', 'ss13-carrier-closed', 'CLOSED CAGE', 'ss13-objects/cage-closed/d0/f0', 'ss13-rift-objects'],
		['cage-locked', 'ss13-carrier-locked', 'LATCHED CAGE', 'ss13-objects/cage-locked/d0/f0', 'ss13-rift-objects'],
		['cage-occupied', 'ss13-carrier-occupied', 'OCCUPIED CAGE', 'ss13-objects/cage-occupied/d0/f0', 'ss13-rift-objects'],
		['tennis-ball', 'ss13-tennis-ball', 'BALL', 'ss13-objects/tennis-ball/d0/f0', 'ss13-rift-objects'],
		['hairbrush', 'ss13-hairbrush', 'BRUSH', 'ss13-objects/hairbrush/d0/f0', 'ss13-rift-objects'],
		['toy-mouse', 'ss13-toy-mouse', 'TOY MOUSE', 'ss13-objects/toy-mouse/d0/f0', 'ss13-rift-objects'],
		['carp-plush', 'ss13-carp-plush', 'CARP PLUSH', 'ss13-objects/carp-plush/d0/f0', 'ss13-rift-objects'],
		['toolbox', 'ss13-toolbox', 'TOOLBOX', 'ss13-objects/toolbox/d0/f0', 'ss13-rift-objects'],
		['tug-rope', 'ss13-tug-rope', 'TUG', 'ss13-objects/tug-rope/d0/f0', 'ss13-rift-objects'],
	].map(([id, sourceRegisterId, fallbackLabel, frameId, provenanceId]) => [id, {
		id,
		frameId,
		provenanceId,
		sourceRegisterId,
		requiredForCreativeSprint: true,
		fallbackLabel,
	}])),
	sounds: Object.fromEntries([
		['voice-bark', 'voice', 'audio-bark-1', voiceBarkUrl, 0.75, 2_000],
		['voice-growl', 'voice', 'audio-dog-growl-1', voiceGrowlUrl, 0.6, 2_500],
		['toy-squeak', 'toys', 'audio-squeak-1', toySqueakUrl, 0.55, 900],
		['toy-brush', 'toys', 'audio-brush-soft', toyBrushUrl, 0.35, 1_500],
		['toy-whistle', 'toys', 'audio-whistle', toyWhistleUrl, 0.5, 3_000],
		['toy-handling', 'toys', 'audio-toolbox-pickup', toyHandlingUrl, 0.35, 600],
		['radio-alert', 'radio', 'audio-radio-receive', radioAlertUrl, 0.45, 800],
		['rare-idle', 'rare-idle', 'audio-dog-growl-long-1', rareIdleUrl, 0.35, 45_000],
	].map(([id, channel, sourceRegisterId, src, authoredVolume, cooldownMs]) => [id, {
		id,
		src,
		provenanceId: 'ss13-rift-audio',
		sourceRegisterId,
		requiredForCreativeSprint: true,
		channel,
		authoredVolume,
		cooldownMs,
		fallback: 'silent',
	}])) as ParsecAssetManifest['sounds'],
};

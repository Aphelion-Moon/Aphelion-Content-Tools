export interface ParsecAssetProvenance {
	id: string;
	source: string;
	license: string;
	author: string | null;
	adaptation: string;
}

export interface ParsecSpriteSheet {
	id: string;
	src: string;
	width: number;
	height: number;
	frameWidth: number;
	frameHeight: number;
	provenanceId: string;
}

export interface ParsecAnchor {
	x: number;
	y: number;
}

export interface ParsecSpriteFrame {
	id: string;
	sheetId: string;
	x: number;
	y: number;
	width: number;
	height: number;
	anchors: Record<string, ParsecAnchor>;
}

export type ParsecLoopMode = 'loop' | 'once' | 'hold';

export interface ParsecSoundCue {
	frame: number;
	soundId: string;
}

export interface ParsecDirectionVariant {
	frames: string[];
	durationsMs: number[];
	reducedMotionFrame: string;
}

export interface ParsecAnimationClip {
	id: string;
	atlas: string;
	frames: string[];
	durationsMs: number[];
	loopMode: ParsecLoopMode;
	interruptible: boolean;
	reducedMotionFrame: string;
	requiredAnchors: string[];
	requiredForCreativeSprint: boolean;
	plannedUniqueFrames: number;
	creativeStatus: 'fallback' | 'accepted' | 'coherent-reuse' | 'deferred-human' | 'fallback-approved';
	visualReview?: {
		status: 'accepted' | 'coherent-reuse';
		reason: string;
		target?: string;
	};
	soundCues: ParsecSoundCue[];
	fallback: string | null;
	directionVariants?: Record<string, ParsecDirectionVariant>;
	defaultDirection?: string;
}

export interface ParsecHabitatObjectAsset {
	id: string;
	frameId: string | null;
	provenanceId: string | null;
	sourceRegisterId: string | null;
	requiredForCreativeSprint: boolean;
	fallbackLabel: string;
}

export interface ParsecSoundAsset {
	id: string;
	src: string | null;
	provenanceId: string | null;
	sourceRegisterId: string | null;
	requiredForCreativeSprint: boolean;
	channel: 'voice' | 'toys' | 'radio' | 'rare-idle';
	authoredVolume: number;
	cooldownMs: number;
	fallback: 'silent';
}

export interface ParsecAssetManifest {
	schemaVersion: 1;
	logicalCanvas: { width: number; height: number };
	identityPalette: {
		leftEye: string;
		rightEye: string;
		laterality: 'anatomical';
	};
	provenance: Record<string, ParsecAssetProvenance>;
	sheets: Record<string, ParsecSpriteSheet>;
	frames: Record<string, ParsecSpriteFrame>;
	clips: Record<string, ParsecAnimationClip>;
	aliases: Record<string, string>;
	legacyStates: Record<string, string>;
	defaultClip: string;
	objects: Record<string, ParsecHabitatObjectAsset>;
	sounds: Record<string, ParsecSoundAsset>;
}

function hasClipOrAlias(id: string, manifest: ParsecAssetManifest): boolean {
	return id in manifest.clips || id in manifest.aliases;
}

function aliasHasCycle(start: string, manifest: ParsecAssetManifest): boolean {
	const visited = new Set<string>();
	let current: string | undefined = start;
	while (current !== undefined && current in manifest.aliases) {
		if (visited.has(current)) return true;
		visited.add(current);
		current = manifest.aliases[current];
	}
	return false;
}

/** Return authoring errors without throwing so a broken optional pack can fall back safely. */
export function validateParsecManifest(manifest: ParsecAssetManifest): string[] {
	const errors: string[] = [];
	if (manifest.logicalCanvas.width <= 0) errors.push('logicalCanvas.width must be positive');
	if (manifest.logicalCanvas.height <= 0) errors.push('logicalCanvas.height must be positive');
	if (!/^#[0-9A-F]{6}$/.test(manifest.identityPalette.leftEye)) errors.push('identityPalette.leftEye must be an uppercase hex color');
	if (!/^#[0-9A-F]{6}$/.test(manifest.identityPalette.rightEye)) errors.push('identityPalette.rightEye must be an uppercase hex color');

	for (const [sheetId, sheet] of Object.entries(manifest.sheets)) {
		if (sheet.width <= 0 || sheet.height <= 0) errors.push(`sheets.${sheetId} dimensions must be positive`);
		if (!(sheet.provenanceId in manifest.provenance)) {
			errors.push(`sheets.${sheetId}.provenanceId references ${sheet.provenanceId}`);
		}
	}

	for (const [frameId, frame] of Object.entries(manifest.frames)) {
		const sheet = manifest.sheets[frame.sheetId];
		if (!sheet) {
			errors.push(`frames.${frameId}.sheetId references ${frame.sheetId}`);
			continue;
		}
		if (frame.x < 0 || frame.width <= 0 || frame.x + frame.width > sheet.width) {
			errors.push(`frames.${frameId} extends beyond sheets.${frame.sheetId} width`);
		}
		if (frame.y < 0 || frame.height <= 0 || frame.y + frame.height > sheet.height) {
			errors.push(`frames.${frameId} extends beyond sheets.${frame.sheetId} height`);
		}
	}

	for (const [clipId, clip] of Object.entries(manifest.clips)) {
		if (clip.frames.length === 0) errors.push(`clips.${clipId}.frames must contain at least one frame`);
		if (clip.durationsMs.length !== clip.frames.length) {
			errors.push(`clips.${clipId}.durationsMs must match its frame count`);
		}
		for (const frameId of clip.frames) {
			if (!(frameId in manifest.frames)) errors.push(`clips.${clipId}.frames references ${frameId}`);
		}
		if (!clip.frames.includes(clip.reducedMotionFrame)) {
			errors.push(`clips.${clipId}.reducedMotionFrame must reference one of its frames`);
		}
		if (clip.durationsMs.some((duration) => duration <= 0)) {
			errors.push(`clips.${clipId}.durationsMs must be positive`);
		}
		if (clip.directionVariants && (!clip.defaultDirection || !(clip.defaultDirection in clip.directionVariants))) {
			errors.push(`clips.${clipId}.defaultDirection references ${clip.defaultDirection ?? 'nothing'}`);
		}
		if (!clip.directionVariants && clip.defaultDirection) {
			errors.push(`clips.${clipId}.defaultDirection requires directionVariants`);
		}
		for (const [direction, variant] of Object.entries(clip.directionVariants ?? {})) {
			if (variant.frames.length === 0) errors.push(`clips.${clipId}.directionVariants.${direction} must contain at least one frame`);
			if (variant.durationsMs.length !== variant.frames.length) {
				errors.push(`clips.${clipId}.directionVariants.${direction} durations must match its frame count`);
			}
			if (!variant.frames.includes(variant.reducedMotionFrame)) {
				errors.push(`clips.${clipId}.directionVariants.${direction} reduced-motion frame must belong to the variant`);
			}
			if (variant.frames.some((frameId) => !clip.frames.includes(frameId))) {
				errors.push(`clips.${clipId}.directionVariants.${direction} must use frames from the clip`);
			}
			if (variant.durationsMs.some((duration) => duration <= 0)) {
				errors.push(`clips.${clipId}.directionVariants.${direction} durations must be positive`);
			}
		}
		if (clip.fallback !== null && !hasClipOrAlias(clip.fallback, manifest)) {
			errors.push(`clips.${clipId}.fallback references ${clip.fallback}`);
		}
		if (clip.requiredForCreativeSprint && clip.fallback === null && clip.creativeStatus === 'fallback') {
			errors.push(`clips.${clipId} requires an explicit fallback`);
		}
		if (clip.plannedUniqueFrames <= 0) errors.push(`clips.${clipId}.plannedUniqueFrames must be positive`);
		for (const frameId of clip.frames) {
			const frame = manifest.frames[frameId];
			if (!frame) continue;
			for (const anchor of clip.requiredAnchors) {
				if (!(anchor in frame.anchors)) errors.push(`clips.${clipId} requires ${anchor} on ${frameId}`);
			}
		}
		for (const cue of clip.soundCues) {
			if (cue.frame < 0 || cue.frame >= clip.frames.length) errors.push(`clips.${clipId}.soundCues has an invalid frame`);
			if (!(cue.soundId in manifest.sounds)) errors.push(`clips.${clipId}.soundCues references ${cue.soundId}`);
		}
	}

	for (const [objectId, object] of Object.entries(manifest.objects)) {
		if (object.frameId !== null && !(object.frameId in manifest.frames)) {
			errors.push(`objects.${objectId}.frameId references ${object.frameId}`);
		}
		if (object.provenanceId !== null && !(object.provenanceId in manifest.provenance)) {
			errors.push(`objects.${objectId}.provenanceId references ${object.provenanceId}`);
		}
		if (object.requiredForCreativeSprint && object.frameId === null && !object.fallbackLabel) {
			errors.push(`objects.${objectId} requires a fallback label`);
		}
	}

	for (const [soundId, sound] of Object.entries(manifest.sounds)) {
		if (sound.provenanceId !== null && !(sound.provenanceId in manifest.provenance)) {
			errors.push(`sounds.${soundId}.provenanceId references ${sound.provenanceId}`);
		}
	}

	for (const [aliasId, target] of Object.entries(manifest.aliases)) {
		if (!hasClipOrAlias(target, manifest)) errors.push(`aliases.${aliasId} references ${target}`);
		if (aliasHasCycle(aliasId, manifest)) errors.push(`aliases.${aliasId} contains a fallback cycle`);
	}

	if (!(manifest.defaultClip in manifest.clips)) errors.push(`defaultClip references ${manifest.defaultClip}`);
	return errors;
}

/** Resolve an authored name through aliases, always returning the manifest's safe default clip. */
export function resolveClip(requestedId: string, manifest: ParsecAssetManifest): ParsecAnimationClip {
	const visited = new Set<string>();
	let current = requestedId;
	while (current in manifest.aliases && !visited.has(current)) {
		visited.add(current);
		current = manifest.aliases[current]!;
	}
	return manifest.clips[current] ?? manifest.clips[manifest.defaultClip]!;
}

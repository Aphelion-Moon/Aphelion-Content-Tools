const EFFECTS_BY_COMPANION_CLIP: Readonly<Record<string, string>> = {
	'feedback-working-focus': 'effect-radio-ping',
	'feedback-success-wag': 'effect-hearts',
	'feedback-success-proud': 'effect-hearts',
	'feedback-warning-alert': 'effect-station-alert',
	'error-anxious': 'effect-station-alert',
	'tool-growl': 'effect-station-alert',
	'search-sniff': 'effect-scent-trail',
	'fetch-dig': 'effect-scent-trail',
	'touch-pat-delighted': 'effect-hearts',
	'intrusive-demand-attention': 'effect-hearts',
	'touch-release-drop': 'effect-dust-landing',
	'touch-release-toss': 'effect-dust-landing',
	'touch-landing-bounce': 'effect-dust-landing',
	'touch-landing-recover': 'effect-dust-landing',
	'intrusive-cursor-pounce': 'effect-dust-landing',
	'intrusive-zoomies': 'effect-dust-landing',
};

const ACTOR_ALIGNED_EFFECTS = new Set(['effect-scent-trail', 'effect-dust-landing']);

export function effectForCompanionClip(clipId: string): string | null {
	return EFFECTS_BY_COMPANION_CLIP[clipId] ?? null;
}

export function isActorAlignedEffect(effectClipId: string): boolean {
	return ACTOR_ALIGNED_EFFECTS.has(effectClipId);
}

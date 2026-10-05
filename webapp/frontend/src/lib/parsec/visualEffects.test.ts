import { describe, expect, it } from 'vitest';
import { effectForCompanionClip } from './visualEffects';

describe('Parsec companion visual effects', () => {
	it('maps feedback, affection, search, and landing clips to noninteractive overlays', () => {
		expect(effectForCompanionClip('feedback-working-focus')).toBe('effect-radio-ping');
		expect(effectForCompanionClip('feedback-warning-alert')).toBe('effect-station-alert');
		expect(effectForCompanionClip('touch-pat-delighted')).toBe('effect-hearts');
		expect(effectForCompanionClip('search-sniff')).toBe('effect-scent-trail');
		expect(effectForCompanionClip('touch-landing-bounce')).toBe('effect-dust-landing');
		expect(effectForCompanionClip('core-idle-seated')).toBeNull();
	});
});

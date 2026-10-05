import { afterEach, describe, expect, it } from 'vitest';
import { appState } from '~/store/appStore';
import { dismissParsec } from './parsec/coordinator';
import { announceError, announceSuccess } from './notify';

afterEach(() => dismissParsec());

describe('Parsec notification compatibility helpers', () => {
	it('turns success into playful feedback through the coordinator', () => {
		announceSuccess('Catalog refresh finished.', 'file-management');

		expect(appState.parsecFeedback?.kind).toBe('success');
		expect(appState.parsecFeedback?.text).toContain('*wags her tail excitedly!*');
		expect(appState.parsecFeedback?.text).toContain('Catalog refresh finished.');
	});

	it('retains an exact error separately from the playful line', () => {
		announceError(new Error('HTTP 500: catalog refresh failed'), 'file-management');

		expect(appState.parsecFeedback?.kind).toBe('error');
		expect(appState.parsecFeedback?.text).toContain('*growls in frustration.*');
		expect(appState.announcements[0]?.technicalDetail).toBe('HTTP 500: catalog refresh failed');
	});
});

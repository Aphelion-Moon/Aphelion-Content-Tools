import { afterEach, describe, expect, it, vi } from 'vitest';
import { readReviewerIdentity, writeReviewerIdentity } from './reviewerIdentity';

afterEach(() => {
	vi.restoreAllMocks();
	window.localStorage.clear();
});

describe('Lore reviewer identity', () => {
	it('stores a trimmed reviewer and removes an empty identity', () => {
		writeReviewerIdentity('  Zoe  ');
		expect(window.localStorage.getItem('aphelion-lore-reviewer')).toBe('Zoe');
		expect(readReviewerIdentity()).toBe('Zoe');

		writeReviewerIdentity('   ');
		expect(window.localStorage.getItem('aphelion-lore-reviewer')).toBeNull();
		expect(readReviewerIdentity()).toBe('');
	});

	it('keeps the in-memory workflow usable when browser storage is unavailable', () => {
		vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
			throw new Error('storage disabled');
		});
		expect(readReviewerIdentity()).toBe('');

		vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
			throw new Error('storage disabled');
		});
		expect(() => writeReviewerIdentity('Zoe')).not.toThrow();
	});
});

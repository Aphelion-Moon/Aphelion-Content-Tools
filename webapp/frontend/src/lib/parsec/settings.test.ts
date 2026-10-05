import { afterEach, describe, expect, it, vi } from 'vitest';
import {
	readActivityRetention,
	readIdleChatterPreference,
	readParsecLogMode,
	writeActivityRetention,
	writeIdleChatterPreference,
	writeParsecLogMode,
} from './settings';

afterEach(() => {
	vi.restoreAllMocks();
	window.localStorage.clear();
});

describe('Parsec idle chatter preference', () => {
	it('defaults to rare and persists every supported preference', () => {
		expect(readIdleChatterPreference()).toBe('rare');
		for (const preference of ['off', 'rare', 'occasional', 'frequent'] as const) {
			writeIdleChatterPreference(preference);
			expect(readIdleChatterPreference()).toBe(preference);
		}
	});

	it('falls back to rare for invalid or inaccessible storage', () => {
		window.localStorage.setItem('aphelion-parsec-idle-chatter', 'constantly');
		expect(readIdleChatterPreference()).toBe('rare');

		vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
			throw new Error('storage disabled');
		});
		expect(readIdleChatterPreference()).toBe('rare');
	});

	it('does not surface storage write failures as recursive feedback', () => {
		vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
			throw new Error('storage disabled');
		});
		expect(() => writeIdleChatterPreference('frequent')).not.toThrow();
	});
});

describe('Parsec log and retention preferences', () => {
	it('defaults to the compact live log and 90-day activity retention', () => {
		expect(readParsecLogMode()).toBe('compact');
		expect(readActivityRetention()).toBe(90);
	});

	it('persists every supported presentation and retention choice', () => {
		for (const mode of ['compact', 'collapsed', 'expanded'] as const) {
			writeParsecLogMode(mode);
			expect(readParsecLogMode()).toBe(mode);
		}
		for (const retention of [7, 30, 90, 365, 'manual'] as const) {
			writeActivityRetention(retention);
			expect(readActivityRetention()).toBe(retention);
		}
	});

	it('restores approved defaults after invalid stored values', () => {
		window.localStorage.setItem('aphelion-parsec-log-mode', 'balloon');
		window.localStorage.setItem('aphelion-parsec-activity-retention', 'forever');
		expect(readParsecLogMode()).toBe('compact');
		expect(readActivityRetention()).toBe(90);
	});
});

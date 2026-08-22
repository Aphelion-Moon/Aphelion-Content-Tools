import { describe, expect, it } from 'vitest';
import { escapeHtml, formatBytes, formatElapsed } from './format';

describe('formatBytes', () => {
	it('renders zero without a unit jump', () => {
		expect(formatBytes(0)).toBe('0 B');
	});

	it('renders whole bytes without a decimal', () => {
		expect(formatBytes(512)).toBe('512 B');
	});

	it('steps up through units at 1024 boundaries', () => {
		expect(formatBytes(1024)).toBe('1.0 KB');
		expect(formatBytes(1024 * 1024)).toBe('1.0 MB');
		expect(formatBytes(1024 * 1024 * 1024)).toBe('1.0 GB');
	});

	it('stops at GB rather than inventing a larger unit', () => {
		expect(formatBytes(1024 ** 4)).toBe('1024.0 GB');
	});
});

describe('formatElapsed', () => {
	const now = () => Date.now() / 1000;

	it('renders seconds under a minute', () => {
		expect(formatElapsed(now() - 5)).toBe('5s');
	});

	it('renders minutes and seconds past a minute', () => {
		expect(formatElapsed(now() - 125)).toBe('2m 5s');
	});

	it('renders hours and minutes past an hour', () => {
		expect(formatElapsed(now() - 3720)).toBe('1h 2m');
	});

	it('clamps a future timestamp to zero rather than going negative', () => {
		expect(formatElapsed(now() + 60)).toBe('0s');
	});
});

describe('escapeHtml', () => {
	it('escapes every character that could break out of an attribute or element', () => {
		expect(escapeHtml(`<img src="x" onerror='alert(1)'>&`)).toBe(
			'&lt;img src=&quot;x&quot; onerror=&#39;alert(1)&#39;&gt;&amp;',
		);
	});

	it('escapes ampersands first so entities are not double-encoded into nonsense', () => {
		expect(escapeHtml('&lt;')).toBe('&amp;lt;');
	});
});

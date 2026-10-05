import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

describe('global control sizing', () => {
	it('keeps form fields full width without stretching every button', () => {
		const stylesheet = readFileSync('src/app.css', 'utf8');

		expect(stylesheet).toMatch(/input,\s*textarea,\s*select\s*\{[^}]*width:\s*100%/s);
		expect(stylesheet).toMatch(/button\s*\{[^}]*width:\s*auto/s);
	});
});

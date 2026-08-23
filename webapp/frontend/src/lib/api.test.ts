import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, requestJson } from './api';

afterEach(() => vi.unstubAllGlobals());

describe('requestJson error details', () => {
	it('preserves typed conflict fields for side-by-side resolution', async () => {
		vi.stubGlobal('fetch', () => Promise.resolve(new Response(JSON.stringify({
			error: "Record 'items.radio' changed after it was loaded.",
			code: 'record_conflict',
			record_id: 'items.radio',
			expected_hash: 'a'.repeat(64),
			current_hash: 'b'.repeat(64),
			base: { name: 'Base' },
			current: { name: 'Current' },
			proposed: { name: 'Mine' },
		}), { status: 409, headers: { 'content-type': 'application/json' } })));

		const caught = await requestJson('/api/entries/items.radio').catch((error: unknown) => error);
		expect(caught).toBeInstanceOf(ApiError);
		expect((caught as ApiError).code).toBe('record_conflict');
		expect((caught as ApiError).details).toMatchObject({
			record_id: 'items.radio',
			current: { name: 'Current' },
			proposed: { name: 'Mine' },
		});
	});
});

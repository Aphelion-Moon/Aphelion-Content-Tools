import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, requestJson } from './api';

afterEach(() => vi.unstubAllGlobals());

describe('requestJson error details', () => {
	it('rejects a successful HTML response as a protocol error', async () => {
		vi.stubGlobal('fetch', () => Promise.resolve(new Response('<html>Wrong service</html>', {
			status: 200, headers: { 'content-type': 'text/html' },
		})));
		await expect(requestJson('/api/example')).rejects.toMatchObject({
			name: 'ApiError', status: 200, code: 'invalid_response',
		});
	});
	it('keeps successful malformed JSON as a decoding failure', async () => {
		vi.stubGlobal('fetch', () => Promise.resolve(new Response('not json', {
			headers: { 'content-type': 'application/json' },
		})));
		await expect(requestJson('/api/example')).rejects.toBeInstanceOf(SyntaxError);
	});
	it('preserves Headers objects when adding the JSON content type', async () => {
		const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { headers: { 'content-type': 'application/json' } }));
		vi.stubGlobal('fetch', fetchMock);
		await requestJson('/api/example', { method: 'POST', body: '{}', headers: new Headers({ 'X-Request-ID': 'example' }) });
		const sent = new Headers(fetchMock.mock.calls[0]![1].headers);
		expect(sent.get('X-Request-ID')).toBe('example');
		expect(sent.get('Content-Type')).toBe('application/json');
	});
	it.each(['null', '{"error":42}', 'not json'])('retains HTTP status for an unexpected error body: %s', async (body) => {
		vi.stubGlobal('fetch', () => Promise.resolve(new Response(body, { status: 502, headers: { 'content-type': 'application/json' } })));
		await expect(requestJson('/api/example')).rejects.toMatchObject({ name: 'ApiError', status: 502, message: 'Request failed (502).' });
	});
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

import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import CollaborationStatus from './CollaborationStatus';

function jsonResponse(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

const capabilities = { configured: true, version: true, session_access: false, join: false, checkpoint: false, reason: 'Session actions require user authorization.' };

afterEach(() => {
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
	document.body.replaceChildren();
	localStorage.clear();
});

describe('CollaborationStatus', () => {
	it('keeps an unconfigured integration out of the shell and does not probe the service', async () => {
		const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ...capabilities, configured: false, version: false }));
		vi.stubGlobal('fetch', fetchMock);
		const host = document.createElement('div');
		const dispose = render(() => <CollaborationStatus />, host);
		await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
		expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/collaboration/capabilities');
		expect(host.querySelector('section')).toBeNull();
		dispose();
	});

	it('does not offer session actions merely because the protocol is compatible', async () => {
		const fetchMock = vi.fn()
			.mockResolvedValueOnce(jsonResponse(capabilities))
			.mockResolvedValueOnce(jsonResponse({ build: 'test', revision: 'abc', protocol_versions: [1], schema_versions: [1], compatible: true }));
		vi.stubGlobal('fetch', fetchMock);
		const host = document.createElement('div');
		const dispose = render(() => <CollaborationStatus />, host);
		await vi.waitFor(() => expect(host.textContent).toContain('user authorization'));
		expect(host.textContent).toContain('Compatible');
		expect(host.querySelector('input')).toBeNull();
		expect(host.querySelector('button')).toBeNull();
		expect(fetchMock).toHaveBeenCalledTimes(2);
		dispose();
	});

	it('distinguishes incompatible and unavailable diagnostics with a focusable retry', async () => {
		const fetchMock = vi.fn()
			.mockResolvedValueOnce(jsonResponse(capabilities))
			.mockResolvedValueOnce(jsonResponse({ error: 'offline', code: 'collaboration_unavailable' }, 503))
			.mockResolvedValueOnce(jsonResponse({ build: 'test', revision: 'abc', protocol_versions: [2], schema_versions: [1], compatible: false }));
		vi.stubGlobal('fetch', fetchMock);
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <CollaborationStatus />, host);
		await vi.waitFor(() => expect(host.textContent).toContain('Unavailable'));
		const retry = host.querySelector<HTMLButtonElement>('button')!;
		retry.focus();
		expect(document.activeElement).toBe(retry);
		expect(retry.textContent).toBe('Retry');
		retry.click();
		await vi.waitFor(() => expect(host.textContent).toContain('Incompatible'));
		expect(host.querySelector('[role="status"]')).not.toBeNull();
		dispose();
	});
});

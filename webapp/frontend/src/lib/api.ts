// The single HTTP client for the whole app. Before the rewrite this function existed in seven separate
// copies (file-management.js, open-in-menu.js, references-panel.js, store-status-widget.js,
// lore_editor/app.js, content_graph/graph.js, content_graph/modular-debug.js), each subtly free to drift.
// Every caller now imports this one.

export class ApiError extends Error {
	readonly status: number;
	readonly code: string | null;
	readonly details: Readonly<Record<string, unknown>>;

	constructor(message: string, status: number, body: Readonly<Record<string, unknown>> = {}) {
		super(message);
		this.name = 'ApiError';
		this.status = status;
		this.code = typeof body['code'] === 'string' ? body['code'] : null;
		this.details = body;
	}
}

/**
 * Fetch JSON from the backend, raising ApiError with the server's own message on failure.
 *
 * The backend reports failures as `{"error": "..."}` with a non-2xx status; that message is written for
 * humans and is what the UI surfaces, so it is preserved rather than replaced with a generic string.
 */
export async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
	const init: RequestInit = { ...options };
	// Only set a JSON content type when there is actually a body -- a GET with this header set trips
	// stricter servers and preflight paths for no benefit.
	if (options.body !== undefined && options.body !== null) {
		const headers = new Headers(options.headers);
		if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
		init.headers = headers;
	}
	const response = await fetch(path, init);

	const contentType = response.headers.get('content-type') ?? '';
	let payload: unknown = {};
	if (contentType.includes('application/json')) {
		try { payload = await response.json(); }
		catch (error) {
			// A broken error response must not hide the HTTP status. Successful malformed JSON
			// remains a decoding error rather than masquerading as an empty successful payload.
			if (response.ok) throw error;
		}
	} else if (response.ok) {
		throw new ApiError('The server returned an unexpected response format.', response.status, { code: 'invalid_response' });
	}

	if (!response.ok) {
		const details = payload && typeof payload === 'object' && !Array.isArray(payload) ? payload as Record<string, unknown> : {};
		const message = typeof details['error'] === 'string' ? details['error'] : `Request failed (${response.status}).`;
		throw new ApiError(message, response.status, details);
	}
	return payload as T;
}

function withBody(method: string, body: unknown): RequestInit {
	return body === undefined ? { method } : { method, body: JSON.stringify(body) };
}

export const api = {
	get: <T>(path: string, options: RequestInit = {}) => requestJson<T>(path, options),
	post: <T>(path: string, body?: unknown) => requestJson<T>(path, withBody('POST', body)),
	put: <T>(path: string, body?: unknown) => requestJson<T>(path, withBody('PUT', body)),
	delete: <T>(path: string, body?: unknown) => requestJson<T>(path, withBody('DELETE', body)),
};

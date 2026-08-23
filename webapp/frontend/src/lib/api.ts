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

interface ErrorBody {
	error?: string;
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
		init.headers = { 'Content-Type': 'application/json', ...options.headers };
	}
	const response = await fetch(path, init);

	const contentType = response.headers.get('content-type') ?? '';
	const payload: unknown = contentType.includes('application/json') ? await response.json() : {};

	if (!response.ok) {
		const message = (payload as ErrorBody).error ?? `Request failed (${response.status}).`;
		const details = payload && typeof payload === 'object' ? payload as Record<string, unknown> : {};
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

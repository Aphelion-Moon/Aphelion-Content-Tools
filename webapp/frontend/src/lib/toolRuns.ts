import { api } from './api';
import type { components } from './api-schema';

type ToolRun = components['schemas']['ToolRun'];

function pause(signal: AbortSignal): Promise<void> {
	return new Promise((resolve, reject) => {
		signal.throwIfAborted();
		const abort = () => { clearTimeout(timer); reject(signal.reason); };
		const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve(); }, 750);
		signal.addEventListener('abort', abort, { once: true });
	});
}

/** Observe an existing job without owning or cancelling the backend job itself.
 * Every tool uses the same serialized polling and route-disposal behavior.
 */
export async function waitForToolRun(runId: string, options: {
	readonly signal: AbortSignal;
	readonly onUpdate?: (run: ToolRun) => void;
}): Promise<ToolRun> {
	for (;;) {
		options.signal.throwIfAborted();
		const run = await api.get<ToolRun>(`/api/tools/runs/${encodeURIComponent(runId)}`, { signal: options.signal });
		options.signal.throwIfAborted();
		options.onUpdate?.(run);
		if (run.status !== 'queued' && run.status !== 'running') return run;
		await pause(options.signal);
	}
}

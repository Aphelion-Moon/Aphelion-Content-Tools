import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';
import { waitForToolRun } from './toolRuns';

afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

describe('shared tool-run observer', () => {
	it('reports progress in order and returns the terminal record', async () => {
		vi.useFakeTimers();
		const done = { run_id: 'run/1', status: 'succeeded', output: 'Finished' };
		const get = vi.spyOn(api, 'get').mockResolvedValueOnce({ status: 'running', output: 'Working' }).mockResolvedValueOnce(done);
		const progress = vi.fn();
		const result = waitForToolRun('run/1', { signal: new AbortController().signal, onUpdate: progress });
		await vi.advanceTimersByTimeAsync(750);
		expect(await result).toEqual(done);
		expect(progress.mock.calls.map(([run]) => run.output)).toEqual(['Working', 'Finished']);
		expect(get.mock.calls[0]![0]).toBe('/api/tools/runs/run%2F1');
	});
	it('aborts the scheduled wait without leaving another poll behind', async () => {
		vi.useFakeTimers();
		const controller = new AbortController();
		const get = vi.spyOn(api, 'get').mockResolvedValue({ status: 'running', output: 'Working' });
		const result = waitForToolRun('run-1', { signal: controller.signal });
		const rejected = expect(result).rejects.toMatchObject({ name: 'AbortError' });
		await vi.advanceTimersByTimeAsync(1);
		controller.abort();
		await rejected;
		await vi.advanceTimersByTimeAsync(5000);
		expect(get).toHaveBeenCalledTimes(1);
		expect(vi.getTimerCount()).toBe(0);
	});
	it('ignores a pending response even if its transport does not honor abort', async () => {
		const controller = new AbortController();
		let resolve!: (value: unknown) => void;
		vi.spyOn(api, 'get').mockReturnValue(new Promise((done) => { resolve = done; }));
		const progress = vi.fn();
		const result = waitForToolRun('run-1', { signal: controller.signal, onUpdate: progress });
		const rejected = expect(result).rejects.toMatchObject({ name: 'AbortError' });
		controller.abort();
		resolve({ status: 'succeeded' });
		await rejected;
		expect(progress).not.toHaveBeenCalled();
	});
});

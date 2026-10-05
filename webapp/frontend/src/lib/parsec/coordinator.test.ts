import { describe, expect, it, vi } from 'vitest';
import { createParsecCoordinator, type ParsecCoordinatorEnvironment } from './coordinator';
import type { ActivityRecord } from './journalTypes';
import type { ParsecFeedback } from './types';

interface ScheduledTimer {
	readonly id: number;
	readonly at: number;
	readonly callback: () => void;
}

function createHarness() {
	let now = 0;
	let nextTimerId = 1;
	const timers = new Map<number, ScheduledTimer>();
	const published: Array<ParsecFeedback | null> = [];
	const liveLines: Array<{ readonly feedback: ParsecFeedback; readonly activityId: string }> = [];
	const activities: ActivityRecord[] = [];
	const activityFailures: unknown[] = [];

	const environment: ParsecCoordinatorEnvironment<number> = {
		now: () => now,
		setTimer: (callback, delayMs) => {
			const id = nextTimerId++;
			timers.set(id, { id, at: now + delayMs, callback });
			return id;
		},
		clearTimer: (id) => timers.delete(id),
		publish: (feedback) => published.push(feedback),
		context: () => ({ route: '/lore-editor', contextId: 'record:/obj/item/radio' }),
		record: (feedback, activityId) => liveLines.push({ feedback, activityId }),
		recordActivity: async (record) => {
			activities.push(record);
		},
		activityFailure: (error) => activityFailures.push(error),
	};

	function advanceBy(delayMs: number): void {
		const target = now + delayMs;
		while (true) {
			const next = [...timers.values()]
				.filter((timer) => timer.at <= target)
				.sort((left, right) => left.at - right.at || left.id - right.id)[0];
			if (!next) break;
			timers.delete(next.id);
			now = next.at;
			next.callback();
		}
		now = target;
	}

	return { environment, advanceBy, published, liveLines, activities, activityFailures };
}

describe('Parsec coordinator', () => {
	it('publishes companion dialogue with its origin, queues behind errors, and clears without journaling a new line', async () => {
		const harness = createHarness();
		const publish = vi.fn(harness.environment.publish);
		const coordinator = createParsecCoordinator({ ...harness.environment, publish });
		const event = { type: 'interaction', phase: 'companion', lineId: 'furniture.bed.voluntary', tool: 'parsec' } as const;
		coordinator.report({ type: 'notice', phase: 'error', summary: 'Read failed', tool: 'lore-editor' });
		coordinator.report(event);
		expect(publish).toHaveBeenCalledTimes(1);
		harness.advanceBy(8_000);
		expect(publish).toHaveBeenLastCalledWith(expect.objectContaining({ priority: 10 }), event);
		await coordinator.flushActivity();
		expect(harness.activities).toHaveLength(2);
		expect(harness.activities[1]).toMatchObject({ eventType: 'interaction', phase: 'companion', parsecText: expect.stringContaining('bed') });
		coordinator.dismiss();
		expect(publish).toHaveBeenLastCalledWith(null);
		await coordinator.flushActivity();
		expect(harness.activities).toHaveLength(2);
	});

	it('keeps simultaneous activity from independent coordinators distinct', async () => {
		const first = createHarness();
		const second = createHarness();
		const left = createParsecCoordinator(first.environment);
		const right = createParsecCoordinator(second.environment);
		left.report({ type: 'notice', phase: 'info', tool: 'parsec', summary: 'First tab' });
		right.report({ type: 'notice', phase: 'info', tool: 'parsec', summary: 'Second tab' });
		await Promise.all([left.flushActivity(), right.flushActivity()]);
		expect(first.activities[0]!.id).not.toBe(second.activities[0]!.id);
	});
	it('replaces delayed progress with a higher-priority error and never resurrects progress', () => {
		const harness = createHarness();
		const coordinator = createParsecCoordinator(harness.environment);

		coordinator.report({
			type: 'fetch',
			phase: 'started',
			tool: 'lore-editor',
			summary: 'Loading',
			dedupeKey: 'entry:radio',
		});
		harness.advanceBy(200);
		expect(harness.published).toEqual([]);

		coordinator.report({
			type: 'fetch',
			phase: 'failed',
			tool: 'lore-editor',
			summary: 'Load failed',
			technicalDetail: 'HTTP 500',
			dedupeKey: 'entry:radio',
		});
		harness.advanceBy(1000);

		expect(harness.published.at(-1)?.kind).toBe('error');
		expect(harness.published.some((item) => item?.text.includes('Still fetching'))).toBe(false);
		expect(harness.liveLines).toHaveLength(1);
		expect(harness.liveLines[0]?.feedback.technicalDetail).toBe('HTTP 500');
	});

	it('bounds the pending queue and drops idle feedback before real work', () => {
		const harness = createHarness();
		const coordinator = createParsecCoordinator(harness.environment);

		coordinator.report({ type: 'idle', phase: 'contextual', route: '/lore-editor', tool: 'parsec' });
		for (let index = 0; index < 8; index += 1) {
			coordinator.report({
				type: 'mutation',
				phase: 'completed',
				tool: 'lore-editor',
				summary: `Saved ${index}`,
				dedupeKey: `save:${index}`,
			});
		}

		expect(coordinator.pendingCount()).toBeLessThanOrEqual(5);
		expect(coordinator.snapshot().some((item) => item.priority === 10)).toBe(false);
		expect(harness.published.at(-1)?.text).toContain('Saved 0');
	});

	it('advances to the next queued message when the current one expires', () => {
		const harness = createHarness();
		const coordinator = createParsecCoordinator(harness.environment);

		coordinator.report({ type: 'mutation', phase: 'completed', tool: 'lore-editor', summary: 'First save', dedupeKey: 'first' });
		coordinator.report({ type: 'mutation', phase: 'completed', tool: 'lore-editor', summary: 'Second save', dedupeKey: 'second' });
		expect(harness.published.at(-1)?.text).toContain('First save');

		harness.advanceBy(4000);
		expect(harness.published.at(-1)?.text).toContain('Second save');
	});

	it('suppresses a completed fetch that finishes before delayed feedback appears', () => {
		const harness = createHarness();
		const coordinator = createParsecCoordinator(harness.environment);

		coordinator.report({ type: 'fetch', phase: 'started', tool: 'lore-editor', summary: 'Loading Radio', dedupeKey: 'entry:radio' });
		harness.advanceBy(200);
		coordinator.report({ type: 'fetch', phase: 'completed', tool: 'lore-editor', summary: 'Loaded Radio', dedupeKey: 'entry:radio' });
		harness.advanceBy(500);

		expect(harness.published).toEqual([]);
		expect(harness.liveLines).toEqual([]);
	});

	it('accepts navigation as context without producing a balloon or history entry', () => {
		const harness = createHarness();
		const coordinator = createParsecCoordinator(harness.environment);

		coordinator.report({ type: 'navigation', phase: 'context-changed', tool: null, route: '/content-graph' });

		expect(harness.published).toEqual([]);
		expect(harness.liveLines).toEqual([]);
	});

	it('records one durable event for accepted feedback and links the live line', async () => {
		const harness = createHarness();
		const coordinator = createParsecCoordinator(harness.environment);

		coordinator.report({
			type: 'fetch',
			phase: 'failed',
			tool: 'lore-editor',
			summary: 'Could not load entry.',
			technicalDetail: 'HTTP 500 token=station-secret',
			dedupeKey: 'entry:radio',
		});
		await coordinator.flushActivity();

		expect(harness.activities).toHaveLength(1);
		expect(harness.activities[0]?.technicalDetail).toBe('HTTP 500 token=[REDACTED]');
		expect(harness.liveLines[0]?.activityId).toBe(harness.activities[0]?.id);
		expect(harness.activityFailures).toEqual([]);
	});

	it('does not persist a fast fetch that was suppressed before the delay', async () => {
		const harness = createHarness();
		const coordinator = createParsecCoordinator(harness.environment);

		coordinator.report({ type: 'fetch', phase: 'started', tool: 'lore-editor', summary: 'Loading', dedupeKey: 'entry:radio' });
		harness.advanceBy(100);
		coordinator.report({ type: 'fetch', phase: 'completed', tool: 'lore-editor', summary: 'Loaded', dedupeKey: 'entry:radio' });
		await coordinator.flushActivity();

		expect(harness.activities).toEqual([]);
		expect(harness.liveLines).toEqual([]);
	});

	it('coalesces unchanged connection phases until the connection state changes', async () => {
		const harness = createHarness();
		const coordinator = createParsecCoordinator(harness.environment);

		coordinator.report({ type: 'connection', phase: 'disconnected', tool: 'live', dedupeKey: 'live-connection' });
		coordinator.dismiss();
		coordinator.report({ type: 'connection', phase: 'disconnected', tool: 'live', dedupeKey: 'live-connection' });
		await coordinator.flushActivity();

		expect(harness.activities.map((activity) => activity.phase)).toEqual(['disconnected']);
		expect(harness.liveLines).toHaveLength(1);

		coordinator.report({ type: 'connection', phase: 'recovered', tool: 'live', dedupeKey: 'live-connection' });
		await coordinator.flushActivity();
		expect(harness.activities.map((activity) => activity.phase)).toEqual(['disconnected', 'recovered']);
	});
});

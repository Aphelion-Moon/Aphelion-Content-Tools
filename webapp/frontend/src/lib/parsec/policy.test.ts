import { describe, expect, it } from 'vitest';
import { canEmitIdle, dwellMsForFeedback, priorityForEvent, shouldDelayFeedback } from './policy';

describe('Parsec policy', () => {
	it('orders errors above blocked work, success, progress, and idle', () => {
		const error = priorityForEvent({
			type: 'fetch',
			phase: 'failed',
			tool: 'lore-editor',
			summary: 'Failed',
		});
		const blocked = priorityForEvent({
			type: 'validation',
			phase: 'blocked',
			tool: 'file-management',
			summary: 'Blocked',
		});
		const success = priorityForEvent({
			type: 'mutation',
			phase: 'completed',
			tool: 'lore-editor',
			summary: 'Saved',
		});
		const progress = priorityForEvent({
			type: 'fetch',
			phase: 'started',
			tool: 'lore-editor',
			summary: 'Loading',
		});
		const idle = priorityForEvent({
			type: 'idle',
			phase: 'contextual',
			tool: 'parsec',
			route: '/lore-editor',
		});

		expect([error, blocked, success, progress, idle]).toEqual([100, 80, 60, 40, 10]);
	});

	it('delays started searches and fetches but not failures or completions', () => {
		expect(shouldDelayFeedback({
			type: 'search',
			phase: 'started',
			tool: 'global-search',
			query: 'radio',
		})).toBe(true);
		expect(shouldDelayFeedback({
			type: 'fetch',
			phase: 'started',
			tool: 'lore-editor',
			summary: 'Loading',
		})).toBe(true);
		expect(shouldDelayFeedback({
			type: 'fetch',
			phase: 'failed',
			tool: 'lore-editor',
			summary: 'Failed',
		})).toBe(false);
		expect(shouldDelayFeedback({
			type: 'mutation',
			phase: 'completed',
			tool: 'lore-editor',
			summary: 'Saved',
		})).toBe(false);
	});

	it('keeps errors longest and gives readable long messages extra time', () => {
		expect(dwellMsForFeedback({ kind: 'error', text: 'Failed.' })).toBe(8000);
		expect(dwellMsForFeedback({ kind: 'warning', text: 'Blocked.' })).toBe(6000);
		expect(dwellMsForFeedback({ kind: 'info', text: 'Short.' })).toBe(4000);
		expect(dwellMsForFeedback({ kind: 'success', text: 'A'.repeat(121) })).toBe(6000);
	});

	it('allows idle feedback only when the visible app is quiet and the user is not typing', () => {
		const quiet = {
			documentVisible: true,
			editableFocused: false,
			activeRunCount: 0,
			hasFeedback: false,
			connectionNeedsAttention: false,
		};

		expect(canEmitIdle(quiet)).toBe(true);
		expect(canEmitIdle({ ...quiet, documentVisible: false })).toBe(false);
		expect(canEmitIdle({ ...quiet, editableFocused: true })).toBe(false);
		expect(canEmitIdle({ ...quiet, activeRunCount: 1 })).toBe(false);
		expect(canEmitIdle({ ...quiet, hasFeedback: true })).toBe(false);
		expect(canEmitIdle({ ...quiet, connectionNeedsAttention: true })).toBe(false);
	});
});

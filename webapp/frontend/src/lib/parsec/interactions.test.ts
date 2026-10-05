import { describe, expect, it } from 'vitest';
import { initialCompanionState } from './companionReducer';
import { beginToolInteraction, finishToolInteraction, updateToolInteraction } from './interactions';
import { DEFAULT_COMPANION_SETTINGS } from './companionTypes';

const state = initialCompanionState({
	consent: 'allowed',
	familiarity: 1,
	settings: DEFAULT_COMPANION_SETTINGS,
});

describe('Parsec primary interaction mapping', () => {
	it.each([
		['pat', 'pat-started'],
		['ball', 'ball-placed'],
		['tug', 'tug-offered'],
		['brush', 'brush-started'],
		['treat', 'treat-offered'],
		['whistle', 'recall-requested'],
	] as const)('maps %s to %s without application commands', (tool, expectedType) => {
		const result = beginToolInteraction(tool, state, { point: { x: 20, y: 20 }, at: 100 });
		expect(result.intents).toContainEqual(expect.objectContaining({ type: expectedType }));
		expect(result.intents.some((intent) => ['navigate', 'search', 'save', 'fetch'].includes(intent.type))).toBe(false);
	});

	it('normalizes tug tension and brush distance without emitting arbitrary commands', () => {
		const tug = beginToolInteraction('tug', state, { point: { x: 0, y: 0 }, at: 0 }).session!;
		expect(updateToolInteraction(tug, { point: { x: 500, y: 0 }, at: 100 })).toContainEqual({
			type: 'tug-tension',
			tension: 1,
		});
		const brush = beginToolInteraction('brush', state, { point: { x: 0, y: 0 }, at: 0 }).session!;
		expect(updateToolInteraction(brush, { point: { x: 3, y: 4 }, at: 50 })).toContainEqual({
			type: 'brush-stroke',
			direction: { x: 0.6, y: 0.8 },
		});
	});

	it('finishes throwable, tug, brush, and treat sessions with typed intents', () => {
		for (const [tool, expected] of [
			['ball', 'ball-thrown'],
			['tug', 'tug-released'],
			['brush', 'brush-finished'],
			['treat', 'treat-placed'],
		] as const) {
			const session = beginToolInteraction(tool, state, { point: { x: 0, y: 0 }, at: 0 }).session!;
			expect(finishToolInteraction(session, { point: { x: 20, y: 10 }, at: 100 }))
				.toContainEqual(expect.objectContaining({ type: expected }));
		}
	});

	it('refuses physical toy sessions while Parsec is in a closed cage', () => {
		const caged = { ...state, location: { kind: 'cage', closed: true } as const };
		expect(beginToolInteraction('ball', caged, { point: { x: 0, y: 0 }, at: 0 }).session).toBeNull();
		expect(beginToolInteraction('pat', caged, { point: { x: 0, y: 0 }, at: 0 }).intents)
			.toContainEqual(expect.objectContaining({ type: 'pat-started' }));
	});
});

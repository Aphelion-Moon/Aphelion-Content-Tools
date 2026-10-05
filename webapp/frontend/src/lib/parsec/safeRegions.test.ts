import { describe, expect, it } from 'vitest';
import { chooseOrdinaryPerch, collectSafeRegions, type SafeRegionSnapshot } from './safeRegions';

describe('Parsec safe regions', () => {
	it('chooses an edge perch that does not overlap controls, shell chrome, or selections', () => {
		const snapshot: SafeRegionSnapshot = {
			viewport: { x: 0, y: 0, width: 1000, height: 700 },
			shellChrome: [{ x: 0, y: 0, width: 220, height: 700 }],
			interactiveControls: [{ x: 760, y: 0, width: 240, height: 120 }],
			selectionRanges: [{ x: 760, y: 580, width: 240, height: 120 }],
		};
		const perch = chooseOrdinaryPerch(snapshot, { width: 96, height: 96 }, { next: () => 0 });
		expect(perch).toEqual({ x: 452, y: 12 });
	});

	it('collects visible interactive controls without treating the whole app root as blocked', () => {
		const root = document.createElement('main');
		const button = document.createElement('button');
		button.getBoundingClientRect = () => ({ x: 10, y: 20, left: 10, top: 20, right: 110, bottom: 60, width: 100, height: 40, toJSON: () => ({}) });
		root.append(button, document.createElement('p'));
		document.body.append(root);
		const snapshot = collectSafeRegions(root, { width: 500, height: 400 });
		expect(snapshot.interactiveControls).toEqual([{ x: 10, y: 20, width: 100, height: 40 }]);
		expect(snapshot.interactiveControls).toHaveLength(1);
	});
});

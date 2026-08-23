import { describe, expect, it } from 'vitest';
import {
	DEFAULT_FORCES,
	DEFAULT_SIMULATION_TUNING,
	LARGE_SCOPE_SETTLE_TICKS,
	chargeStrengthForNode,
	resolvePhysicsPolicy,
} from './simulation';

describe('Content Graph physics policy', () => {
	it('keeps live physics automatic only for bounded interactive scopes', () => {
		expect(resolvePhysicsPolicy('auto', 1_500, 1_500)).toMatchObject({ runInitialSettle: true, live: true });
		expect(resolvePhysicsPolicy('auto', 1_501, 1_500)).toMatchObject({ runInitialSettle: true, live: false });
		expect(resolvePhysicsPolicy('off', 200, 1_500)).toMatchObject({ runInitialSettle: true, live: false });
		expect(resolvePhysicsPolicy('on', 1_501, 1_500)).toMatchObject({ runInitialSettle: true, live: true });
	});

	it('does not start a 41k-node force settle in automatic mode', () => {
		expect(resolvePhysicsPolicy('auto', 41_703, 1_500)).toEqual({
			runInitialSettle: false,
			live: false,
			settleTickLimit: 0,
		});
		expect(resolvePhysicsPolicy('on', 41_703, 1_500).settleTickLimit).toBe(LARGE_SCOPE_SETTLE_TICKS);
	});

	it('preserves the tuned legacy defaults', () => {
		expect(DEFAULT_FORCES).toEqual({
			repulsion: 2600,
			springLength: 70,
			springStrength: 0.02,
			center: 0.004,
			clusterStrength: 0.025,
			isolatedPull: 4,
		});
		expect(DEFAULT_SIMULATION_TUNING.ambientAlpha).toBe(0.02);
		expect(DEFAULT_SIMULATION_TUNING.collideEnabled).toBe(true);
	});

	it('applies the drag-only repulsion multiplier without changing saved force settings', () => {
		const node = { degree: 4 } as never;
		const weighted = { ...DEFAULT_SIMULATION_TUNING, chargeByDegree: true, chargeByDegreeFactor: 0.25 };
		expect(chargeStrengthForNode(node, DEFAULT_FORCES, weighted, 3)).toBe(-15_600);
		expect(DEFAULT_FORCES.repulsion).toBe(2_600);
	});
});

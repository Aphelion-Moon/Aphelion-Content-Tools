import { describe, expect, it } from 'vitest';
import { createTabCoordinator, type TabCoordinatorEnvironment } from './tabCoordinator';

class MemoryStorage implements Storage {
	private readonly values = new Map<string, string>();
	get length(): number { return this.values.size; }
	clear(): void { this.values.clear(); }
	getItem(key: string): string | null { return this.values.get(key) ?? null; }
	key(index: number): string | null { return [...this.values.keys()][index] ?? null; }
	removeItem(key: string): void { this.values.delete(key); }
	setItem(key: string, value: string): void { this.values.set(key, value); }
}

function harness() {
	const storage = new MemoryStorage();
	let now = 1_000;
	let visible = true;
	const environment = (tabId: string): TabCoordinatorEnvironment => ({
		tabId,
		storage,
		now: () => now,
		isVisible: () => visible,
		leaseMs: 5_000,
	});
	return {
		environment,
		advance: (milliseconds: number) => { now += milliseconds; },
		setVisible: (next: boolean) => { visible = next; },
	};
}

describe('companion active-tab coordination', () => {
	it('prefers a granted Web Lock and releases it on disposal', async () => {
		let released = false;
		let observeRelease: (() => void) | undefined;
		const releaseObserved = new Promise<void>((resolve) => { observeRelease = resolve; });
		const storage = new MemoryStorage();
		const coordinator = createTabCoordinator({
			tabId: 'native',
			storage,
			now: () => 1_000,
			isVisible: () => true,
			locks: {
				request: async (_name, _options, callback) => {
					await callback({ name: 'aphelion-parsec-autonomous' });
					released = true;
					observeRelease?.();
				},
			},
		});
		expect(await coordinator.start()).toBe(true);
		expect(coordinator.isLeader()).toBe(true);
		coordinator.dispose();
		await releaseObserved;
		expect(released).toBe(true);
	});

	it('can reacquire its Web Lock after a hidden-visible cycle', async () => {
		let visible = true;
		let acquisitions = 0;
		const coordinator = createTabCoordinator({
			tabId: 'native-reacquire',
			storage: new MemoryStorage(),
			now: () => 1_000,
			isVisible: () => visible,
			locks: {
				request: async (_name, _options, callback) => {
					acquisitions += 1;
					await callback({ name: 'aphelion-parsec-autonomous' });
				},
			},
		});
		expect(await coordinator.start()).toBe(true);
		visible = false;
		expect(coordinator.heartbeat()).toBe(false);
		await Promise.resolve();
		await Promise.resolve();
		visible = true;
		expect(coordinator.tryAcquire()).toBe(true);
		expect(acquisitions).toBe(2);
		expect(await coordinator.start()).toBe(true);
		expect(acquisitions).toBe(2);
		expect(coordinator.isLeader()).toBe(true);
		coordinator.dispose();
	});

	it('elects only one autonomous owner and hands off an expired lease', () => {
		const shared = harness();
		const first = createTabCoordinator(shared.environment('a'));
		const second = createTabCoordinator(shared.environment('b'));
		expect(first.tryAcquire()).toBe(true);
		expect(second.tryAcquire()).toBe(false);
		expect([first.isLeader(), second.isLeader()].filter(Boolean)).toHaveLength(1);

		shared.advance(5_001);
		expect(second.tryAcquire()).toBe(true);
		expect(second.isLeader()).toBe(true);
		expect(first.isLeader()).toBe(false);
	});

	it('renews its own lease without stealing another live owner', () => {
		const shared = harness();
		const first = createTabCoordinator(shared.environment('a'));
		const second = createTabCoordinator(shared.environment('b'));
		first.tryAcquire();
		shared.advance(2_000);
		expect(first.heartbeat()).toBe(true);
		shared.advance(4_000);
		expect(second.tryAcquire()).toBe(false);
	});

	it('releases leadership when hidden and permits a visible handoff', () => {
		const shared = harness();
		const first = createTabCoordinator(shared.environment('a'));
		first.tryAcquire();
		shared.setVisible(false);
		expect(first.heartbeat()).toBe(false);

		shared.setVisible(true);
		const second = createTabCoordinator(shared.environment('b'));
		expect(second.tryAcquire()).toBe(true);
	});

	it('does not delete a lease that has already transferred to another tab', () => {
		const shared = harness();
		const first = createTabCoordinator(shared.environment('a'));
		const second = createTabCoordinator(shared.environment('b'));
		first.tryAcquire();
		shared.advance(5_001);
		second.tryAcquire();
		first.release();
		expect(second.isLeader()).toBe(true);
	});
});

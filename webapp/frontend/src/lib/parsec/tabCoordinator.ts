export const COMPANION_LEASE_KEY = 'aphelion-parsec-autonomous-lease';

interface CompanionLease {
	ownerId: string;
	expiresAt: number;
}

export interface TabCoordinatorChannel {
	postMessage(message: unknown): void;
	close(): void;
}

export interface TabCoordinatorEnvironment {
	tabId: string;
	storage: Storage;
	now: () => number;
	isVisible: () => boolean;
	leaseMs?: number;
	channel?: TabCoordinatorChannel;
	locks?: {
		request(
			name: string,
			options: { ifAvailable: true; mode: 'exclusive' },
			callback: (lock: { name: string } | null) => Promise<void>,
		): Promise<void>;
	};
}

export interface CompanionTabCoordinator {
	start(): Promise<boolean>;
	tryAcquire(): boolean;
	isLeader(): boolean;
	heartbeat(): boolean;
	release(): void;
	dispose(): void;
}

function readLease(storage: Storage): CompanionLease | null {
	try {
		const source = storage.getItem(COMPANION_LEASE_KEY);
		if (!source) return null;
		const value = JSON.parse(source) as Partial<CompanionLease>;
		return typeof value.ownerId === 'string' && typeof value.expiresAt === 'number' && Number.isFinite(value.expiresAt)
			? { ownerId: value.ownerId, expiresAt: value.expiresAt }
			: null;
	} catch {
		return null;
	}
}

export function createTabCoordinator(environment: TabCoordinatorEnvironment): CompanionTabCoordinator {
	const leaseMs = environment.leaseMs ?? 8_000;
	let disposed = false;
	let nativeLeader = false;
	let nativeRelease: (() => void) | null = null;
	let nativeStart: Promise<boolean> | null = null;

	function writeLease(): boolean {
		try {
			const lease: CompanionLease = { ownerId: environment.tabId, expiresAt: environment.now() + leaseMs };
			environment.storage.setItem(COMPANION_LEASE_KEY, JSON.stringify(lease));
			environment.channel?.postMessage({ type: 'lease', ...lease });
			return readLease(environment.storage)?.ownerId === environment.tabId;
		} catch {
			return false;
		}
	}

	function isLeader(): boolean {
		if (disposed || !environment.isVisible()) return false;
		if (environment.locks) return nativeLeader;
		const lease = readLease(environment.storage);
		return lease?.ownerId === environment.tabId && lease.expiresAt > environment.now();
	}

	function release(): void {
		if (nativeRelease) {
			nativeLeader = false;
			nativeRelease();
			nativeRelease = null;
			nativeStart = null;
		}
		try {
			if (readLease(environment.storage)?.ownerId === environment.tabId) {
				environment.storage.removeItem(COMPANION_LEASE_KEY);
				environment.channel?.postMessage({ type: 'release', ownerId: environment.tabId });
			}
		} catch {
			// Losing optional autonomous ownership is safe when storage is unavailable.
		}
	}

	return {
		start(): Promise<boolean> {
			if (!environment.locks) return Promise.resolve(this.tryAcquire());
			if (nativeStart) return nativeStart;
			nativeStart = new Promise<boolean>((resolve) => {
				void environment.locks!.request(
					'aphelion-parsec-autonomous',
					{ ifAvailable: true, mode: 'exclusive' },
					async (lock) => {
						if (!lock || disposed || !environment.isVisible()) {
							resolve(false);
							return;
						}
						nativeLeader = true;
						resolve(true);
						await new Promise<void>((release) => { nativeRelease = release; });
						nativeLeader = false;
					},
				)
					.catch(() => resolve(false))
					.finally(() => { nativeStart = null; });
			});
			return nativeStart;
		},
		tryAcquire(): boolean {
			if (disposed || !environment.isVisible()) return false;
			if (environment.locks) {
				if (!nativeLeader) void this.start();
				return nativeLeader;
			}
			const lease = readLease(environment.storage);
			if (lease && lease.ownerId !== environment.tabId && lease.expiresAt > environment.now()) return false;
			return writeLease();
		},
		isLeader,
		heartbeat(): boolean {
			if (disposed || !environment.isVisible()) {
				release();
				return false;
			}
			if (environment.locks) return nativeLeader;
			return isLeader() ? writeLease() : false;
		},
		release,
		dispose(): void {
			release();
			disposed = true;
			environment.channel?.close();
		},
	};
}

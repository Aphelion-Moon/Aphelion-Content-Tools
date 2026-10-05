// @vitest-environment node
import { IDBFactory, IDBIndex, IDBKeyRange, IDBObjectStore } from 'fake-indexeddb';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { openIndexedDbJournal } from './indexedDbJournal';
import type { ActivityRecord } from './journalTypes';

beforeEach(() => vi.stubGlobal('IDBKeyRange', IDBKeyRange));
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function activity(id: string, at = 1, tool = 'lore-editor'): ActivityRecord {
	return { schemaVersion: 1, id, at, eventType: 'search', phase: 'completed', tool, route: null, contextId: null, durationMs: null, resultCount: null, outcome: 'completed', technicalDetail: null, parsecText: id, reaction: 'happy' };
}

describe('IndexedDB activity queries', () => {
	it('reads a bounded cursor page instead of materializing the full object store', async () => {
		const opened = await openIndexedDbJournal(new IDBFactory());
		expect(opened.persistence).toBe('indexeddb');
		try {
			for (let id = 0; id < 150; id += 1) await opened.journal.append(activity(`record-${id}`, id));
			vi.spyOn(IDBObjectStore.prototype, 'getAll').mockImplementation(() => { throw new Error('unbounded getAll'); });
			let visited = 0;
			const openCursor = IDBIndex.prototype.openCursor;
			vi.spyOn(IDBIndex.prototype, 'openCursor').mockImplementation(function (this: IDBIndex, ...args) {
				const request = openCursor.apply(this, args);
				request.addEventListener('success', () => { if (request.result) visited += 1; });
				return request;
			});
			expect((await opened.journal.query({ limit: 10 })).map((row) => row.at)).toEqual([149, 148, 147, 146, 145, 144, 143, 142, 141, 140]);
			expect(visited).toBeLessThanOrEqual(11);
		} finally { opened.journal.close(); }
	});

	it('pages duplicate timestamps and applies filters before the page limit', async () => {
		const { journal } = await openIndexedDbJournal(new IDBFactory());
		try {
			for (const id of ['z', 'Z', 'a', '-', '_']) await journal.append(activity(id));
			await journal.append(activity('unrelated', 2, 'content-graph'));
			const first = await journal.queryPage({ limit: 2, tool: 'lore-editor' });
			const second = await journal.queryPage({ limit: 2, tool: 'lore-editor', cursor: first.nextCursor! });
			const third = await journal.queryPage({ limit: 2, tool: 'lore-editor', cursor: second.nextCursor! });
			expect([...first.records, ...second.records, ...third.records].map((row) => row.id)).toEqual(['z', 'a', '_', 'Z', '-']);
			expect(third.nextCursor).toBeNull();
			expect(await journal.query({ limit: 10, after: 2, before: 1 })).toEqual([]);
		} finally { journal.close(); }
	});

	it('counts and clears in one transaction while preserving a later writer', async () => {
		const factory = new IDBFactory();
		const first = await openIndexedDbJournal(factory);
		const second = await openIndexedDbJournal(factory);
		try {
			for (let id = 0; id < 1_007; id += 1) await first.journal.append(activity(String(id)));
			const clearing = first.journal.clear();
			const append = second.journal.append(activity('after-clear'));
			expect(await clearing).toBe(1_007);
			await append;
			expect((await first.journal.query({ limit: 10 })).map((row) => row.id)).toEqual(['after-clear']);
		} finally { first.journal.close(); second.journal.close(); }
	});
});

function failingFactory(error: DOMException): IDBFactory {
	return {
		open: () => {
			let onerror: ((event: Event) => void) | null = null;
			const request = {
				error,
				get onerror() {
					return onerror;
				},
				set onerror(handler: ((event: Event) => void) | null) {
					onerror = handler;
					queueMicrotask(() => onerror?.(new Event('error')));
				},
			} as unknown as IDBOpenDBRequest;
			return request;
		},
	} as unknown as IDBFactory;
}

describe('IndexedDB activity journal opening', () => {
	it('falls back to a usable memory journal when IndexedDB is unavailable', async () => {
		const result = await openIndexedDbJournal(undefined);

		expect(result.persistence).toBe('memory');
		expect(result.diagnostic).toBe('indexeddb-unavailable');
		expect(result.resetRequired).toBe(false);
		expect(await result.journal.query({ limit: 10 })).toEqual([]);
	});

	it('reports an unsupported newer schema without deleting it', async () => {
		const result = await openIndexedDbJournal(failingFactory(new DOMException('newer', 'VersionError')));

		expect(result.persistence).toBe('memory');
		expect(result.diagnostic).toBe('unsupported-schema');
		expect(result.resetRequired).toBe(true);
	});

	it('uses a nonrecursive session fallback for ordinary open failures', async () => {
		const result = await openIndexedDbJournal(failingFactory(new DOMException('blocked', 'UnknownError')));

		expect(result.persistence).toBe('memory');
		expect(result.diagnostic).toBe('open-failed');
		expect(result.resetRequired).toBe(false);
	});
});

describe('IndexedDB activity journal recovery', () => {
	it('deletes only the named activity database after explicit recovery is requested', async () => {
		let deletedName: string | null = null;
		const factory = {
			deleteDatabase: (name: string) => {
				deletedName = name;
				let onsuccess: ((event: Event) => void) | null = null;
				const request = {
					get onsuccess() {
						return onsuccess;
					},
					set onsuccess(handler: ((event: Event) => void) | null) {
						onsuccess = handler;
						queueMicrotask(() => onsuccess?.(new Event('success')));
					},
				} as unknown as IDBOpenDBRequest;
				return request;
			},
		} as unknown as IDBFactory;

		const { resetIndexedDbJournal } = await import('./indexedDbJournal');
		expect(await resetIndexedDbJournal(factory)).toBe('reset');
		expect(deletedName).toBe('aphelion-parsec');
	});
});

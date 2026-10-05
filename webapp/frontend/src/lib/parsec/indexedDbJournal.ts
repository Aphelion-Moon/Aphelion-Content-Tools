import {
	activityPage, activityQueryLimit, createActivityJournal, createMemoryJournalBackend,
	matchesActivityQuery, type ActivityJournalBackend,
} from './journal';
import type { ActivityJournal, ActivityRecord } from './journalTypes';

const DATABASE_NAME = 'aphelion-parsec';
const DATABASE_VERSION = 1;
const ACTIVITY_STORE = 'activity';

export interface OpenActivityJournalResult {
	readonly journal: ActivityJournal;
	readonly persistence: 'indexeddb' | 'memory';
	readonly diagnostic: 'indexeddb-unavailable' | 'open-failed' | 'unsupported-schema' | null;
	readonly resetRequired: boolean;
}

function requestResult<T>(request: IDBRequest<T>): Promise<T> {
	return new Promise((resolve, reject) => {
		request.onsuccess = () => resolve(request.result);
		request.onerror = () => reject(request.error ?? new Error('IndexedDB request failed.'));
	});
}

function transactionComplete(transaction: IDBTransaction): Promise<void> {
	return new Promise((resolve, reject) => {
		transaction.oncomplete = () => resolve();
		transaction.onerror = () => reject(transaction.error ?? new Error('IndexedDB transaction failed.'));
		transaction.onabort = () => reject(transaction.error ?? new Error('IndexedDB transaction was aborted.'));
	});
}

function createIndexedDbBackend(database: IDBDatabase): ActivityJournalBackend {
	return {
		put: async (record) => {
			const transaction = database.transaction(ACTIVITY_STORE, 'readwrite');
			const completed = transactionComplete(transaction);
			transaction.objectStore(ACTIVITY_STORE).put(record);
			await completed;
		},
		queryPage: async (query) => {
			const limit = activityQueryLimit(query);
			const upper = query.cursor ? Math.min(query.before ?? Infinity, query.cursor.at) : query.before;
			if (limit === 0 || (upper !== undefined && query.after !== undefined && upper < query.after)) return activityPage([], 0);
			const range = upper === undefined
				? (query.after === undefined ? null : IDBKeyRange.lowerBound(query.after))
				: (query.after === undefined ? IDBKeyRange.upperBound(upper) : IDBKeyRange.bound(query.after, upper));
			const transaction = database.transaction(ACTIVITY_STORE, 'readonly');
			const completed = transactionComplete(transaction);
			const records: ActivityRecord[] = [];
			const request = transaction.objectStore(ACTIVITY_STORE).index('at').openCursor(range, 'prev');
			request.onsuccess = () => {
				const cursor = request.result;
				if (!cursor) return;
				// Seek within a tied timestamp instead of rescanning its earlier pages.
				if (query.cursor && cursor.key === query.cursor.at && cursor.primaryKey > query.cursor.id) {
					cursor.continuePrimaryKey(query.cursor.at, query.cursor.id);
					return;
				}
				const record = cursor.value as ActivityRecord;
				if (matchesActivityQuery(record, query)) records.push(record);
				if (records.length <= limit) cursor.continue();
			};
			await completed;
			return activityPage(records, limit);
		},
		deleteBefore: async (cutoff) => {
			const transaction = database.transaction(ACTIVITY_STORE, 'readwrite');
			const completed = transactionComplete(transaction);
			const store = transaction.objectStore(ACTIVITY_STORE);
			const request = store.index('at').openKeyCursor(IDBKeyRange.upperBound(cutoff, true));
			let removed = 0;
			request.onsuccess = () => {
				const cursor = request.result;
				if (!cursor) return;
				store.delete(cursor.primaryKey);
				removed += 1;
				cursor.continue();
			};
			await completed;
			return removed;
		},
		clear: async () => {
			const transaction = database.transaction(ACTIVITY_STORE, 'readwrite');
			const completed = transactionComplete(transaction);
			const store = transaction.objectStore(ACTIVITY_STORE);
			const count = store.count();
			store.clear();
			await completed;
			return count.result;
		},
		close: () => database.close(),
	};
}

function memoryResult(
	diagnostic: Exclude<OpenActivityJournalResult['diagnostic'], null>,
	resetRequired = false,
): OpenActivityJournalResult {
	return {
		journal: createActivityJournal(createMemoryJournalBackend()),
		persistence: 'memory',
		diagnostic,
		resetRequired,
	};
}

export async function openIndexedDbJournal(
	factory: IDBFactory | undefined = globalThis.indexedDB,
): Promise<OpenActivityJournalResult> {
	if (!factory) return memoryResult('indexeddb-unavailable');

	try {
		const request = factory.open(DATABASE_NAME, DATABASE_VERSION);
		request.onupgradeneeded = (event) => {
			const database = request.result;
			if ((event as IDBVersionChangeEvent).oldVersion !== 0) {
				request.transaction?.abort();
				return;
			}
			const store = database.createObjectStore(ACTIVITY_STORE, { keyPath: 'id' });
			store.createIndex('at', 'at');
			store.createIndex('eventType', 'eventType');
			store.createIndex('tool', 'tool');
			store.createIndex('outcome', 'outcome');
		};
		const database = await requestResult(request);
		return {
			journal: createActivityJournal(createIndexedDbBackend(database)),
			persistence: 'indexeddb',
			diagnostic: null,
			resetRequired: false,
		};
	} catch (error) {
		if (error instanceof DOMException && error.name === 'VersionError') {
			return memoryResult('unsupported-schema', true);
		}
		return memoryResult('open-failed');
	}
}

let browserActivityJournal: Promise<OpenActivityJournalResult> | null = null;

export function getBrowserActivityJournal(): Promise<OpenActivityJournalResult> {
	browserActivityJournal ??= openIndexedDbJournal();
	return browserActivityJournal;
}

export type ResetIndexedDbJournalResult = 'reset' | 'unavailable' | 'blocked' | 'failed';

export async function resetIndexedDbJournal(
	factory: IDBFactory | undefined = globalThis.indexedDB,
): Promise<ResetIndexedDbJournalResult> {
	if (!factory) return 'unavailable';
	return new Promise((resolve) => {
		const request = factory.deleteDatabase(DATABASE_NAME);
		request.onsuccess = () => {
			browserActivityJournal = null;
			resolve('reset');
		};
		request.onblocked = () => resolve('blocked');
		request.onerror = () => resolve('failed');
	});
}

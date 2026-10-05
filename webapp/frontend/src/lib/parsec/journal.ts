import type {
	ActivityJournal,
	ActivityPage,
	ActivityQuery,
	ActivityRecord,
	ActivityRetentionDays,
} from './journalTypes';

const DAY_SECONDS = 24 * 60 * 60;
const MAX_QUERY_LIMIT = 1_000;

export interface ActivityJournalBackend {
	put(record: ActivityRecord): Promise<void>;
	queryPage(query: ActivityQuery): Promise<ActivityPage>;
	deleteBefore(cutoff: number): Promise<number>;
	clear(): Promise<number>;
	close(): void;
}

export function createMemoryJournalBackend(): ActivityJournalBackend {
	const records = new Map<string, ActivityRecord>();
	return {
		put: async (record) => {
			records.set(record.id, record);
		},
		queryPage: async (query) => {
			const limit = activityQueryLimit(query);
			if (limit === 0) return activityPage([], 0);
			const matching = [...records.values()]
				.filter((record) => matchesActivityQuery(record, query))
				// IndexedDB breaks equal index keys by primary key, using code-unit order.
				.sort((left, right) => right.at - left.at || (left.id < right.id ? 1 : left.id > right.id ? -1 : 0))
				.slice(0, limit + 1);
			return activityPage(matching, limit);
		},
		deleteBefore: async (cutoff) => {
			let removed = 0;
			for (const [id, record] of records) {
				if (record.at >= cutoff) continue;
				records.delete(id);
				removed += 1;
			}
			return removed;
		},
		clear: async () => {
			const count = records.size;
			records.clear();
			return count;
		},
		close: () => undefined,
	};
}

function includesText(record: ActivityRecord, query: string): boolean {
	const haystack = [
		record.parsecText,
		record.technicalDetail,
		record.contextId,
		record.tool,
		record.route,
	].filter((value): value is string => value !== null).join('\n').toLocaleLowerCase();
	return haystack.includes(query.toLocaleLowerCase());
}

export function activityQueryLimit(query: ActivityQuery): number {
	if (!Number.isFinite(query.limit)
		|| (query.before !== undefined && !Number.isFinite(query.before))
		|| (query.after !== undefined && !Number.isFinite(query.after))
		|| (query.cursor !== undefined && !Number.isFinite(query.cursor.at))
		|| (query.before !== undefined && query.after !== undefined && query.before < query.after)) return 0;
	return Math.max(0, Math.min(MAX_QUERY_LIMIT, Math.floor(query.limit)));
}

export function matchesActivityQuery(record: ActivityRecord, query: ActivityQuery): boolean {
	return (query.before === undefined || record.at <= query.before)
		&& (query.after === undefined || record.at >= query.after)
		&& (!query.cursor || record.at < query.cursor.at || (record.at === query.cursor.at && record.id < query.cursor.id))
		&& (query.eventType === undefined || record.eventType === query.eventType)
		&& (query.tool === undefined || record.tool === query.tool)
		&& (query.outcome === undefined || record.outcome === query.outcome)
		&& (query.text === undefined || includesText(record, query.text));
}

export function activityPage(matching: readonly ActivityRecord[], limit: number): ActivityPage {
	const records = matching.slice(0, limit);
	const last = records.at(-1);
	return { records, nextCursor: matching.length > limit && last ? { at: last.at, id: last.id } : null };
}

export function createActivityJournal(backend: ActivityJournalBackend): ActivityJournal {
	return {
		append: (record) => backend.put(record),
		query: async (query) => (await backend.queryPage(query)).records,
		queryPage: (query) => backend.queryPage(query),
		prune: (retention: ActivityRetentionDays, now: number) => {
			if (retention === 'manual') return Promise.resolve(0);
			return backend.deleteBefore(now - retention * DAY_SECONDS);
		},
		clear: () => backend.clear(),
		close: () => backend.close(),
	};
}

export function recordsToJson(records: readonly ActivityRecord[]): string {
	return JSON.stringify(records, null, 2);
}

const CSV_FIELDS = [
	'schemaVersion',
	'id',
	'at',
	'eventType',
	'phase',
	'tool',
	'route',
	'contextId',
	'durationMs',
	'resultCount',
	'outcome',
	'technicalDetail',
	'parsecText',
	'reaction',
] as const satisfies readonly (keyof ActivityRecord)[];

function csvCell(value: ActivityRecord[keyof ActivityRecord]): string {
	let text = value === null ? '' : String(value);
	if (/^[=+\-@]/.test(text)) text = `'${text}`;
	if (/[",\r\n]/.test(text)) text = `"${text.replaceAll('"', '""')}"`;
	return text;
}

export function recordsToCsv(records: readonly ActivityRecord[], includeHeader = true): string {
	const rows = includeHeader ? [CSV_FIELDS.join(',')] : [];
	for (const record of records) rows.push(CSV_FIELDS.map((field) => csvCell(record[field])).join(','));
	return `${rows.join('\r\n')}\r\n`;
}

import { describe, expect, it } from 'vitest';
import { recordForFeedback } from './journalTypes';
import { redactTechnicalDetail } from './redaction';
import type { ParsecEvent, ParsecFeedback } from './types';

describe('Parsec activity redaction', () => {
	it('redacts secret assignments without deleting useful failure context', () => {
		expect(redactTechnicalDetail('HTTP 500 token=abc123 path=C:\\repo\\file.json'))
			.toBe('HTTP 500 token=[REDACTED] path=C:\\repo\\file.json');
		expect(redactTechnicalDetail('Authorization: Bearer station-secret; cookie=session-value'))
			.toBe('Authorization: [REDACTED]; cookie=[REDACTED]');
		expect(redactTechnicalDetail('PASSWORD="do not store" api_key: key-value'))
			.toBe('PASSWORD=[REDACTED] api_key: [REDACTED]');
	});

	it('clamps persisted technical detail to the documented limit', () => {
		expect(redactTechnicalDetail('x'.repeat(8_001))).toHaveLength(8_000);
	});
});

describe('Parsec activity projection', () => {
	it('copies only allowlisted fields and never serializes a lore body', () => {
		const event: ParsecEvent = {
			type: 'search',
			phase: 'completed',
			query: 'radio',
			resultCount: 4,
			tool: 'lore-editor',
			technicalDetail: 'HTTP 200 token=abc123',
		};
		const feedback: ParsecFeedback = {
			id: 7,
			priority: 60,
			at: 123.5,
			text: '*wags her tail excitedly!* Found four records.',
			kind: 'success',
			animation: 'happy',
			tool: 'lore-editor',
			technicalDetail: 'HTTP 200 token=abc123',
			dedupeKey: 'search:radio',
		};
		const context = {
			route: '/lore-editor',
			contextId: 'record:/obj/item/radio',
			durationMs: 42,
			documentBody: 'A complete human-authored lore document that must not persist.',
		};

		const record = recordForFeedback(event, feedback, context);

		expect(record).toEqual({
			schemaVersion: 1,
			id: expect.stringMatching(/^parsec:[0-9a-f-]{36}$/),
			at: 123.5,
			eventType: 'search',
			phase: 'completed',
			tool: 'lore-editor',
			route: '/lore-editor',
			contextId: 'record:/obj/item/radio',
			durationMs: 42,
			resultCount: 4,
			outcome: 'completed',
			technicalDetail: 'HTTP 200 token=[REDACTED]',
			parsecText: '*wags her tail excitedly!* Found four records.',
			reaction: 'happy',
		});
		expect(JSON.stringify(record)).not.toContain('complete human-authored lore document');
		expect(JSON.stringify(record)).not.toContain('documentBody');
	});

	it('clamps Parsec transcript text and normalizes absent context fields', () => {
		const event: ParsecEvent = {
			type: 'notice',
			phase: 'info',
			summary: 'Status',
			tool: null,
		};
		const feedback: ParsecFeedback = {
			id: 8,
			priority: 10,
			at: 124,
			text: 'w'.repeat(1_001),
			kind: 'info',
			animation: 'idle',
			tool: null,
			technicalDetail: null,
			dedupeKey: null,
		};

		const record = recordForFeedback(event, feedback, {});

		expect(record.parsecText).toHaveLength(1_000);
		expect(record.route).toBeNull();
		expect(record.contextId).toBeNull();
		expect(record.durationMs).toBeNull();
		expect(record.resultCount).toBeNull();
		expect(record.outcome).toBe('notice');
	});
});

import { describe, expect, it } from 'vitest';
import type { ParsecEvent, ParsecFeedbackKind } from './types';
import { voiceForEvent } from './voice';

describe('Parsec voice', () => {
	it('cycles reviewed route-specific idle lines before repeating', () => {
		const first = voiceForEvent({ type: 'idle', phase: 'contextual', tool: 'parsec', route: '/lore-editor', lineIndex: 0 });
		const second = voiceForEvent({ type: 'idle', phase: 'contextual', tool: 'parsec', route: '/lore-editor', lineIndex: 1 });
		const wrapped = voiceForEvent({ type: 'idle', phase: 'contextual', tool: 'parsec', route: '/lore-editor', lineIndex: 3 });

		expect(first.text).not.toBe(second.text);
		expect(wrapped.text).toBe(first.text);
		expect(first.text).not.toContain('/obj/');
	});

	it('uses the Content Graph idle copy for its actual /graph route', () => {
		const feedback = voiceForEvent({ type: 'idle', phase: 'contextual', tool: 'parsec', route: '/graph', lineIndex: 0 });

		expect(feedback.text).toContain('*tilts her head at the node map.*');
	});

	it('uses a canine action without changing technical identifiers', () => {
		const feedback = voiceForEvent({
			type: 'fetch',
			phase: 'failed',
			tool: 'lore-editor',
			summary: 'Could not load /obj/item/radio.',
			technicalDetail: 'HTTP 500: /obj/item/radio',
			dedupeKey: 'lore:/obj/item/radio',
		});

		expect(feedback.text).toContain('*growls');
		expect(feedback.technicalDetail).toBe('HTTP 500: /obj/item/radio');
		expect(feedback.text).toContain('/obj/item/radio');
		expect(feedback.text).not.toContain('/obj/item/wadio');
	});

	it('uses the approved empty-search reaction', () => {
		const feedback = voiceForEvent({
			type: 'search',
			phase: 'empty',
			tool: 'global-search',
			query: 'radio',
			resultCount: 0,
			dedupeKey: 'global-search',
		});

		expect(feedback.text).toBe('*tilts her head in confusion.* No matching records in this context.');
		expect(feedback.animation).toBe('confused');
	});

	it('keeps serious validation failures direct while retaining Parsec voice', () => {
		const feedback = voiceForEvent({
			type: 'validation',
			phase: 'blocked',
			tool: 'file-management',
			summary: 'Export refused because the checkout is dirty.',
			technicalDetail: 'Dirty checkout: C:\\Meridian-Rift',
		});

		expect(feedback.text).toBe('*stares disapprovingly.* Export refused because the checkout is dirty.');
		expect(feedback.technicalDetail).toBe('Dirty checkout: C:\\Meridian-Rift');
	});

	it.each<readonly [string, ParsecEvent, ParsecFeedbackKind]>([
		['active search', { type: 'search', phase: 'started', tool: 'global-search', query: 'radio' }, 'info'],
		['completed search', { type: 'search', phase: 'completed', tool: 'global-search', query: 'radio', resultCount: 3 }, 'success'],
		['failed search', { type: 'search', phase: 'failed', tool: 'global-search', query: 'radio', technicalDetail: 'offline' }, 'error'],
		['superseded search', { type: 'search', phase: 'superseded', tool: 'global-search', query: 'radio' }, 'info'],
		['started fetch', { type: 'fetch', phase: 'started', tool: 'lore-editor', summary: 'Loading Radio' }, 'info'],
		['delayed fetch', { type: 'fetch', phase: 'delayed', tool: 'lore-editor', summary: 'Loading Radio' }, 'info'],
		['completed fetch', { type: 'fetch', phase: 'completed', tool: 'lore-editor', summary: 'Loaded Radio' }, 'success'],
		['cancelled fetch', { type: 'fetch', phase: 'cancelled', tool: 'lore-editor', summary: 'Radio load cancelled' }, 'info'],
		['completed mutation', { type: 'mutation', phase: 'completed', tool: 'lore-editor', summary: 'Override saved.' }, 'success'],
		['failed mutation', { type: 'mutation', phase: 'failed', tool: 'lore-editor', summary: 'Save failed.' }, 'error'],
		['active job', { type: 'job', phase: 'started', tool: 'file-management', summary: 'Catalog refresh started.' }, 'info'],
		['job progress', { type: 'job', phase: 'progress', tool: 'file-management', summary: 'Catalog refresh is halfway done.' }, 'info'],
		['completed job', { type: 'job', phase: 'completed', tool: 'file-management', summary: 'Catalog refresh completed.' }, 'success'],
		['failed job', { type: 'job', phase: 'failed', tool: 'file-management', summary: 'Catalog refresh failed.' }, 'error'],
		['initial connection', { type: 'connection', phase: 'connected', tool: 'live' }, 'success'],
		['lost connection', { type: 'connection', phase: 'disconnected', tool: 'live' }, 'error'],
		['polling fallback', { type: 'connection', phase: 'polling', tool: 'live' }, 'warning'],
		['recovered connection', { type: 'connection', phase: 'recovered', tool: 'live' }, 'success'],
		['validation warning', { type: 'validation', phase: 'warning', tool: 'file-management', summary: 'Check the stage hash.' }, 'warning'],
		['failed validation', { type: 'validation', phase: 'failed', tool: 'file-management', summary: 'Stage hash failed.' }, 'error'],
		['ordinary pat', { type: 'interaction', phase: 'pat', tool: 'parsec' }, 'info'],
		['repeated pat', { type: 'interaction', phase: 'repeated-pat', tool: 'parsec' }, 'info'],
		['navigation context', { type: 'navigation', phase: 'context-changed', tool: null, route: '/content-graph' }, 'info'],
		['contextual idle', { type: 'idle', phase: 'contextual', tool: 'parsec', route: '/lore-editor' }, 'info'],
		['compatibility notice', { type: 'notice', phase: 'info', tool: 'parsec', summary: 'Just so you know.' }, 'info'],
		['compatibility success', { type: 'notice', phase: 'success', tool: 'parsec', summary: 'Preview succeeded.' }, 'success'],
		['compatibility error', { type: 'notice', phase: 'error', tool: 'parsec', summary: 'Preview failed.' }, 'error'],
	])('formats %s as an action-led %s message', (_label, event, kind) => {
		const feedback = voiceForEvent(event);

		expect(feedback.kind).toBe(kind);
		expect(feedback.text).toMatch(/^\*[^*]+\*/);
		expect(feedback.text).not.toMatch(/\b[wl]adio\b/i);
	});
});

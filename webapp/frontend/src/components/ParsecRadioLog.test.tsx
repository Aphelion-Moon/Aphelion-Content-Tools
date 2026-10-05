import { render } from 'solid-js/web';
import axe from 'axe-core';
import { afterEach, describe, expect, it } from 'vitest';
import { appendParsecLog, clearParsecLiveLog } from '~/store/appStore';
import type { ParsecFeedback } from '~/lib/parsec/types';
import ParsecRadioLog from './ParsecRadioLog';

function feedback(id: number, kind: ParsecFeedback['kind'] = 'info'): ParsecFeedback {
	return {
		id,
		text: kind === 'error' ? '*growls in frustration.* Could not load entry.' : `*wuffs softly.* Line ${id}`,
		kind,
		animation: kind === 'error' ? 'growl' : 'idle',
		priority: kind === 'error' ? 100 : 10,
		tool: 'lore-editor',
		technicalDetail: kind === 'error' ? 'HTTP 500 secret detail' : null,
		dedupeKey: `line:${id}`,
		at: 100 + id,
	};
}

afterEach(() => {
	clearParsecLiveLog();
	document.body.replaceChildren();
});

describe('Parsec radio log', () => {
	it('shows the newest five lines in compact SS13 radio form', () => {
		for (let id = 1; id <= 6; id += 1) appendParsecLog(feedback(id), `activity-${id}`);
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecRadioLog mode="compact" />, host);

		const log = host.querySelector('[data-parsec-radio-log]');
		expect(log?.querySelectorAll('li')).toHaveLength(5);
		expect(log?.textContent).toContain('Parsec:');
		expect(log?.textContent).toContain('Line 6');
		expect(log?.textContent).not.toContain('Line 1');
		expect(log?.querySelector('time')?.getAttribute('datetime')).toBeTruthy();
		dispose();
	});

	it('expands an actionable error without rendering technical detail as character copy', () => {
		appendParsecLog(feedback(6, 'error'), 'activity-6');
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecRadioLog mode="compact" />, host);

		const log = host.querySelector('[data-parsec-radio-log]');
		expect(log?.getAttribute('data-expanded')).toBe('true');
		expect(log?.querySelector('[role="alert"]')).not.toBeNull();
		expect(log?.querySelector('[data-parsec-copy]')?.textContent).not.toContain('HTTP 500 secret detail');
		expect(log?.textContent).toContain('View technical details in activity history');
		expect(host.querySelector('[data-parsec-balloon]')).toBeNull();
		dispose();
	});

	it('keeps populated error lines as valid list items for axe', async () => {
		appendParsecLog(feedback(6, 'error'), 'activity-6');
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecRadioLog mode="compact" />, host);

		const line = host.querySelector('ol > li');
		expect(line?.getAttribute('role')).toBeNull();
		expect(line?.querySelector('[role="alert"]')).not.toBeNull();
		const accessibility = await axe.run(host, { rules: { 'color-contrast': { enabled: false } } });
		expect(accessibility.violations.filter((violation) => ['aria-allowed-role', 'list'].includes(violation.id))).toEqual([]);
		dispose();
	});

	it('uses one polite live region for the newest ordinary line', () => {
		appendParsecLog(feedback(1), 'activity-1');
		appendParsecLog(feedback(2), 'activity-2');
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecRadioLog mode="compact" />, host);

		expect(host.querySelectorAll('[role="status"]')).toHaveLength(1);
		expect(host.querySelector('[role="status"]')?.getAttribute('aria-live')).toBe('polite');
		dispose();
	});

	it('offers collapsed and expanded transcript presentations', () => {
		for (let id = 1; id <= 6; id += 1) appendParsecLog(feedback(id), `activity-${id}`);
		const collapsedHost = document.createElement('div');
		document.body.append(collapsedHost);
		const disposeCollapsed = render(() => <ParsecRadioLog mode="collapsed" />, collapsedHost);
		expect(collapsedHost.querySelector('[data-parsec-radio-log]')?.getAttribute('data-mode')).toBe('collapsed');
		expect(collapsedHost.querySelector('ol')).toBeNull();
		expect(collapsedHost.textContent).toContain('6 unread');
		disposeCollapsed();

		const expandedHost = document.createElement('div');
		document.body.append(expandedHost);
		const disposeExpanded = render(() => <ParsecRadioLog mode="expanded" />, expandedHost);
		expect(expandedHost.querySelectorAll('li')).toHaveLength(6);
		disposeExpanded();
	});
});

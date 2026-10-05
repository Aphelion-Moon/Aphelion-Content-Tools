import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { flushParsecActivity, reportParsec } from '~/lib/parsec/coordinator';
import { loadCompanionProfile } from '~/lib/parsec/profile';
import ParsecPage from './ParsecPage';

afterEach(() => {
	window.localStorage.clear();
	document.body.replaceChildren();
});

describe('Parsec page', () => {
	it('groups preview actions as compact controls', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecPage />, host);

		const actions = host.querySelector('[role="group"][aria-label="Parsec preview actions"]');
		expect(actions).not.toBeNull();
		expect(actions?.querySelectorAll('button')).toHaveLength(5);
		dispose();
	});

	it('exposes and persists the reduced-motion preference', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecPage />, host);

		const select = host.querySelector<HTMLSelectElement>('select[aria-label="Parsec motion"]');
		expect(select).not.toBeNull();
		expect(Array.from(select!.options, (option) => option.value)).toEqual(['animate', 'reduce']);
		select!.value = 'reduce';
		select!.dispatchEvent(new Event('change', { bubbles: true }));

		expect(loadCompanionProfile().settings.motion).toBe('reduce');
		dispose();
	});

	it('defaults idle chatter to rare and persists an explicit frequency', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecPage />, host);

		const select = host.querySelector<HTMLSelectElement>('select[aria-label="Parsec idle chatter"]');
		expect(select).not.toBeNull();
		expect(select?.value).toBe('rare');
		select!.value = 'frequent';
		select!.dispatchEvent(new Event('change', { bubbles: true }));

		expect(loadCompanionProfile().settings.idleChatter).toBe('frequent');
		dispose();
	});

	it('exposes the approved presence, personality, handling, feedback, audio, accessibility, and data groups', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecPage />, host);
		for (const heading of ['Presence', 'Personality', 'Handling', 'Feedback', 'Audio', 'Accessibility', 'Companion data']) {
			expect(host.textContent).toContain(heading);
		}
		expect(host.querySelector<HTMLSelectElement>('select[aria-label="Parsec presence"]')?.value).toBe('edge-biased');
		expect(host.querySelector<HTMLSelectElement>('select[aria-label="Parsec personality tone"]')?.value).toBe('playful-flirtatious');
		expect(host.querySelector<HTMLSelectElement>('select[aria-label="Parsec handling physics"]')?.value).toBe('gentle-momentum');
		expect(host.querySelector<HTMLInputElement>('input[aria-label="Parsec audio enabled"]')?.checked).toBe(true);
		dispose();
	});

	it('persists intrusive mode and every audio channel as configurable profile settings', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecPage />, host);
		const presence = host.querySelector<HTMLSelectElement>('select[aria-label="Parsec presence"]')!;
		presence.value = 'intrusive';
		presence.dispatchEvent(new Event('change', { bubbles: true }));
		const voice = host.querySelector<HTMLInputElement>('input[aria-label="Parsec voice volume"]')!;
		voice.value = '0.4';
		voice.dispatchEvent(new Event('input', { bubbles: true }));
		const rareIdle = host.querySelector<HTMLInputElement>('input[aria-label="Parsec rare idle volume"]')!;
		rareIdle.value = '0.6';
		rareIdle.dispatchEvent(new Event('input', { bubbles: true }));

		const profile = loadCompanionProfile();
		expect(profile.settings.presence).toBe('intrusive');
		expect(profile.settings.audio.voice).toBe(0.4);
		expect(profile.settings.audio.rareIdle).toBe(0.6);
		dispose();
	});

	it('notifies the mounted radio and idle scheduler when unified feedback settings change', () => {
		const logChanged = vi.fn();
		const idleChanged = vi.fn();
		window.addEventListener('parsec-log-mode-change', logChanged);
		window.addEventListener('parsec-idle-preference-change', idleChanged);
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecPage />, host);
		const logMode = host.querySelector<HTMLSelectElement>('select[aria-label="Parsec chat presentation"]')!;
		logMode.value = 'expanded';
		logMode.dispatchEvent(new Event('change', { bubbles: true }));
		const idle = host.querySelector<HTMLSelectElement>('select[aria-label="Parsec idle chatter"]')!;
		idle.value = 'occasional';
		idle.dispatchEvent(new Event('change', { bubbles: true }));
		expect(logChanged).toHaveBeenCalled();
		expect(idleChanged).toHaveBeenCalled();
		window.removeEventListener('parsec-log-mode-change', logChanged);
		window.removeEventListener('parsec-idle-preference-change', idleChanged);
		dispose();
	});

	it('keeps playful history separate from exact technical diagnostics', async () => {
		reportParsec({
			type: 'job',
			phase: 'failed',
			tool: 'file-management',
			summary: 'Catalog refresh failed.',
			technicalDetail: 'HTTP 500: rebuild-search-embeddings',
		});
		await flushParsecActivity();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecPage />, host);

		for (let attempt = 0; attempt < 20 && !host.textContent?.includes('Catalog refresh failed.'); attempt += 1) {
			await Promise.resolve();
		}
		expect(host.textContent).toContain('*growls angrily at the code.* Catalog refresh failed.');
		expect(host.querySelector('code')?.textContent).toBe('HTTP 500: rebuild-search-embeddings');
		dispose();
	});

	it('links the canonical sprite, asset register, and upstream source', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecPage />, host);
		const links = [...host.querySelectorAll<HTMLAnchorElement>('a')].map((link) => link.getAttribute('href'));

		expect(links).toContain('/references/parsec-asset-register.md');
		expect(links.some((href) => href?.includes('parsec.png'))).toBe(true);
		expect(links).toContain('https://opengameart.org/content/husky-sprites');
		dispose();
	});

	it('keeps companion-profile and activity-history exports separate', () => {
		const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecPage />, host);

		expect(host.querySelector('button[aria-label="Export companion profile"]')).not.toBeNull();
		expect(host.querySelector('button[aria-label="Export activity history as JSON"]')).not.toBeNull();
		expect(host.querySelector<HTMLSelectElement>('select[aria-label="Activity retention"]')?.value).toBe('90');
		host.querySelector<HTMLButtonElement>('button[aria-label="Export companion profile"]')!.click();
		expect(anchorClick).toHaveBeenCalledOnce();
		dispose();
	});

	it('provides one recovery action that returns the bed and cage to habitat defaults', () => {
		const changed = loadCompanionProfile();
		changed.furnishings.bed = { x: 1, y: 0, anchor: 'app-edge' };
		changed.furnishings.cage = { x: 0, y: 1, anchor: 'app-edge' };
		window.localStorage.setItem('aphelion-parsec-profile', JSON.stringify(changed));
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecPage />, host);
		host.querySelector<HTMLButtonElement>('button[aria-label="Return Parsec furniture home"]')?.click();
		const restored = loadCompanionProfile();
		expect(restored.furnishings.bed).toEqual({ x: 0.18, y: 0.76, anchor: 'habitat' });
		expect(restored.furnishings.cage).toEqual({ x: 0.72, y: 0.72, anchor: 'habitat' });
		dispose();
	});
});

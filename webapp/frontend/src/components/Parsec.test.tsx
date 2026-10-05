import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { announceSuccess } from '~/lib/notify';
import { dismissParsec, reportParsec } from '~/lib/parsec/coordinator';
import { clearParsecLiveLog } from '~/store/appStore';
import {
	browserCompanionSnapshot,
	dispatchBrowserCompanionIntent,
	startBrowserCompanionRuntime,
} from '~/lib/parsec/runtime';
import { defaultCompanionProfile, saveCompanionProfile } from '~/lib/parsec/profile';
import Parsec from './Parsec';

function pointerEvent(type: string, values: Record<string, number>): Event {
	const event = new Event(type, { bubbles: true });
	for (const [key, value] of Object.entries(values)) Object.defineProperty(event, key, { value });
	return event;
}

afterEach(() => {
	vi.useRealTimers();
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	dismissParsec();
	clearParsecLiveLog();
	document.body.replaceChildren();
});

describe('Parsec', () => {
	it('follows a sidebar opened after the companion has mounted', async () => {
		saveCompanionProfile(window.localStorage, defaultCompanionProfile());
		const stopRuntime = startBrowserCompanionRuntime();
		const sidebar = document.createElement('aside');
		sidebar.style.visibility = 'hidden';
		const host = document.createElement('div');
		const dispose = render(() => <Parsec />, host);
		sidebar.append(host);
		document.body.append(sidebar);
		const stage = host.querySelector<HTMLElement>('[data-parsec-stage]')!;
		stage.getBoundingClientRect = () => {
			const left = sidebar.dataset.open === 'true' ? 16 : -248;
			return { x: left, y: 200, left, top: 200, width: 230, height: 112, right: left + 230, bottom: 312, toJSON: () => ({}) };
		};
		try {
			await Promise.resolve();
			const actor = document.querySelector<HTMLElement>('[data-parsec-actor]')!;
			expect(actor.style.visibility).toBe('hidden');
			sidebar.dataset.open = 'true';
			sidebar.style.visibility = 'visible';
			await vi.waitFor(() => expect(actor.style.visibility).toBe('visible'));
			expect(actor.querySelector<HTMLElement>('[data-frame-id]')!.style.transform).toBe('translate(16px, 216px)');
			stage.getBoundingClientRect = () => ({ x: 20, y: 180, left: 20, top: 180, width: 230, height: 112, right: 250, bottom: 292, toJSON: () => ({}) });
			sidebar.dispatchEvent(new Event('transitionend', { bubbles: true }));
			expect(actor.querySelector<HTMLElement>('[data-frame-id]')!.style.transform).toBe('translate(20px, 196px)');
		} finally {
			dispose(); stopRuntime(); window.localStorage.clear();
		}
	});

	it('keeps a carried actor outside sidebar clipping and aligned with viewport pointer coordinates', async () => {
		saveCompanionProfile(window.localStorage, defaultCompanionProfile());
		const stopRuntime = startBrowserCompanionRuntime();
		const host = document.createElement('div');
		host.style.transform = 'translateX(0)';
		host.style.overflow = 'hidden';
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);
		const stage = host.querySelector<HTMLElement>('[data-parsec-stage]')!;
		let top = 200;
		stage.getBoundingClientRect = () => ({ x: 16, y: top, left: 16, top, width: 230, height: 112, right: 246, bottom: top + 112, toJSON: () => ({}) });
		try {
			await Promise.resolve();
			const scruff = document.querySelector<HTMLElement>('[data-parsec-scruff]')!;
			const actor = scruff.parentElement!;
			expect(host.contains(actor)).toBe(false);
			expect(actor.style.transform).toBe('translate(16px, 216px)');
			top = 150;
			window.dispatchEvent(new Event('scroll'));
			expect(actor.style.transform).toBe('translate(16px, 166px)');
			scruff.setPointerCapture = () => undefined;
			scruff.releasePointerCapture = () => undefined;
			scruff.dispatchEvent(pointerEvent('pointerdown', { pointerId: 21, clientX: 51, clientY: 206, timeStamp: 0 }));
			await Promise.resolve();
			window.dispatchEvent(pointerEvent('pointermove', { pointerId: 21, clientX: 600, clientY: 300, timeStamp: 100 }));
			expect(actor.style.transform).toBe('translate(565px, 260px)');
			top = 100;
			window.dispatchEvent(new Event('resize'));
			expect(actor.style.transform).toBe('translate(565px, 260px)');
			expect(document.querySelector('[data-parsec-scruff]')).toBe(scruff);
			window.dispatchEvent(pointerEvent('pointercancel', { pointerId: 21, clientX: 600, clientY: 300, timeStamp: 120 }));
			expect(actor.getAttribute('data-held')).toBe('false');
		} finally {
			dispose(); stopRuntime(); window.localStorage.clear();
		}
	});

	it('positions habitat furniture within the stage rather than over the toolbar and radio', async () => {
		saveCompanionProfile(window.localStorage, defaultCompanionProfile());
		const stopRuntime = startBrowserCompanionRuntime();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);
		const bounds = (height: number) => ({ x: 10, y: 100, left: 10, top: 100, width: 300, height, right: 310, bottom: 100 + height, toJSON: () => ({}) });
		host.querySelector<HTMLElement>('[data-parsec-habitat-surface]')!.getBoundingClientRect = () => bounds(400);
		host.querySelector<HTMLElement>('[data-parsec-stage]')!.getBoundingClientRect = () => bounds(112);
		try {
			await dispatchBrowserCompanionIntent({ type: 'go-to-bed', mode: 'voluntary' });
			await Promise.resolve();
			expect(document.querySelector<HTMLElement>('[data-parsec-actor] [data-frame-id]')!.style.transform).toContain('116px');
		} finally {
			dispose(); stopRuntime(); window.localStorage.clear();
		}
	});
	it('routes habitat pats through the runtime invitation and interaction path', async () => {
		saveCompanionProfile(window.localStorage, defaultCompanionProfile());
		const stopRuntime = startBrowserCompanionRuntime();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);
		try {
			host.querySelector<HTMLButtonElement>('button[aria-label="Pat Parsec in her habitat"]')!.click();
			await vi.waitFor(() => expect(host.querySelector('[role="dialog"][aria-label="Parsec excursion invitation"]')).not.toBeNull());
			expect(browserCompanionSnapshot()?.activity).toBe('playing');
		} finally {
			dispose();
			stopRuntime();
			window.localStorage.clear();
		}
	});

	it('reserves enough compact habitat height for the full 96px actor above the toolbar', () => {
		const stopRuntime = startBrowserCompanionRuntime();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);
		try {
			const stage = host.querySelector<HTMLElement>('[data-parsec-stage]')!;
			expect(stage.style.minHeight).toBe('112px');
		} finally {
			dispose();
			stopRuntime();
		}
	});

	it('cancels release motion when a new grab starts', () => {
		vi.spyOn(window, 'requestAnimationFrame').mockImplementation(() => 41);
		const cancelAnimationFrame = vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => undefined);
		const testProfile = defaultCompanionProfile();
		saveCompanionProfile(window.localStorage, {
			...testProfile,
			consent: 'allowed',
			settings: {
				...testProfile.settings,
				handlingPhysics: 'full-tossing',
				audio: { ...testProfile.settings.audio, enabled: false },
			},
		});
		const stopRuntime = startBrowserCompanionRuntime();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);
		try {
			const scruff = document.querySelector<HTMLElement>('[data-parsec-scruff]')!;
			scruff.setPointerCapture = () => undefined;
			scruff.releasePointerCapture = () => undefined;
			scruff.dispatchEvent(pointerEvent('pointerdown', { pointerId: 9, clientX: 100, clientY: 100, timeStamp: 0 }));
			scruff.dispatchEvent(pointerEvent('pointermove', { pointerId: 9, clientX: 220, clientY: 80, timeStamp: 100 }));
			scruff.dispatchEvent(pointerEvent('pointerup', { pointerId: 9, clientX: 260, clientY: 70, timeStamp: 150 }));
			expect(document.querySelector('[data-parsec-actor]')?.getAttribute('data-release-mode')).toBe('full');

			scruff.dispatchEvent(pointerEvent('pointerdown', { pointerId: 10, clientX: 260, clientY: 70, timeStamp: 200 }));

			expect(cancelAnimationFrame).toHaveBeenCalledWith(41);
			expect(document.querySelector('[data-parsec-actor]')?.getAttribute('data-release-mode')).toBe('none');
		} finally {
			dispose();
			stopRuntime();
			window.localStorage.clear();
		}
	});

	it('moves the persistent actor after a full-toss pointer release', async () => {
		const animationFrames: FrameRequestCallback[] = [];
		vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
			animationFrames.push(callback);
			return animationFrames.length;
		});
		vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => undefined);
		const testProfile = defaultCompanionProfile();
		saveCompanionProfile(window.localStorage, {
			...testProfile,
			consent: 'allowed',
			settings: {
				...testProfile.settings,
				handlingPhysics: 'full-tossing',
				audio: { ...testProfile.settings.audio, enabled: false },
			},
		});
		const stopRuntime = startBrowserCompanionRuntime();
		expect(browserCompanionSnapshot()?.settings.handlingPhysics).toBe('full-tossing');
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);
		try {
			const scruff = document.querySelector<HTMLElement>('[data-parsec-scruff]')!;
			scruff.setPointerCapture = () => undefined;
			scruff.releasePointerCapture = () => undefined;
			scruff.dispatchEvent(pointerEvent('pointerdown', { pointerId: 9, clientX: 100, clientY: 100, timeStamp: 0 }));
			scruff.dispatchEvent(pointerEvent('pointermove', { pointerId: 9, clientX: 220, clientY: 80, timeStamp: 100 }));
			scruff.dispatchEvent(pointerEvent('pointerup', { pointerId: 9, clientX: 260, clientY: 70, timeStamp: 150 }));
			const actor = document.querySelector<HTMLElement>('[data-parsec-actor] [data-frame-id]')!;
			const releasedTransform = actor.style.transform;
			expect(document.querySelector('[data-parsec-actor]')?.getAttribute('data-release-mode')).toBe('full');

			expect(animationFrames).toHaveLength(1);
			animationFrames.shift()!(1000);
			expect(animationFrames).toHaveLength(1);
			animationFrames.shift()!(1016);
			expect(actor.style.transform).not.toBe(releasedTransform);
		} finally {
			dispose();
			stopRuntime();
			window.localStorage.clear();
		}
	});

	it('keeps one actor node through habitat pickup, movement, and release', async () => {
		const stopRuntime = startBrowserCompanionRuntime();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);
		try {
			const actor = document.querySelector('[data-parsec-scruff]')?.parentElement;
			expect(actor).not.toBeNull();

			await dispatchBrowserCompanionIntent({ type: 'grabbed', point: { x: 40, y: 40 } });
			await dispatchBrowserCompanionIntent({ type: 'held-moved', point: { x: 180, y: 120 }, movementSpeed: 16 });
			expect(document.querySelector('[data-parsec-scruff]')?.parentElement).toBe(actor);

			await dispatchBrowserCompanionIntent({ type: 'released', point: { x: 180, y: 120 }, velocity: { x: 0, y: 0 } });
			expect(document.querySelectorAll('[data-parsec-scruff]')).toHaveLength(1);
			expect(document.querySelector('[data-parsec-scruff]')?.parentElement).toBe(actor);
		} finally {
			dispose();
			stopRuntime();
		}
	});

	it('continues a live scruff gesture after the grabbed clip moves the hit target', async () => {
		const testProfile = defaultCompanionProfile();
		saveCompanionProfile(window.localStorage, {
			...testProfile,
			consent: 'allowed',
			settings: {
				...testProfile.settings,
				audio: { ...testProfile.settings.audio, enabled: false },
			},
		});
		const stopRuntime = startBrowserCompanionRuntime();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);
		try {
			const scruff = document.querySelector<HTMLElement>('[data-parsec-scruff]')!;
			const actor = scruff.parentElement!;
			scruff.setPointerCapture = () => undefined;
			scruff.releasePointerCapture = () => undefined;
			const beforeMove = actor.style.transform;
			scruff.dispatchEvent(pointerEvent('pointerdown', { pointerId: 12, clientX: 100, clientY: 100, timeStamp: 0 }));
			await new Promise((resolve) => window.setTimeout(resolve, 0));

			expect(document.querySelector('[data-parsec-scruff]')).toBe(scruff);
			expect(actor.getAttribute('data-held')).toBe('true');

			window.dispatchEvent(pointerEvent('pointermove', { pointerId: 12, clientX: 180, clientY: 140, timeStamp: 100 }));
			expect(actor.style.transform).not.toBe(beforeMove);
			window.dispatchEvent(pointerEvent('pointerup', { pointerId: 12, clientX: 180, clientY: 140, timeStamp: 120 }));
			expect(actor.getAttribute('data-held')).toBe('false');
		} finally {
			dispose();
			stopRuntime();
			window.localStorage.clear();
		}
	});

	it('routes the Bed action to saved habitat coordinates while the furnishing is hidden', async () => {
		const testProfile = defaultCompanionProfile();
		saveCompanionProfile(window.localStorage, {
			...testProfile,
			consent: 'allowed',
			settings: {
				...testProfile.settings,
				audio: { ...testProfile.settings.audio, enabled: false },
			},
		});
		const stopRuntime = startBrowserCompanionRuntime();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);
		try {
			const surface = host.querySelector<HTMLElement>('[data-parsec-stage]')!;
			surface.getBoundingClientRect = () => ({
				x: 100, y: 200, left: 100, top: 200, right: 500, bottom: 500, width: 400, height: 300, toJSON: () => ({}),
			});
			await new Promise((resolve) => window.setTimeout(resolve, 0));

			host.querySelector<HTMLButtonElement>('button[aria-label="Go to bed"]')!.click();
			await new Promise((resolve) => window.setTimeout(resolve, 0));

			expect(document.querySelector<HTMLElement>('[data-parsec-actor] [data-frame-id]')?.style.transform)
				.toBe('translate(124px, 380px)');
		} finally {
			dispose();
			stopRuntime();
			window.localStorage.clear();
		}
	});

	it('places Parsec on the bed when she is released over the visible furnishing', async () => {
		const testProfile = defaultCompanionProfile();
		saveCompanionProfile(window.localStorage, {
			...testProfile,
			consent: 'allowed',
			settings: {
				...testProfile.settings,
				handlingPhysics: 'carry-only',
				audio: { ...testProfile.settings.audio, enabled: false },
			},
			furnishings: {
				...testProfile.furnishings,
				bed: { x: 0.5, y: 0.5, anchor: 'app-edge' },
			},
		});
		const stopRuntime = startBrowserCompanionRuntime();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);
		try {
			const bed = document.querySelector<HTMLElement>('[data-furniture-id="bed"]')!;
			bed.getBoundingClientRect = () => ({
				x: 200, y: 140, left: 200, top: 140, right: 264, bottom: 204, width: 64, height: 64, toJSON: () => ({}),
			});
			const scruff = document.querySelector<HTMLElement>('[data-parsec-scruff]')!;
			scruff.setPointerCapture = () => undefined;
			scruff.releasePointerCapture = () => undefined;

			scruff.dispatchEvent(pointerEvent('pointerdown', { pointerId: 14, clientX: 100, clientY: 100, timeStamp: 0 }));
			window.dispatchEvent(pointerEvent('pointermove', { pointerId: 14, clientX: 268, clientY: 208, timeStamp: 100 }));
			window.dispatchEvent(pointerEvent('pointerup', { pointerId: 14, clientX: 268, clientY: 208, timeStamp: 120 }));
			await new Promise((resolve) => window.setTimeout(resolve, 0));

			expect(browserCompanionSnapshot()?.location).toEqual({ kind: 'bed', mode: 'voluntary' });
		} finally {
			dispose();
			stopRuntime();
			window.localStorage.clear();
		}
	});

	it('places and latches Parsec in the cage when she is released over it', async () => {
		const testProfile = defaultCompanionProfile();
		saveCompanionProfile(window.localStorage, {
			...testProfile,
			consent: 'allowed',
			settings: {
				...testProfile.settings,
				handlingPhysics: 'carry-only',
				audio: { ...testProfile.settings.audio, enabled: false },
			},
			furnishings: {
				...testProfile.furnishings,
				cage: { x: 0.5, y: 0.5, anchor: 'app-edge' },
			},
		});
		const stopRuntime = startBrowserCompanionRuntime();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);
		try {
			const cage = document.querySelector<HTMLElement>('[data-furniture-id="cage"]')!;
			cage.getBoundingClientRect = () => ({
				x: 200, y: 140, left: 200, top: 140, right: 264, bottom: 204, width: 64, height: 64, toJSON: () => ({}),
			});
			const scruff = document.querySelector<HTMLElement>('[data-parsec-scruff]')!;
			scruff.setPointerCapture = () => undefined;
			scruff.releasePointerCapture = () => undefined;

			scruff.dispatchEvent(pointerEvent('pointerdown', { pointerId: 15, clientX: 100, clientY: 100, timeStamp: 0 }));
			window.dispatchEvent(pointerEvent('pointermove', { pointerId: 15, clientX: 268, clientY: 208, timeStamp: 100 }));
			window.dispatchEvent(pointerEvent('pointerup', { pointerId: 15, clientX: 268, clientY: 208, timeStamp: 120 }));
			await new Promise((resolve) => window.setTimeout(resolve, 0));

			expect(browserCompanionSnapshot()?.location).toEqual({ kind: 'cage', closed: true });
		} finally {
			dispose();
			stopRuntime();
			window.localStorage.clear();
		}
	});

	it('renders the scruff handling target and eight-action bar before the radio log', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);
		expect(document.querySelector('[data-parsec-scruff]')).not.toBeNull();
		const toolbar = host.querySelector('[data-parsec-toolbar]')!;
		const log = host.querySelector('[data-parsec-radio-log]')!;
		expect(toolbar.querySelectorAll('button')).toHaveLength(8);
		expect(toolbar.compareDocumentPosition(log) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0);
		dispose();
	});

	it('opens a draggable fallback interaction object from a physical toy action', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);
		host.querySelector<HTMLButtonElement>('button[aria-label="Throw ball"]')!.click();
		expect(host.querySelector('[data-parsec-active-tool="ball"]')).not.toBeNull();
		dispose();
	});

	it('moves focus into an opened tool and restores it when Escape closes the tool', async () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);
		const toolbarButton = host.querySelector<HTMLButtonElement>('button[aria-label="Throw ball"]')!;
		toolbarButton.focus();
		toolbarButton.click();
		await Promise.resolve();

		const toy = host.querySelector<HTMLButtonElement>('[data-parsec-active-tool="ball"]')!;
		expect(document.activeElement).toBe(toy);
		toy.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
		await Promise.resolve();

		expect(host.querySelector('[data-parsec-active-tool="ball"]')).toBeNull();
		expect(document.activeElement).toBe(toolbarButton);
		dispose();
	});

	it('offers exactly the three approved excursion choices after the invitation request', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);
		window.dispatchEvent(new Event('parsec-invitation-request'));
		const dialog = host.querySelector('[role="dialog"][aria-label="Parsec excursion invitation"]');
		expect(dialog).not.toBeNull();
		expect([...dialog!.querySelectorAll('button')].map((button) => button.textContent)).toEqual([
			'Allow occasional excursions',
			'Ask each time',
			'Stay in the habitat',
		]);
		dialog!.querySelector<HTMLButtonElement>('button')!.click();
		expect(host.querySelector('[role="dialog"]')).toBeNull();
		dispose();
	});

	it('shows application announcements in the visible radio log', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);

		announceSuccess('Catalog refresh finished.', 'file-management');

		expect(host.textContent).toContain('Catalog refresh finished.');
		dispose();
	});

	it('renders one expanded error line without leaking technical detail into character copy', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);

		reportParsec({
			type: 'fetch',
			phase: 'failed',
			tool: 'lore-editor',
			summary: 'Could not load entry.',
			technicalDetail: 'HTTP 500 secret detail',
			dedupeKey: 'entry:radio',
		});

		const log = host.querySelector('[data-parsec-radio-log]');
		expect(log).not.toBeNull();
		expect(log?.querySelector('[data-parsec-copy]')?.textContent).toContain('*growls');
		expect(log?.querySelector('[data-parsec-copy]')?.textContent).not.toContain('HTTP 500 secret detail');
		expect(log?.querySelector('[role="alert"]')).not.toBeNull();
		expect(log?.getAttribute('data-expanded')).toBe('true');
		expect(host.querySelector('[data-parsec-balloon]')).toBeNull();
		expect(host.querySelector('[data-parsec-stage]')?.getAttribute('data-speaking')).toBe('true');
		dispose();
	});

	it('uses polite status semantics for ordinary feedback', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <Parsec />, host);

		reportParsec({ type: 'notice', phase: 'info', tool: 'parsec', summary: 'Checking the station.' });

		const line = host.querySelector('[data-parsec-radio-log] [role="status"]');
		expect(line).not.toBeNull();
		expect(line?.getAttribute('aria-live')).toBe('polite');
		dispose();
	});
});

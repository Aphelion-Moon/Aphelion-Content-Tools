import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ParsecToolbar from './ParsecToolbar';

afterEach(() => document.body.replaceChildren());

describe('Parsec toolbar', () => {
	it('shows available atlas icons, the selected toy, and a clear unavailable state', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecToolbar onTool={vi.fn()} cageLatched={false} activeTool="ball" />, host);
		const ball = host.querySelector<HTMLButtonElement>('button[aria-label="Throw ball"]')!;
		expect(ball.getAttribute('aria-pressed')).toBe('true');
		expect(ball.querySelector('[data-parsec-object-icon]')?.getAttribute('data-parsec-object-icon')).toBe('tennis-ball');
		expect(host.querySelector('button[aria-label="Play tug"]')?.getAttribute('aria-pressed')).toBe('false');
		dispose();
		const disposeClosed = render(() => <ParsecToolbar onTool={vi.fn()} cageLatched />, host);
		for (const button of host.querySelectorAll<HTMLButtonElement>('button')) {
			if (button.getAttribute('aria-label') === 'Release Parsec') expect(button.disabled).toBe(false);
			else expect(button.disabled).toBe(true);
		}
		expect(host.textContent).toContain('Release Parsec to use toys and interactions.');
		disposeClosed();
	});

	it('renders the approved eight actions in order and dispatches only companion tool IDs', () => {
		const onTool = vi.fn();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecToolbar onTool={onTool} cageLatched={false} />, host);
		const buttons = [...host.querySelectorAll<HTMLButtonElement>('button')];
		for (const button of buttons) {
			expect(button.querySelector('[data-parsec-object-icon], [data-parsec-tool-icon]')).not.toBeNull();
		}
		expect(buttons.map((button) => button.getAttribute('aria-label'))).toEqual([
			'Pat Parsec',
			'Throw ball',
			'Play tug',
			'Brush Parsec',
			'Offer treat',
			'Whistle',
			'Go to bed',
			'Go to cage',
		]);
		buttons[1]!.click();
		expect(onTool.mock.calls[0]?.[0]).toBe('ball');
		dispose();
	});

	it('turns Cage into an explicit Release action while confinement is latched', () => {
		const onTool = vi.fn();
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => <ParsecToolbar onTool={onTool} cageLatched />, host);
		const release = host.querySelector<HTMLButtonElement>('button[aria-label="Release Parsec"]');
		expect(release?.textContent).toContain('Release');
		release?.click();
		expect(onTool.mock.calls[0]?.[0]).toBe('cage');
		dispose();
	});
});

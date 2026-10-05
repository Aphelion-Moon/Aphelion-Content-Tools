import { Route, Router } from '@solidjs/router';
import { render } from 'solid-js/web';
import { afterEach, describe, expect, it } from 'vitest';
import { appState } from '~/store/appStore';
import { dismissParsec } from '~/lib/parsec/coordinator';
import AppShell from './AppShell';

afterEach(() => {
	dismissParsec();
	window.history.replaceState({}, '', '/');
	document.body.replaceChildren();
});

describe('AppShell Parsec context', () => {
	it('publishes the active route as quiet shared context', () => {
		window.history.replaceState({}, '', '/lore-editor');
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<Router><Route path="*" component={() => <AppShell><p>Lore</p></AppShell>} /></Router>
		), host);

		expect(appState.activeRoute).toBe('/lore-editor');
		expect(appState.parsecFeedback).toBeNull();
		expect(host.querySelector('main h1')?.textContent).toBe('Lore Editor');
		expect(host.querySelector('nav [aria-current="page"]')?.getAttribute('href')).toBe('/lore-editor');
		expect(host.querySelectorAll('#global-search')).toHaveLength(1);
		expect(host.querySelector('header[aria-label="Workspace header"] #global-search')).not.toBeNull();
		dispose();
	});
	it('opens navigation and restores the menu button on Escape', () => {
		const host = document.createElement('div');
		document.body.append(host);
		const dispose = render(() => (
			<Router><Route path="*" component={() => <AppShell><p>Content</p></AppShell>} /></Router>
		), host);
		const menu = host.querySelector<HTMLButtonElement>('button[aria-controls="application-sidebar"]');
		expect(menu).not.toBeNull();
		menu!.click();
		expect(menu!.getAttribute('aria-expanded')).toBe('true');
		const navLink = host.querySelector<HTMLAnchorElement>('nav a')!;
		navLink.focus();
		navLink.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
		expect(menu!.getAttribute('aria-expanded')).toBe('false');
		expect(document.activeElement).toBe(menu);
		dispose();
	});
});

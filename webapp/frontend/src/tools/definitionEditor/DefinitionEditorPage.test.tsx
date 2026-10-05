import { Route, Router, useNavigate } from '@solidjs/router';
import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '~/lib/api';
import { dismissParsec } from '~/lib/parsec/coordinator';
import { setDefinitionRuns, setSelectedContext } from '~/store/appStore';
import DefinitionEditorPage from './DefinitionEditorPage';
import type { Definition, DefinitionDraft, SavedDraft } from './types';

vi.mock('./TypePicker', () => ({ default: () => <p>Type catalog</p> }));
const first: Definition = { type_path: '/datum/outfit/first', kind: 'outfit', fields: [{ name: 'name', expression: '"First"', value: 'First', value_known: true, owner_type: '/datum/outfit/first', editable: true, local: true }], procedures: [], references: [] };
const second: Definition = { ...first, type_path: '/datum/outfit/second', fields: [{ ...first.fields![0]!, expression: '"Second"', value: 'Second', owner_type: '/datum/outfit/second' }] };
let dispose: (() => void) | undefined;
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

afterEach(() => { dispose?.(); dispose = undefined; dismissParsec(); setDefinitionRuns([]); setSelectedContext(null); vi.restoreAllMocks(); document.body.replaceChildren(); });

function button(host: HTMLElement, label: string): HTMLButtonElement { const found = [...host.querySelectorAll('button')].find((item) => item.textContent === label); if (!found) throw new Error(`Missing button ${label}`); return found; }
function nameInput(host: HTMLElement): HTMLInputElement { return [...host.querySelectorAll<HTMLInputElement>('input')].find((input) => input.closest('label')?.textContent === 'name')!; }
function enter(input: HTMLInputElement, text: string) { input.value = text; input.dispatchEvent(new InputEvent('input', { bubbles: true })); }

async function mount() {
	vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined);
	window.history.replaceState(null, '', '/outfit-editor?type_path=%2Fdatum%2Foutfit%2Ffirst&catalog_id=catalog-1');
	vi.spyOn(api, 'get').mockImplementation(async (path) => {
		if (path.includes('/status')) return { catalog_id: 'catalog-1', current: true, analyzer_available: true, byond_available: false };
		if (path.includes('/drafts')) return { drafts: [] };
		if (path.includes('/definition?')) return path.includes('second') ? second : first;
		if (path.includes('/references')) return [];
		throw new Error(`Unexpected GET ${path}`);
	});
	const host = document.createElement('div'); document.body.append(host);
	function Harness() { const navigate = useNavigate(); return <><button onClick={() => navigate('/outfit-editor?type_path=%2Fdatum%2Foutfit%2Fsecond&catalog_id=catalog-1')}>Select second by link</button><DefinitionEditorPage kind="outfit" /></>; }
	dispose = render(() => <Router><Route path="*" component={Harness} /></Router>, host);
	await settle(); await settle();
	return host;
}

describe('definition editor draft ownership', () => {
	it('preserves edits made while a previous save is in flight', async () => {
		const host = await mount(); button(host, 'Override').click();
		let finish!: (value: SavedDraft) => void;
		let saving!: DefinitionDraft;
		vi.spyOn(api, 'post').mockImplementation((_path, body) => { saving = (body as { draft: DefinitionDraft }).draft; return new Promise((resolve) => { finish = resolve; }); });
		enter(nameInput(host), 'First saved version'); button(host, 'Save draft').click();
		enter(nameInput(host), 'Newer unsaved version');
		finish({ draft: saving, record_hash: 'saved-hash' }); await settle();
		expect(nameInput(host).value).toBe('Newer unsaved version');
		expect(host.textContent).toContain('newer changes remain unsaved');
	});

	it('keeps the existing draft when navigation is declined and clears it after accepted navigation', async () => {
		const host = await mount(); button(host, 'Override').click(); enter(nameInput(host), 'Unsaved');
		const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
		button(host, 'Select second by link').click(); await settle();
		expect(nameInput(host).value).toBe('Unsaved');
		confirm.mockReturnValue(true); button(host, 'Select second by link').click(); await settle(); await settle();
		expect(host.querySelector('input[aria-label="DM procedure source"]')).toBeNull();
		expect([...host.querySelectorAll('button')].some((item) => item.textContent === 'Save draft')).toBe(false);
		button(host, 'Override').click(); expect(nameInput(host).value).toBe('Second');
	});

	it('keeps draft authoring available while native validation is unavailable', async () => {
		const host = await mount(); button(host, 'Override').click();
		expect(button(host, 'Save draft').disabled).toBe(false);
		expect(host.textContent).toContain('BYOND unavailable');
		const native = [...host.querySelectorAll('button')].filter((item) => /Validate.*compile|Render character|Launch test map/i.test(item.textContent ?? ''));
		expect(native.length).toBeGreaterThan(0); expect(native.every((item) => item.disabled)).toBe(true);
	});
});

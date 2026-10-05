import { render } from 'solid-js/web';
import { afterEach, expect, it, vi } from 'vitest';
import FieldEditor from './Fields';

let dispose: (() => void) | undefined;
afterEach(() => { dispose?.(); document.body.replaceChildren(); });
it('keeps multiline DM expressions intact while editing unsupported source', () => {
	const source = 'list(\n\t/obj/item/wrench = counted_items(),\n\t/obj/item/screwdriver = 1\n)';
	const change = vi.fn();
	const host = document.createElement('div'); document.body.append(host);
	dispose = render(() => <FieldEditor field={{ name: 'custom_contents', expression: source, owner_type: '/datum/outfit', editable: true, value_known: false, local: true }} onChange={change} onPick={() => {}} onInspect={() => {}} onPreview={() => {}} onConstants={() => {}} />, host);
	const input = host.querySelector('textarea');
	expect(input).not.toBeNull();
	expect(input!.value).toBe(source);
	input!.value = source.replace('counted_items()', 'other_count()');
	input!.dispatchEvent(new InputEvent('input', { bubbles: true }));
	expect(change).toHaveBeenCalledWith(source.replace('counted_items()', 'other_count()'));
});

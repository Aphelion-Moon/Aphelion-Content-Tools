import { type JSX, onCleanup, onMount } from 'solid-js';
import styles from './DefinitionEditor.module.css';

export default function PickerDialog(props: { label: string; close: () => void; children: JSX.Element }) {
	let element!: HTMLDivElement;
	const opener = document.activeElement instanceof HTMLElement ? document.activeElement : undefined;
	onMount(() => queueMicrotask(() => element.querySelector<HTMLElement>('input,button')?.focus()));
	onCleanup(() => { if (opener?.isConnected) opener.focus(); });
	function keyboard(event: KeyboardEvent) {
		if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); props.close(); }
		if (event.key !== 'Tab') return;
		const nodes = [...element.querySelectorAll<HTMLElement>('input,button,select,a[href],[tabindex="0"]')].filter((node) => !node.hasAttribute('disabled'));
		const first = nodes[0], last = nodes.at(-1);
		if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
		else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
	}
	return <div class={styles.modalBackdrop}><div ref={element} class={styles.modal} role="dialog" aria-modal="true" aria-label={props.label} onKeyDown={keyboard}>
		<button onClick={props.close}>Close picker</button>{props.children}
	</div></div>;
}

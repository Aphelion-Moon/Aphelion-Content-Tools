import { onCleanup, onMount } from 'solid-js';
import { formatElapsed } from '~/lib/format';

export function startElapsedTicker(
	since: number,
	onTick: (text: string) => void,
	schedule: typeof setInterval = setInterval,
	cancel: typeof clearInterval = clearInterval,
): () => void {
	let now = Date.now() / 1000;
	onTick(formatElapsed(since, now));
	const timer = schedule(() => {
		now += 1;
		onTick(formatElapsed(since, now));
	}, 1_000);
	return () => cancel(timer);
}

/** A compact elapsed-time label that advances locally between backend state updates. */
export default function Elapsed(props: { readonly since: number }) {
	let element!: HTMLSpanElement;
	let stop: () => void = () => undefined;
	onMount(() => {
		stop = startElapsedTicker(props.since, (text) => {
			element.textContent = text;
		});
	});
	onCleanup(() => stop());
	return <span ref={element}>{formatElapsed(props.since)}</span>;
}

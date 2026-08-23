import { Show, createEffect, createSignal, onCleanup, onMount } from 'solid-js';
import { appState } from '~/store/appStore';
import { announce, react } from '~/lib/notify';
import {
	CELL_WIDTH,
	FRAME_INTERVAL_MS,
	FRAME_SETS,
	PATROL_SPEED_PX_PER_TICK,
	TWERK_DURATION_MS,
	advancePatrol,
	nextFrameIndex,
	prefersReducedMotion,
	registerPat,
} from '~/lib/parsecEngine';
import { cx } from '~/lib/cx';
import spriteUrl from '~/assets/parsec.png';
import styles from './Parsec.module.css';

const PAT_LINES = [
	'Rows: counted. Naps: pending.',
	'All quiet on the database front!',
	'*wags tail*',
	'Good data. Good day.',
	'Sniffing for stale fragments...',
];

// Hidden easter egg: enough rapid pats swaps her reaction for "twerking" -- a repurposed leftover
// animation that was mistakenly used as her idle loop before turning out to be a sit-down/stand-up
// transition rather than a genuine cycle.
const TWERK_LINES = [
	"okay THAT'S enough patting",
	'you found the secret. weird flex but ok',
	'*aggressive tail action*',
	"we don't talk about this one",
];

const pick = (lines: readonly string[]) => lines[Math.floor(Math.random() * lines.length)]!;

/**
 * Parsec, living in the sidebar.
 *
 * There is exactly one of her, mounted by AppShell. Pre-rewrite this required a shared object hung off
 * `window` plus a reparenting dance on every navigation, because each SPA page rebuilt its own copy of
 * the sidebar and re-ran the whole script. With a single persistent shell component she simply never
 * unmounts, and her position and animation state survive navigation for free.
 */
export default function Parsec() {
	let boxRef: HTMLDivElement | undefined;
	let spriteRef: HTMLDivElement | undefined;

	const [bubble, setBubble] = createSignal<{ text: string; kind: string } | null>(null);
	let patTimestamps: readonly number[] = [];
	let bubbleTimer: ReturnType<typeof setTimeout> | undefined;
	let lastAnnouncementId = appState.announcements[0]?.id ?? 0;

	createEffect(() => {
		const current = appState.announcements[0];
		if (!current || current.id <= lastAnnouncementId) return;
		lastAnnouncementId = current.id;
		showBubble(current.message, current.kind);
	});

	onMount(() => {
		let frameIndex = 0;
		let lastFrameTime = 0;
		let x = 0;
		let direction: 1 | -1 = 1;
		let rafId = 0;

		const tick = (timestamp: number) => {
			rafId = requestAnimationFrame(tick);
			if (timestamp - lastFrameTime < FRAME_INTERVAL_MS) return;
			lastFrameTime = timestamp;

			const sprite = spriteRef;
			const box = boxRef;
			if (!sprite || !box) return;

			const reduced = prefersReducedMotion();
			const frames = FRAME_SETS[appState.parsecState];

			if (!reduced) {
				frameIndex = nextFrameIndex(frameIndex, frames.length);
				if (appState.parsecState === 'working') {
					const maxX = Math.max(0, box.clientWidth - CELL_WIDTH);
					const next = advancePatrol({ x, direction, maxX, speed: PATROL_SPEED_PX_PER_TICK });
					x = next.x;
					direction = next.direction;
				}
			}

			const frame = frames[reduced ? 0 : frameIndex] ?? frames[0]!;
			sprite.style.backgroundPosition = `-${frame.x}px -${frame.y}px`;
			// The art faces left natively; flip it to face the direction of travel.
			sprite.style.transform = `translateX(${x}px) scaleX(${direction === 1 ? -1 : 1})`;
		};

		rafId = requestAnimationFrame(tick);
		onCleanup(() => cancelAnimationFrame(rafId));
	});

	onCleanup(() => clearTimeout(bubbleTimer));

	function showBubble(text: string, kind: string): void {
		setBubble({ text, kind });
		clearTimeout(bubbleTimer);
		bubbleTimer = setTimeout(() => setBubble(null), 4000);
	}

	function pat(): void {
		const result = registerPat(patTimestamps, performance.now());
		patTimestamps = result.timestamps;
		const line = result.reaction === 'twerking' ? pick(TWERK_LINES) : pick(PAT_LINES);
		react(result.reaction, result.reaction === 'twerking' ? TWERK_DURATION_MS : undefined);
		announce(line, 'info', 'parsec');
		showBubble(line, 'info');
	}

	return (
		<div
			ref={boxRef}
			class={styles.box}
			onClick={pat}
			role="button"
			tabIndex={0}
			aria-label="Parsec. Click to pat her."
			onKeyDown={(event) => {
				if (event.key === 'Enter' || event.key === ' ') {
					event.preventDefault();
					pat();
				}
			}}
		>
			<div ref={spriteRef} class={styles.sprite} style={{ 'background-image': `url(${spriteUrl})` }} />
			<Show when={bubble()}>
				{(current) => (
					<div
						class={cx(
							styles.bubble,
							current().kind === 'success' && styles.bubbleSuccess,
							current().kind === 'error' && styles.bubbleError,
						)}
					>
						{current().text}
					</div>
				)}
			</Show>
		</div>
	);
}

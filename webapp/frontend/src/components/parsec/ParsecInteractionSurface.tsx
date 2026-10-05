import { createSignal, onCleanup, onMount } from 'solid-js';
import type { CompanionIntent, CompanionState } from '~/lib/parsec/companionTypes';
import {
	beginToolInteraction,
	finishToolInteraction,
	updateToolInteraction,
	type ToolInteractionSession,
} from '~/lib/parsec/interactions';
import styles from './ParsecInteractionSurface.module.css';
import ParsecObjectIcon, { PARSEC_TOOL_OBJECTS } from './ParsecObjectIcon';

export type ParsecPhysicalToolId = 'ball' | 'tug' | 'brush' | 'treat';

interface ParsecInteractionSurfaceProps {
	readonly tool: ParsecPhysicalToolId;
	readonly state: CompanionState;
	readonly onIntent: (intent: CompanionIntent) => void;
	readonly onClose: () => void;
}

const LABELS: Record<ParsecPhysicalToolId, string> = {
	ball: 'BALL',
	tug: 'TUG',
	brush: 'BRUSH',
	treat: 'TREAT',
};

export default function ParsecInteractionSurface(props: ParsecInteractionSurfaceProps) {
	const [point, setPoint] = createSignal({ x: 48, y: 40 });
	let session: ToolInteractionSession | null = null;
	let pointerId: number | null = null;
	let captureTarget: HTMLButtonElement | null = null;
	let surfaceRef: HTMLDivElement | undefined;
	let objectRef: HTMLButtonElement | undefined;

	function sample(next = point()) {
		return { point: next, at: performance.now() };
	}

	function dispatch(intents: CompanionIntent[]): void {
		for (const intent of intents) props.onIntent(intent);
	}

	function begin(next = point()): boolean {
		if (session) return true;
		const result = beginToolInteraction(props.tool, props.state, sample(next));
		if (!result.session) return false;
		session = result.session;
		props.onIntent({ type: 'direct-interaction', action: props.tool });
		dispatch(result.intents);
		return true;
	}

	function move(next: { x: number; y: number }): void {
		setPoint(next);
		if (session) dispatch(updateToolInteraction(session, sample(next)));
	}

	function finish(): void {
		const completed = session;
		const captured = pointerId;
		const target = captureTarget;
		session = null;
		pointerId = null;
		captureTarget = null;
		if (captured !== null && target) {
			try { target.releasePointerCapture(captured); } catch { /* Capture may already be lost. */ }
		}
		if (completed) dispatch(finishToolInteraction(completed, sample()));
	}

	onCleanup(() => {
		finish();
		if (props.tool === 'brush') props.onIntent({ type: 'brush-finished', point: point() });
	});

	onMount(() => queueMicrotask(() => objectRef?.focus()));

	function localPoint(event: PointerEvent): { x: number; y: number } {
		const bounds = surfaceRef?.getBoundingClientRect();
		return {
			x: Math.max(0, Math.min(bounds?.width ?? 96, event.clientX - (bounds?.left ?? 0))),
			y: Math.max(0, Math.min(bounds?.height ?? 96, event.clientY - (bounds?.top ?? 0))),
		};
	}

	return (
		<div ref={surfaceRef} class={styles.surface} data-parsec-interaction-surface>
			<button
				ref={objectRef}
				type="button"
				class={styles.object}
				data-parsec-active-tool={props.tool}
				aria-label={`Use Parsec ${props.tool}`}
				disabled={props.state.location.kind === 'cage' && props.state.location.closed}
				aria-description="Drag with a pointer, or press Enter, move with arrow keys, and press Enter again."
				style={{ left: `${point().x}px`, top: `${point().y}px` }}
				onClick={(event) => event.stopPropagation()}
				onPointerDown={(event) => {
					if (event.button > 0 || pointerId !== null) return;
					event.stopPropagation();
					const next = localPoint(event);
					move(next);
					if (!begin(next)) return;
					pointerId = event.pointerId;
					captureTarget = event.currentTarget;
					event.currentTarget.setPointerCapture(event.pointerId);
				}}
				onPointerMove={(event) => {
					if (pointerId !== event.pointerId) return;
					event.stopPropagation();
					move(localPoint(event));
				}}
				onPointerUp={(event) => {
					if (pointerId !== event.pointerId) return;
					event.stopPropagation();
					move(localPoint(event));
					finish();
				}}
				onPointerCancel={() => finish()}
				onLostPointerCapture={() => finish()}
				onKeyDown={(event) => {
					if (event.key === 'Escape') {
						event.preventDefault();
						event.stopPropagation();
						finish();
						props.onClose();
						return;
					}
					if (event.key === 'Enter' || event.key === ' ') {
						event.preventDefault();
						event.stopPropagation();
						if (session) finish();
						else begin();
						return;
					}
					const delta = event.key === 'ArrowLeft' ? { x: -4, y: 0 }
						: event.key === 'ArrowRight' ? { x: 4, y: 0 }
							: event.key === 'ArrowUp' ? { x: 0, y: -4 }
								: event.key === 'ArrowDown' ? { x: 0, y: 4 }
									: null;
					if (!delta) return;
					event.preventDefault();
					event.stopPropagation();
					if (!session && !begin()) return;
					move({ x: point().x + delta.x, y: point().y + delta.y });
				}}
			>
				<ParsecObjectIcon objectId={PARSEC_TOOL_OBJECTS[props.tool]} tool={props.tool} size={48} />
				{LABELS[props.tool]}
			</button>
			<button type="button" class={styles.close} aria-label={`Put away Parsec ${props.tool}`} onClick={(event) => {
				event.stopPropagation();
				finish();
				props.onClose();
			}}>×</button>
		</div>
	);
}

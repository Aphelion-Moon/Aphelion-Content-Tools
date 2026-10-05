import { Show, createEffect, createSignal, onCleanup } from 'solid-js';
import { coreFallbackManifest } from '~/assets/parsec/manifest.v1';
import { resolveClip } from '~/lib/parsec/assets';
import type { CompanionIntent } from '~/lib/parsec/companionTypes';
import type { Point } from '~/lib/parsec/geometry';
import { estimateReleaseVelocity, type GrabPhysics, type PointerSample } from '~/lib/parsec/physics';
import type { ReleaseState } from '~/lib/parsec/physics';
import { isActorAlignedEffect } from '~/lib/parsec/visualEffects';
import styles from './ParsecSprite.module.css';

interface ParsecSpriteProps {
	readonly clipId: string;
	readonly clipInstance?: number;
	readonly effectClipId?: string | null;
	readonly direction?: string;
	readonly point: Point;
	readonly onPointChange?: (point: Point) => void;
	readonly onRelease?: (release: ReleaseState) => void;
	readonly handlingPhysics: 'carry-only' | 'gentle-momentum' | 'full-tossing';
	readonly reducedMotion: boolean;
	readonly confined: boolean;
	readonly dispatch: (intent: CompanionIntent) => void;
}

function physicsMode(props: ParsecSpriteProps): GrabPhysics {
	if (props.reducedMotion || props.handlingPhysics === 'carry-only') return 'carry-only';
	return props.handlingPhysics === 'full-tossing' ? 'full' : 'gentle';
}

export default function ParsecSprite(props: ParsecSpriteProps) {
	const [held, setHeld] = createSignal(false);
	const [frameIndex, setFrameIndex] = createSignal(0);
	const [effectFrameIndex, setEffectFrameIndex] = createSignal(0);
	let activePointer: number | null = null;
	let captureTarget: HTMLElement | null = null;
	let origin = props.point;
	let grabOffset = { x: 0, y: 0 };
	let samples: PointerSample[] = [];

	function detachPointerListeners(): void {
		window.removeEventListener('pointermove', move);
		window.removeEventListener('pointerup', finish);
		window.removeEventListener('pointercancel', finish);
	}

	function attachPointerListeners(): void {
		detachPointerListeners();
		window.addEventListener('pointermove', move);
		window.addEventListener('pointerup', finish);
		window.addEventListener('pointercancel', finish);
	}

	function releaseCapture(): void {
		const pointer = activePointer;
		const target = captureTarget;
		activePointer = null;
		captureTarget = null;
		detachPointerListeners();
		if (pointer !== null) target?.releasePointerCapture(pointer);
	}

	onCleanup(releaseCapture);

	const clip = () => resolveClip(props.clipId, coreFallbackManifest);
	const directionVariant = () => {
		const currentClip = clip();
		const direction = props.direction ?? currentClip.defaultDirection;
		return direction ? currentClip.directionVariants?.[direction] : undefined;
	};
	const playbackFrames = () => directionVariant()?.frames ?? clip().frames;
	const frameId = () => props.reducedMotion
		? directionVariant()?.reducedMotionFrame ?? clip().reducedMotionFrame
		: playbackFrames()[frameIndex() % playbackFrames().length]!;
	const frame = () => coreFallbackManifest.frames[frameId()]!;
	const sheet = () => coreFallbackManifest.sheets[frame().sheetId]!;
	const scruff = () => frame().anchors.scruff ?? { x: frame().width / 2, y: frame().height / 4 };
	const effectClip = () => props.effectClipId ? resolveClip(props.effectClipId, coreFallbackManifest) : null;
	const effectFrameId = () => {
		const current = effectClip();
		if (!current) return null;
		return props.reducedMotion
			? current.reducedMotionFrame
			: current.frames[effectFrameIndex() % current.frames.length]!;
	};
	const effectFrame = () => {
		const id = effectFrameId();
		return id ? coreFallbackManifest.frames[id] : null;
	};
	const effectSheet = () => {
		const current = effectFrame();
		return current ? coreFallbackManifest.sheets[current.sheetId] : null;
	};
	const effectOffset = () => {
		const id = props.effectClipId;
		if (!id || isActorAlignedEffect(id)) return { x: 0, y: 0 };
		const anchor = frame().anchors.effect ?? { x: 48, y: 48 };
		return { x: anchor.x - 48, y: anchor.y - 48 };
	};

	createEffect(() => {
		const currentClip = clip();
		const instance = props.clipInstance;
		const finished = () => props.dispatch({ type: 'clip-finished', clipId: currentClip.id, ...(instance === undefined ? {} : { instance }) });
		const currentVariant = directionVariant();
		const currentFrames = currentVariant?.frames ?? currentClip.frames;
		const currentDurations = currentVariant?.durationsMs ?? currentClip.durationsMs;
		const reduceMotion = props.reducedMotion;
		setFrameIndex(0);
		let timer: ReturnType<typeof setTimeout> | null = null;
		onCleanup(() => { if (timer !== null) clearTimeout(timer); });
		if (reduceMotion) {
			if (currentClip.loopMode === 'once') {
				timer = setTimeout(
					finished,
					currentDurations.reduce((total, duration) => total + duration, 0),
				);
			}
			return;
		}
		const advance = (currentIndex: number) => {
			timer = setTimeout(() => {
				if (currentIndex >= currentFrames.length - 1) {
					if (currentClip.loopMode === 'once') finished();
					if (currentClip.loopMode !== 'loop') return;
					setFrameIndex(0);
					advance(0);
				} else {
					const nextIndex = currentIndex + 1;
					setFrameIndex(nextIndex);
					advance(nextIndex);
				}
			}, currentDurations[currentIndex] ?? 150);
		};
		advance(0);
	});

	createEffect(() => {
		const current = effectClip();
		const reduceMotion = props.reducedMotion;
		setEffectFrameIndex(0);
		if (!current || reduceMotion) return;
		let timer: ReturnType<typeof setTimeout> | null = null;
		const advance = (currentIndex: number) => {
			timer = setTimeout(() => {
				if (currentIndex >= current.frames.length - 1) {
					if (current.loopMode !== 'loop') return;
					setEffectFrameIndex(0);
					advance(0);
					return;
				}
				const nextIndex = currentIndex + 1;
				setEffectFrameIndex(nextIndex);
				advance(nextIndex);
			}, current.durationsMs[currentIndex] ?? 150);
		};
		advance(0);
		onCleanup(() => { if (timer !== null) clearTimeout(timer); });
	});

	function sample(event: PointerEvent): PointerSample {
		return { point: { x: event.clientX, y: event.clientY }, at: event.timeStamp };
	}

	function begin(event: PointerEvent): void {
		if (props.confined || activePointer !== null) return;
		activePointer = event.pointerId;
		origin = props.point;
		grabOffset = { x: event.clientX - props.point.x, y: event.clientY - props.point.y };
		samples = [sample(event)];
		setHeld(true);
		captureTarget = event.currentTarget as HTMLElement;
		captureTarget.setPointerCapture(event.pointerId);
		attachPointerListeners();
		props.dispatch({ type: 'grabbed', point: props.point, movementSpeed: 0, repeatCount: 0, initiatedPlay: false });
	}

	function move(event: PointerEvent): void {
		if (activePointer !== event.pointerId) return;
		const nextSample = sample(event);
		samples = [...samples, nextSample].filter((entry) => nextSample.at - entry.at <= 200).slice(-6);
		const nextPoint = { x: nextSample.point.x - grabOffset.x, y: nextSample.point.y - grabOffset.y };
		props.onPointChange?.(nextPoint);
		const velocity = estimateReleaseVelocity(samples, physicsMode(props));
		props.dispatch({ type: 'held-moved', point: nextPoint, movementSpeed: Math.hypot(velocity.x, velocity.y) });
	}

	function finish(event: PointerEvent): void {
		if (activePointer !== event.pointerId) return;
		const cancelled = event.type === 'pointercancel';
		const finalSample = cancelled ? samples[samples.length - 1]! : sample(event);
		samples = [...samples, finalSample].filter((entry) => finalSample.at - entry.at <= 200).slice(-6);
		const finalPoint = { x: finalSample.point.x - grabOffset.x, y: finalSample.point.y - grabOffset.y };
		props.onPointChange?.(finalPoint);
		const velocity = cancelled ? { x: 0, y: 0 } : estimateReleaseVelocity(samples, physicsMode(props));
		releaseCapture();
		setHeld(false);
		props.dispatch({ type: 'released', point: finalPoint, velocity });
		props.onRelease?.({ point: finalPoint, velocity });
	}

	function keyboard(event: KeyboardEvent): void {
		if (props.confined) return;
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			if (!held()) {
				origin = props.point;
				setHeld(true);
				props.dispatch({ type: 'grabbed', point: props.point, initiatedPlay: false });
			} else {
				releaseCapture();
				setHeld(false);
				props.dispatch({ type: 'released', point: props.point, velocity: { x: 0, y: 0 } });
				props.onRelease?.({ point: props.point, velocity: { x: 0, y: 0 } });
			}
			return;
		}
		if (event.key === 'Escape' && held()) {
			event.preventDefault();
			releaseCapture();
			setHeld(false);
			props.onPointChange?.(origin);
			props.dispatch({ type: 'released', point: origin, velocity: { x: 0, y: 0 } });
			props.onRelease?.({ point: origin, velocity: { x: 0, y: 0 } });
			return;
		}
		if (!held()) return;
		const offsets: Partial<Record<string, Point>> = {
			ArrowLeft: { x: -8, y: 0 },
			ArrowRight: { x: 8, y: 0 },
			ArrowUp: { x: 0, y: -8 },
			ArrowDown: { x: 0, y: 8 },
		};
		const offset = offsets[event.key];
		if (!offset) return;
		event.preventDefault();
		const next = { x: props.point.x + offset.x, y: props.point.y + offset.y };
		props.onPointChange?.(next);
		props.dispatch({ type: 'held-moved', point: next, movementSpeed: 0 });
	}

	return (
		<div
			class={styles.actor}
			data-frame-id={frameId()}
			data-held={held() ? 'true' : 'false'}
			style={{
				transform: `translate(${props.point.x}px, ${props.point.y}px)`,
				width: `${frame().width}px`,
				height: `${frame().height}px`,
				'background-image': `url(${sheet().src})`,
				'background-position': `-${frame().x}px -${frame().y}px`,
			}}
		>
			<Show when={effectFrame() && effectSheet()}>
				<div
					class={styles.effect}
					data-parsec-effect-frame={effectFrameId()!}
					aria-hidden="true"
					style={{
						'pointer-events': 'none',
						left: `${effectOffset().x}px`,
						top: `${effectOffset().y}px`,
						width: `${effectFrame()!.width}px`,
						height: `${effectFrame()!.height}px`,
						'background-image': `url(${effectSheet()!.src})`,
						'background-position': `-${effectFrame()!.x}px -${effectFrame()!.y}px`,
					}}
				/>
			</Show>
			<div
				class={styles.scruff}
				data-parsec-scruff
				role="button"
				tabIndex={props.confined ? -1 : 0}
				aria-label={props.confined ? 'Parsec is inside her closed cage' : 'Pick Parsec up by her scruff'}
				style={{
					left: `${scruff().x - 20}px`,
					top: `${scruff().y - 12}px`,
					width: '40px',
					height: '36px',
				}}
				onPointerDown={begin}
				onKeyDown={keyboard}
				onClick={(event) => event.stopPropagation()}
			/>
		</div>
	);
}

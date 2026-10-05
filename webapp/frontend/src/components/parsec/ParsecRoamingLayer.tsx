import { For, Show, createMemo, onCleanup, type JSX } from 'solid-js';
import { coreFallbackManifest } from '~/assets/parsec/manifest.v1';
import type { ExcursionConsent } from '~/lib/parsec/companionTypes';
import {
	moveFurniture,
	moveFurnitureByKeyboard,
	type FurnitureId,
	type FurnitureState,
} from '~/lib/parsec/furniture';
import styles from './ParsecRoamingLayer.module.css';

interface ParsecRoamingLayerProps {
	readonly furniture: FurnitureState;
	readonly onFurnitureChange: (state: FurnitureState) => void;
	readonly consent?: ExcursionConsent;
	readonly companion?: JSX.Element;
	readonly space?: 'viewport' | 'habitat';
}

export default function ParsecRoamingLayer(props: ParsecRoamingLayerProps) {
	let active: { id: FurnitureId; pointerId: number; grabOffset: { x: number; y: number } } | null = null;
	let captureTarget: HTMLElement | null = null;
	let layerRef: HTMLDivElement | undefined;
	const space = () => props.space ?? 'viewport';
	const furnitureIds = createMemo(() => (['bed', 'cage'] as const).filter((id) => (
		props.furniture[id].anchor === (space() === 'viewport' ? 'app-edge' : 'habitat')
	)));
	const objectId = (id: FurnitureId) => {
		if (id === 'bed') return 'dogbed';
		const status = props.furniture.cage.status;
		if (status.endsWith('occupied')) return 'cage-occupied';
		return status.startsWith('latched') ? 'cage-locked' : 'cage-open';
	};

	function begin(id: FurnitureId, event: PointerEvent): void {
		const target = event.currentTarget as HTMLElement;
		const bounds = target.getBoundingClientRect();
		active = {
			id,
			pointerId: event.pointerId,
			grabOffset: {
				x: event.clientX - (bounds.left + bounds.width / 2),
				y: event.clientY - (bounds.top + bounds.height / 2),
			},
		};
		captureTarget = target;
		captureTarget.setPointerCapture(event.pointerId);
		attachPointerListeners();
	}

	function detachPointerListeners(): void {
		window.removeEventListener('pointermove', move);
		window.removeEventListener('pointerup', finish);
		window.removeEventListener('pointercancel', cancel);
	}

	function attachPointerListeners(): void {
		detachPointerListeners();
		window.addEventListener('pointermove', move);
		window.addEventListener('pointerup', finish);
		window.addEventListener('pointercancel', cancel);
	}

	onCleanup(detachPointerListeners);

	function move(event: PointerEvent): void {
		if (!active || active.pointerId !== event.pointerId) return;
		const habitatBounds = document.querySelector<HTMLElement>('[data-parsec-stage]')?.getBoundingClientRect();
		const insideHabitat = Boolean(habitatBounds
			&& event.clientX >= habitatBounds.left
			&& event.clientX <= habitatBounds.right
			&& event.clientY >= habitatBounds.top
			&& event.clientY <= habitatBounds.bottom);
		const anchor = insideHabitat ? 'habitat' : 'app-edge';
		const bounds = insideHabitat && habitatBounds
			? habitatBounds
			: { left: 0, top: 0, width: window.innerWidth, height: window.innerHeight };
		const center = {
			x: event.clientX - active.grabOffset.x,
			y: event.clientY - active.grabOffset.y,
		};
		props.onFurnitureChange(moveFurniture(
			props.furniture,
			active.id,
			{
				x: Math.min(1, Math.max(0, (center.x - bounds.left) / Math.max(1, bounds.width))),
				y: Math.min(1, Math.max(0, (center.y - bounds.top) / Math.max(1, bounds.height))),
			},
			anchor,
		));
	}

	function finish(event: PointerEvent): void {
		if (!active || active.pointerId !== event.pointerId) return;
		const habitatBounds = document.querySelector<HTMLElement>('[data-parsec-stage]')?.getBoundingClientRect();
		const insideHabitat = Boolean(habitatBounds
			&& event.clientX >= habitatBounds.left
			&& event.clientX <= habitatBounds.right
			&& event.clientY >= habitatBounds.top
			&& event.clientY <= habitatBounds.bottom);
		const anchor = insideHabitat ? 'habitat' : 'app-edge';
		const bounds = insideHabitat && habitatBounds
			? habitatBounds
			: { left: 0, top: 0, width: window.innerWidth, height: window.innerHeight };
		const center = {
			x: event.clientX - active.grabOffset.x,
			y: event.clientY - active.grabOffset.y,
		};
		props.onFurnitureChange(moveFurniture(
			props.furniture,
			active.id,
			{
				x: Math.min(1, Math.max(0, (center.x - bounds.left) / Math.max(1, bounds.width))),
				y: Math.min(1, Math.max(0, (center.y - bounds.top) / Math.max(1, bounds.height))),
			},
			anchor,
		));
		captureTarget?.releasePointerCapture(event.pointerId);
		captureTarget = null;
		detachPointerListeners();
		active = null;
	}

	function cancel(event: PointerEvent): void {
		if (!active || active.pointerId !== event.pointerId) return;
		captureTarget?.releasePointerCapture(event.pointerId);
		captureTarget = null;
		detachPointerListeners();
		active = null;
	}

	function moveByKeyboard(id: FurnitureId, event: KeyboardEvent): void {
		const direction = event.key === 'ArrowLeft' ? { x: -1, y: 0 }
			: event.key === 'ArrowRight' ? { x: 1, y: 0 }
				: event.key === 'ArrowUp' ? { x: 0, y: -1 }
					: event.key === 'ArrowDown' ? { x: 0, y: 1 }
						: null;
		if (!direction) return;
		event.preventDefault();
		event.stopPropagation();
		props.onFurnitureChange(moveFurnitureByKeyboard(props.furniture, id, direction));
	}

	return (
		<div
			ref={layerRef}
			class={space() === 'viewport' ? styles.layer : styles.habitatLayer}
			data-parsec-roaming-layer
			data-space={space()}
			data-excursions-allowed={props.consent === 'allowed' ? 'true' : 'false'}
			style={{ 'pointer-events': 'none' }}
			aria-hidden="false"
		>
			{props.companion}
			<For each={furnitureIds()}>
				{(id) => {
					const position = () => props.furniture[id].position;
					const asset = () => coreFallbackManifest.objects[objectId(id)]!;
					const frame = () => {
						const frameId = asset().frameId;
						return frameId === null ? undefined : coreFallbackManifest.frames[frameId];
					};
					const sheet = () => frame() ? coreFallbackManifest.sheets[frame()!.sheetId] : undefined;
					return (
						<button
							type="button"
							class={styles.furniture}
							data-furniture-id={id}
							data-furniture-control
							aria-label={`Move Parsec ${id}`}
							style={{
								left: `${position().x * 100}%`,
								top: `${position().y * 100}%`,
								'touch-action': 'none',
								'pointer-events': 'auto',
							}}
							onPointerDown={(event) => begin(id, event)}
							onKeyDown={(event) => moveByKeyboard(id, event)}
							onClick={(event) => event.stopPropagation()}
						>
							<span class={styles.artViewport} aria-hidden="true">
								<Show
									when={frame() && sheet()}
									fallback={<span class={styles.fallbackArt} data-fallback-art>{asset().fallbackLabel}</span>}
							>
									<span
										class={styles.objectArt}
										data-frame-id={asset().frameId!}
										style={{
											width: `${frame()!.width}px`,
											height: `${frame()!.height}px`,
											'background-image': `url(${sheet()!.src})`,
											'background-position': `-${frame()!.x}px -${frame()!.y}px`,
										}}
									/>
								</Show>
							</span>
						</button>
					);
				}}
			</For>
		</div>
	);
}

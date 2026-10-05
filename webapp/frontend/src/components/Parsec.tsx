import { Show, createSignal, onCleanup, onMount } from 'solid-js';
import { Portal } from 'solid-js/web';
import { appState } from '~/store/appStore';
import { reportParsec } from '~/lib/parsec/coordinator';
import {
	prefersReducedMotion,
	registerPat,
	resolveState,
} from '~/lib/parsecEngine';
import { coreFallbackManifest } from '~/assets/parsec/manifest.v1';
import { readParsecLogMode } from '~/lib/parsec/settings';
import { loadCompanionProfile, saveCompanionProfile } from '~/lib/parsec/profile';
import type { FurnitureState } from '~/lib/parsec/furniture';
import ParsecRadioLog from './ParsecRadioLog';
import ParsecHabitat from './parsec/ParsecHabitat';
import ParsecToolbar, { type ParsecToolId } from './parsec/ParsecToolbar';
import ParsecSprite from './parsec/ParsecSprite';
import {
	browserCompanionSnapshot,
	dispatchBrowserCompanionIntent,
	interactWithBrowserCompanion,
	subscribeBrowserCompanionState,
} from '~/lib/parsec/runtime';
import { initialCompanionState } from '~/lib/parsec/companionReducer';
import type { CompanionIntent, ExcursionConsent } from '~/lib/parsec/companionTypes';
import ParsecRoamingLayer from './parsec/ParsecRoamingLayer';
import ParsecInteractionSurface, { type ParsecPhysicalToolId } from './parsec/ParsecInteractionSurface';
import { chooseOrdinaryPerch, collectSafeRegions } from '~/lib/parsec/safeRegions';
import { effectForCompanionClip } from '~/lib/parsec/visualEffects';
import { actorPointFromLocation, directionForMovement, shouldChooseActorDestination } from '~/lib/parsec/actorMotion';
import { createReleaseSimulation } from '~/lib/parsec/actorMotion';
import type { GrabPhysics, ReleaseState } from '~/lib/parsec/physics';
import { clampPoint, pointInRect } from '~/lib/parsec/geometry';
import styles from './Parsec.module.css';

const PARSEC_ACTOR_SIZE = 96;
const COMPACT_HABITAT_CLEARANCE = 16;
const COMPACT_HABITAT_STAGE_HEIGHT = PARSEC_ACTOR_SIZE + COMPACT_HABITAT_CLEARANCE;

/**
 * Parsec, living in the sidebar.
 *
 * There is exactly one of her, mounted by AppShell. Pre-rewrite this required a shared object hung off
 * `window` plus a reparenting dance on every navigation, because each SPA page rebuilt its own copy of
 * the sidebar and re-ran the whole script. With a single persistent shell component she simply never
 * unmounts, and her position and animation state survive navigation for free.
 */
export default function Parsec() {
	let stageRef: HTMLDivElement | undefined;
	const [habitatVisible, setHabitatVisible] = createSignal(true);
	let patTimestamps: readonly number[] = [];
	const [logMode, setLogMode] = createSignal(readParsecLogMode());
	const [profile, setProfile] = createSignal(loadCompanionProfile());
	const [companionState, setCompanionState] = createSignal(
		browserCompanionSnapshot() ?? initialCompanionState({
			consent: profile().consent,
			familiarity: profile().familiarity.band,
			settings: profile().settings,
		}),
	);
	const [invitationOpen, setInvitationOpen] = createSignal(false);
	const [actorPoint, updateActorPoint] = createSignal({ x: 12, y: 12 });
	const [actorDirection, setActorDirection] = createSignal('east');
	const [actorDiagonalDirection, setActorDiagonalDirection] = createSignal('south-east');
	const setActorPoint = (point: { x: number; y: number }) => {
		const previous = actorPoint();
		const cardinal = directionForMovement(previous, point);
		const diagonal = directionForMovement(previous, point, true);
		if (cardinal) setActorDirection(cardinal);
		if (diagonal) setActorDiagonalDirection(diagonal);
		updateActorPoint(point);
	};
	const [activeTool, setActiveTool] = createSignal<ParsecPhysicalToolId | null>(null);
	const [releaseMode, setReleaseMode] = createSignal<GrabPhysics | null>(null);
	let activeToolTrigger: HTMLButtonElement | null = null;
	let previousLocation = companionState().location;
	let releaseFrame: number | null = null;

	function grabPhysics(): GrabPhysics {
		if (prefersReducedMotion(profile().settings.motion) || profile().settings.handlingPhysics === 'carry-only') {
			return 'carry-only';
		}
		return profile().settings.handlingPhysics === 'full-tossing' ? 'full' : 'gentle';
	}

	function stopReleaseMotion(): void {
		if (releaseFrame === null) return;
		window.cancelAnimationFrame(releaseFrame);
		releaseFrame = null;
	}

	function furnitureDropTarget(point: { x: number; y: number }): 'bed' | 'cage' | null {
		const actorCenter = { x: point.x + 48, y: point.y + 48 };
		for (const id of ['bed', 'cage'] as const) {
			const controls = document.querySelectorAll<HTMLElement>(`[data-furniture-id="${id}"]`);
			for (const control of controls) {
				const bounds = control.getBoundingClientRect();
				if (bounds.width <= 0 || bounds.height <= 0) continue;
				if (pointInRect(actorCenter, { x: bounds.left, y: bounds.top, width: bounds.width, height: bounds.height })) {
					return id;
				}
			}
		}
		return null;
	}

	function placeOnFurniture(point: { x: number; y: number }): boolean {
		const target = furnitureDropTarget(point);
		if (!target) return false;
		setReleaseMode(null);
		setActorPoint(furniturePoint(target));
		if (target === 'bed') {
			void dispatchBrowserCompanionIntent({ type: 'go-to-bed', mode: 'voluntary' });
		} else {
			void (async () => {
				await dispatchBrowserCompanionIntent({ type: 'go-to-cage' });
				await dispatchBrowserCompanionIntent({ type: 'set-cage-latch', closed: true });
			})();
		}
		return true;
	}

	function startReleaseMotion(release: ReleaseState): void {
		stopReleaseMotion();
		if (placeOnFurniture(release.point)) return;
		const mode = grabPhysics();
		setReleaseMode(mode);
		const simulation = createReleaseSimulation(release, {
			x: 0,
			y: 0,
			width: Math.max(0, window.innerWidth - 96),
			height: Math.max(0, window.innerHeight - 96),
		}, mode);
		if (mode === 'carry-only') {
			const settled = simulation.advance(0);
			setActorPoint(settled.point);
			void dispatchBrowserCompanionIntent({ type: 'motion-settled', point: settled.point });
			setReleaseMode(null);
			return;
		}
		let previousTimestamp: number | null = null;
		const advance = (timestamp: number) => {
			const elapsedSeconds = previousTimestamp === null ? 0 : Math.max(0, (timestamp - previousTimestamp) / 1000);
			previousTimestamp = timestamp;
			const snapshot = simulation.advance(elapsedSeconds);
			setActorPoint(snapshot.point);
			if (snapshot.settled) {
				releaseFrame = null;
				setReleaseMode(null);
				if (placeOnFurniture(snapshot.point)) return;
				void dispatchBrowserCompanionIntent({ type: 'motion-settled', point: snapshot.point });
				return;
			}
			releaseFrame = window.requestAnimationFrame(advance);
		};
		releaseFrame = window.requestAnimationFrame(advance);
	}

	function dispatchActorIntent(intent: CompanionIntent): void {
		if (intent.type === 'grabbed') {
			stopReleaseMotion();
			setReleaseMode(null);
		}
		void dispatchBrowserCompanionIntent(intent);
	}

	function habitatPoint(): { x: number; y: number } {
		const bounds = stageRef?.getBoundingClientRect();
		if (!bounds) return { x: 12, y: 12 };
		return { x: bounds.left, y: bounds.top + Math.max(0, bounds.height - PARSEC_ACTOR_SIZE) };
	}

	function anchoredToHabitat(): boolean {
		const location = companionState().location;
		return location.kind === 'habitat'
			|| ((location.kind === 'bed' || location.kind === 'cage') && profile().furnishings[location.kind].anchor === 'habitat');
	}

	function syncHabitatPlacement(): void {
		if (!stageRef) return;
		const bounds = stageRef.getBoundingClientRect();
		setHabitatVisible(getComputedStyle(stageRef).visibility !== 'hidden'
			&& bounds.right > 0 && bounds.left < window.innerWidth
			&& bounds.bottom > 0 && bounds.top < window.innerHeight);
		const location = companionState().location;
		if (location.kind === 'habitat') setActorPoint(habitatPoint());
		else if (location.kind === 'bed' || location.kind === 'cage') setActorPoint(furniturePoint(location.kind));
	}

	function furniturePoint(id: 'bed' | 'cage'): { x: number; y: number } {
		const furnishing = profile().furnishings[id];
		const habitatBounds = document.querySelector<HTMLElement>('[data-parsec-stage]')?.getBoundingClientRect();
		const bounds = furnishing.anchor === 'habitat' && habitatBounds
			? habitatBounds
			: { left: 0, top: 0, width: window.innerWidth, height: window.innerHeight };
		if (bounds.width <= 0 || bounds.height <= 0) return habitatPoint();
		return clampPoint({
			x: bounds.left + furnishing.x * bounds.width - PARSEC_ACTOR_SIZE / 2,
			y: bounds.top + furnishing.y * bounds.height - PARSEC_ACTOR_SIZE / 2,
		}, {
			x: bounds.left,
			y: bounds.top,
			width: Math.max(0, bounds.width - PARSEC_ACTOR_SIZE),
			height: Math.max(0, bounds.height - PARSEC_ACTOR_SIZE),
		});
	}

	function chooseDestination(nextState: ReturnType<typeof companionState>): void {
		const directPoint = actorPointFromLocation(nextState.location);
		if (directPoint) {
			setActorPoint(directPoint);
			previousLocation = nextState.location;
			return;
		}
		if (!shouldChooseActorDestination(previousLocation, nextState.location)) {
			previousLocation = nextState.location;
			return;
		}
		if (nextState.location.kind === 'perch') {
			const safe = chooseOrdinaryPerch(
				collectSafeRegions(document),
				{ width: 96, height: 96 },
				{ next: Math.random },
			);
			if (safe) setActorPoint(safe);
		} else {
			// Read the current location after layout; a pickup may have superseded this destination.
			queueMicrotask(syncHabitatPlacement);
		}
		previousLocation = nextState.location;
	}

	onMount(() => {
		const syncLogMode = () => setLogMode(readParsecLogMode());
		const syncProfile = () => setProfile(loadCompanionProfile());
		const openInvitation = () => setInvitationOpen(true);
		window.addEventListener('parsec-log-mode-change', syncLogMode);
		window.addEventListener('parsec-profile-change', syncProfile);
		window.addEventListener('parsec-invitation-request', openInvitation);
		const unsubscribeState = subscribeBrowserCompanionState((nextState) => {
			if (nextState.location.kind === 'habitat') {
				stopReleaseMotion();
				setReleaseMode(null);
			}
			if (nextState.location.kind === 'cage' && nextState.location.closed) setActiveTool(null);
			setCompanionState(nextState);
			chooseDestination(nextState);
		});
		window.addEventListener('scroll', syncHabitatPlacement, true);
		window.addEventListener('resize', syncHabitatPlacement);
		const finishLayoutTransition = (event: Event) => {
			if (stageRef && event.target instanceof HTMLElement && event.target.contains(stageRef)) syncHabitatPlacement();
		};
		window.addEventListener('transitionend', finishLayoutTransition, true);
		const resizeObserver = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(syncHabitatPlacement);
		if (stageRef) resizeObserver?.observe(stageRef);
		// Sidebar visibility and habitat expansion can move the home without a window resize.
		const layoutObserver = new MutationObserver(syncHabitatPlacement);
		let disposed = false;
		queueMicrotask(() => {
			if (disposed) return;
			syncHabitatPlacement();
			// Parent components finish attaching their children after this component mounts.
			for (let element: HTMLElement | null = stageRef ?? null; element; element = element.parentElement) {
				layoutObserver.observe(element, { attributes: true, attributeFilter: ['class', 'style', 'hidden', 'data-open', 'data-expanded'] });
			}
		});
		onCleanup(() => {
			disposed = true;
			stopReleaseMotion();
			window.removeEventListener('scroll', syncHabitatPlacement, true);
			window.removeEventListener('resize', syncHabitatPlacement);
			window.removeEventListener('transitionend', finishLayoutTransition, true);
			resizeObserver?.disconnect();
			layoutObserver.disconnect();
			window.removeEventListener('parsec-log-mode-change', syncLogMode);
			window.removeEventListener('parsec-profile-change', syncProfile);
			window.removeEventListener('parsec-invitation-request', openInvitation);
			unsubscribeState();
		});
	});

	function pat(): void {
		const result = registerPat(patTimestamps, performance.now());
		patTimestamps = result.timestamps;
		reportParsec({
			type: 'interaction',
			phase: result.reaction === 'twerking' ? 'repeated-pat' : 'pat',
			tool: 'parsec',
			dedupeKey: 'parsec-pat',
		});
	}

	function closeActiveTool(trigger = activeToolTrigger): void {
		activeToolTrigger = null;
		setActiveTool(null);
		queueMicrotask(() => trigger?.focus());
	}

	function useTool(tool: ParsecToolId, trigger?: HTMLButtonElement): void {
		if ((['ball', 'tug', 'brush', 'treat'] as const).includes(tool as ParsecPhysicalToolId)) {
			if (activeTool() === tool) {
				closeActiveTool(trigger);
				return;
			}
			activeToolTrigger = trigger ?? null;
			setActiveTool(tool as ParsecPhysicalToolId);
			return;
		}
		if (tool === 'pat') pat();
		void interactWithBrowserCompanion(tool);
	}

	const clipId = () => browserCompanionSnapshot()
		? companionState().clip
		: coreFallbackManifest.legacyStates[resolveState(appState.parsecState)]!;
	const effectClipId = () => effectForCompanionClip(clipId());
	const cageLatched = () => {
		const location = companionState().location;
		return location.kind === 'cage' && location.closed;
	};
	const roaming = () => companionState().location.kind === 'perch' || companionState().location.kind === 'roaming';

	function chooseConsent(consent: Exclude<ExcursionConsent, 'unconfigured'>): void {
		setInvitationOpen(false);
		void dispatchBrowserCompanionIntent({ type: 'invitation-response', consent });
	}

	const furniture = (): FurnitureState => {
		const location = companionState().location;
		return {
			bed: {
				position: { x: profile().furnishings.bed.x, y: profile().furnishings.bed.y },
				anchor: profile().furnishings.bed.anchor,
				mode: location.kind === 'bed' ? location.mode : 'empty',
			},
			cage: {
				position: { x: profile().furnishings.cage.x, y: profile().furnishings.cage.y },
				anchor: profile().furnishings.cage.anchor,
				status: location.kind === 'cage'
					? location.closed ? 'latched-occupied' : 'open-occupied'
					: 'open-empty',
			},
		};
	};

	function updateFurniture(next: FurnitureState): void {
		const current = profile();
		saveCompanionProfile(window.localStorage, {
			...current,
			furnishings: {
				bed: { ...next.bed.position, anchor: next.bed.anchor },
				cage: { ...next.cage.position, anchor: next.cage.anchor },
			},
		});
	}

	return (
		<ParsecHabitat>
			<div data-parsec-companion>
				<div
					ref={stageRef}
					class={styles.stage}
					data-parsec-stage
					data-speaking={appState.parsecFeedback ? 'true' : 'false'}
					style={{ 'min-height': `${COMPACT_HABITAT_STAGE_HEIGHT}px` }}
				>
					<button type="button" class={styles.stagePatTarget} aria-label="Pat Parsec in her habitat" disabled={cageLatched()} onClick={() => useTool('pat')} />
					<ParsecRoamingLayer furniture={furniture()} onFurnitureChange={updateFurniture} space="habitat" />
					<Show when={!roaming() && activeTool()} keyed>
						{(tool) => (
							<ParsecInteractionSurface
								tool={tool}
								state={companionState()}
								onIntent={(intent) => { void dispatchBrowserCompanionIntent(intent); }}
								onClose={() => closeActiveTool()}
							/>
						)}
					</Show>
				</div>
				<ParsecToolbar onTool={useTool} cageLatched={cageLatched()} activeTool={activeTool()} />
				<Show when={invitationOpen() && companionState().consent === 'unconfigured'}>
					<div class={styles.invitation} role="dialog" aria-label="Parsec excursion invitation" aria-modal="false">
						<p>Choose whether Parsec may leave her habitat.</p>
						<button type="button" onClick={() => chooseConsent('allowed')}>Allow occasional excursions</button>
						<button type="button" onClick={() => chooseConsent('ask-each-time')}>Ask each time</button>
						<button type="button" onClick={() => chooseConsent('habitat-only')}>Stay in the habitat</button>
					</div>
				</Show>
				<ParsecRadioLog mode={logMode()} />
				<Show when={companionState().pendingExcursion}>
					<div class={styles.invitation} role="dialog" aria-label="Parsec excursion invitation" aria-modal="false">
						<p>May Parsec leave her habitat for this excursion?</p>
						<button type="button" onClick={() => { void dispatchBrowserCompanionIntent({ type: 'excursion-response', allow: true }); }}>Allow this excursion</button>
						<button type="button" onClick={() => { void dispatchBrowserCompanionIntent({ type: 'excursion-response', allow: false }); }}>Stay in the habitat this time</button>
					</div>
				</Show>
				{/* A transformed sidebar would otherwise clip and offset the fixed viewport layer. */}
				<Portal>
					<div data-parsec-companion>
						<ParsecRoamingLayer
							furniture={furniture()}
							onFurnitureChange={updateFurniture}
							space="viewport"
							consent={companionState().consent}
							companion={(
								<div class={styles.roamingActor} data-parsec-actor data-release-mode={releaseMode() ?? 'none'}
									style={{ visibility: anchoredToHabitat() && !habitatVisible() ? 'hidden' : 'visible' }}>
									<ParsecSprite
										clipId={clipId()}
										clipInstance={companionState().clipInstance}
										direction={clipId() === 'core-walk-diagonal' ? actorDiagonalDirection() : actorDirection()}
										effectClipId={effectClipId()}
										point={actorPoint()}
										onPointChange={setActorPoint}
										onRelease={startReleaseMotion}
										handlingPhysics={profile().settings.handlingPhysics}
										reducedMotion={prefersReducedMotion(profile().settings.motion)}
										confined={cageLatched()}
										dispatch={dispatchActorIntent}
									/>
								</div>
							)}
						/>
						<Show when={roaming() && activeTool()} keyed>
							{(tool) => (
								<div class={styles.interactionViewport}>
									<ParsecInteractionSurface
										tool={tool}
										state={companionState()}
										onIntent={(intent) => { void dispatchBrowserCompanionIntent(intent); }}
										onClose={() => closeActiveTool()}
									/>
								</div>
							)}
						</Show>
					</div>
				</Portal>
			</div>
		</ParsecHabitat>
	);
}

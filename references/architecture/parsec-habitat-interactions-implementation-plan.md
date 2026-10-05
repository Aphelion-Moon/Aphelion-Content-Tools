# Parsec Habitat and Interactions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan inline, task by task. Do not dispatch subagents without Zoe's explicit approval. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the expandable Parsec habitat, eight-action interaction bar, direct scruff handling, movable bed and cage, and consent-controlled roaming layer without disrupting the SPA shell or activating work-page controls.

**Architecture:** One persistent Solid component mounted by `AppShell` renders Parsec into either the habitat anchor or a pointer-transparent roaming layer. Pure geometry, physics, furniture, and interaction modules emit typed intents to the companion runtime; components own pointer capture, keyboard equivalents, and presentation only.

**Tech Stack:** SolidJS 1.9, TypeScript 5.7, Vitest 3, DOM Pointer Events, CSS transforms and modules, existing companion reducer/runtime/profile contracts.

**Spec:** [`references/architecture/parsec-companion-design.md`](parsec-companion-design.md)

## Global Constraints

- Preserve one `AppShell`, tool registry, typed client, live owner, shared selected context, app store, and Parsec coordinator.
- The selected habitat is expandable and overlays the sidebar without reflowing the active tool page.
- The primary bar contains Pat, Ball, Tug, Brush, Treat, Whistle, Bed, and Cage; scruff handling is direct manipulation.
- Parsec, toys, furniture, and their handles may receive pointer events; every other roaming-layer pixel is pointer-transparent.
- No companion action may activate, navigate, edit, save, search, or mutate application data.
- Bed and cage positions persist as normalized global coordinates and clamp after viewport changes.
- A latched cage is hard confinement; Parsec never self-releases. A bed is never a hard lock.
- Reduced motion disables autonomous roaming, throws, bounce, zoomies, and large transitions while preserving static direct feedback.
- Add behavioral tests before behavior changes; leave work uncommitted; do not dispatch agents.

---

## File structure

### New files

- `webapp/frontend/src/components/parsec/ParsecHabitat.tsx` and `.module.css` — expandable overlay habitat and render anchor.
- `webapp/frontend/src/components/parsec/ParsecHabitat.test.tsx` — expansion, focus, no-reflow, and fallback coverage.
- `webapp/frontend/src/components/parsec/ParsecToolbar.tsx` and `.module.css` — eight primary actions and accessible descriptions.
- `webapp/frontend/src/components/parsec/ParsecToolbar.test.tsx` — action order, keyboard, disabled-state, and cage-label coverage.
- `webapp/frontend/src/components/parsec/ParsecSprite.tsx` and `.module.css` — manifest clip renderer, scruff hit zone, and pointer capture.
- `webapp/frontend/src/components/parsec/ParsecSprite.test.tsx` — fallback, grab, release, and reduced-motion coverage.
- `webapp/frontend/src/components/parsec/ParsecRoamingLayer.tsx` and `.module.css` — full-page pointer-transparent roaming and furniture layer.
- `webapp/frontend/src/components/parsec/ParsecRoamingLayer.test.tsx` — pointer isolation, route persistence, and safe-region coverage.
- `webapp/frontend/src/lib/parsec/geometry.ts` and `.test.ts` — points, rectangles, clamping, normalization, and hit testing.
- `webapp/frontend/src/lib/parsec/physics.ts` and `.test.ts` — frame-independent gentle/full release simulation.
- `webapp/frontend/src/lib/parsec/interactions.ts` and `.test.ts` — primary action and pointer gesture intent mapping.
- `webapp/frontend/src/lib/parsec/furniture.ts` and `.test.ts` — bed/cage state, drop targets, latch, and recovery.
- `webapp/frontend/src/lib/parsec/safeRegions.ts` and `.test.ts` — ordinary edge perches and interactive-element avoidance.

### Modified files

- `webapp/frontend/src/components/Parsec.tsx` and `.module.css` — reduce to persistent companion composition and feedback bridge.
- `webapp/frontend/src/components/Parsec.test.tsx` — integration coverage without balloon assertions.
- `webapp/frontend/src/components/AppShell.tsx` and `webapp/frontend/src/app.css` — mount habitat and roaming anchors without changing shell contracts.
- `webapp/frontend/src/lib/parsec/companionTypes.ts` and reducer tests — add typed UI intents consumed by these components.
- `webapp/frontend/src/lib/parsec/profile.ts` and tests — persist furniture positions and interaction preferences.
- `webapp/frontend/src/tools/parsec/ParsecPage.tsx` and tests — presence, handling, furniture, and intrusive settings.
- `references/writer-guide.md` and `references/maintainer-guide.md` — document interaction, consent, confinement, recovery, and failure boundaries.

### Core interfaces

```ts
export interface Point {
	readonly x: number;
	readonly y: number;
}

export interface Rect extends Point {
	readonly width: number;
	readonly height: number;
}

export interface Velocity {
	readonly xPixelsPerSecond: number;
	readonly yPixelsPerSecond: number;
}

export type ToolId = 'pat' | 'ball' | 'tug' | 'brush' | 'treat' | 'whistle' | 'bed' | 'cage';
export type GrabPhysics = 'carry-only' | 'gentle' | 'full';
export type FurnitureId = 'bed' | 'cage';

export interface NormalizedPosition {
	readonly x: number;
	readonly y: number;
}

export interface SafeRegionSnapshot {
	readonly viewport: Rect;
	readonly shellChrome: readonly Rect[];
	readonly interactiveControls: readonly Rect[];
	readonly selectionRanges: readonly Rect[];
}
```

### Task 1: Build the expandable habitat and eight-action toolbar

**Files:**
- Create: `webapp/frontend/src/components/parsec/ParsecHabitat.tsx`
- Create: `webapp/frontend/src/components/parsec/ParsecHabitat.module.css`
- Create: `webapp/frontend/src/components/parsec/ParsecHabitat.test.tsx`
- Create: `webapp/frontend/src/components/parsec/ParsecToolbar.tsx`
- Create: `webapp/frontend/src/components/parsec/ParsecToolbar.module.css`
- Create: `webapp/frontend/src/components/parsec/ParsecToolbar.test.tsx`
- Modify: `webapp/frontend/src/components/Parsec.tsx`
- Modify: `webapp/frontend/src/components/Parsec.module.css`
- Modify: `webapp/frontend/src/components/AppShell.tsx`

**Interfaces:**
- Consumes: runtime state, `ToolId`, manifest-backed current sprite fallback, and the radio-log component from the history plan.
- Produces: `ParsecHabitat`, `ParsecToolbar`, `onTool(tool: ToolId)`, `expanded`, and stable habitat/roaming anchor elements.

- [ ] **Step 1: Write failing structure and action-order tests**

```tsx
it('renders the approved eight actions before the compact radio log', () => {
	render(() => <ParsecHarness />);
	const names = screen.getAllByRole('button').map((button) => button.getAttribute('aria-label'));
	expect(names.slice(0, 8)).toEqual(['Pat Parsec', 'Throw ball', 'Play tug', 'Brush Parsec', 'Offer treat', 'Whistle', 'Go to bed', 'Go to cage']);
	expect(screen.getByRole('log', { name: 'Parsec radio' })).toBeTruthy();
});

it('expands over the sidebar without changing the tool-column width', () => {
	const before = toolColumn.getBoundingClientRect().width;
	await user.click(screen.getByRole('button', { name: 'Expand Parsec habitat' }));
	expect(toolColumn.getBoundingClientRect().width).toBe(before);
});
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `npm --prefix webapp/frontend test -- --run src/components/parsec/ParsecHabitat.test.tsx src/components/parsec/ParsecToolbar.test.tsx`

Expected: FAIL because the habitat and toolbar do not exist.

- [ ] **Step 3: Implement expandable overlay composition**

Keep the collapsed playfield inside the existing sidebar module. Render the expanded panel with absolute
positioning against a shell-owned anchor, a fixed maximum width/height constrained by the viewport, and
no grid-template or tool-column changes. Escape, the close button, route navigation, and focus leaving the
expanded surface return it to the compact state without moving Parsec's runtime state.

- [ ] **Step 4: Implement accessible action dispatch**

Render all eight controls in the approved order with native buttons, visible focus, `aria-label`, concise
tooltips, and a roving compact layout at narrow widths. Dispatch only a typed companion intent. Disable an
action only when its physical precondition is impossible; when the cage is latched its visible label and
accessible name become `Release Parsec`.

- [ ] **Step 5: Run focused tests and typecheck**

Run: `npm --prefix webapp/frontend test -- --run src/components/parsec/ParsecHabitat.test.tsx src/components/parsec/ParsecToolbar.test.tsx src/components/Parsec.test.tsx`

Run: `npm --prefix webapp/frontend run typecheck`

Expected: PASS.

### Task 2: Add pure geometry, release physics, and scruff handling

**Files:**
- Create: `webapp/frontend/src/lib/parsec/geometry.ts`
- Create: `webapp/frontend/src/lib/parsec/geometry.test.ts`
- Create: `webapp/frontend/src/lib/parsec/physics.ts`
- Create: `webapp/frontend/src/lib/parsec/physics.test.ts`
- Create: `webapp/frontend/src/components/parsec/ParsecSprite.tsx`
- Create: `webapp/frontend/src/components/parsec/ParsecSprite.module.css`
- Create: `webapp/frontend/src/components/parsec/ParsecSprite.test.tsx`

**Interfaces:**
- Consumes: `GrabPhysics`, manifest scruff/foot anchors, reduced-motion setting, and runtime intent dispatch.
- Produces: `clampPoint`, `normalizePoint`, `denormalizePoint`, `estimateReleaseVelocity`, `stepRelease`, and the `ParsecSprite` pointer/keyboard boundary.

- [ ] **Step 1: Write failing geometry and frame-independence tests**

```ts
it('clamps and round-trips a normalized furniture or companion position', () => {
	const point = clampPoint({ x: 140, y: -10 }, { x: 0, y: 0, width: 100, height: 80 });
	expect(point).toEqual({ x: 100, y: 0 });
	expect(denormalizePoint(normalizePoint({ x: 50, y: 40 }, viewport), viewport)).toEqual({ x: 50, y: 40 });
});

it('produces the same gentle release after equal elapsed time at different frame rates', () => {
	expect(simulate(gentleRelease, 1 / 60, 0.5)).toEqualCloseTo(simulate(gentleRelease, 1 / 20, 0.5));
});
```

- [ ] **Step 2: Write failing pointer-capture and keyboard tests**

```tsx
it('captures the scruff pointer and releases with the configured motion', async () => {
	await pointer.down(scruff, { pointerId: 7, clientX: 20, clientY: 20 });
	expect(scruff.hasPointerCapture(7)).toBe(true);
	await pointer.move(scruff, { pointerId: 7, clientX: 80, clientY: 30 });
	await pointer.up(scruff, { pointerId: 7, clientX: 90, clientY: 35 });
	expect(dispatch).toHaveBeenLastCalledWith(expect.objectContaining({ type: 'released' }));
});
```

- [ ] **Step 3: Run focused tests and confirm failure**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/geometry.test.ts src/lib/parsec/physics.test.ts src/components/parsec/ParsecSprite.test.tsx`

- [ ] **Step 4: Implement bounded handling**

Use the manifest scruff anchor to define the direct grab zone. Sample a short timestamped pointer history
to estimate velocity. `carry-only` releases at zero velocity, `gentle` clamps velocity and uses critically
damped settling, and `full` uses bounded gravity/restitution. Reduced motion always behaves as carry-only.
Cancel capture on visibility loss, pointer cancellation, unmount, or confinement. Arrow keys reposition a
focused held Parsec in eight-pixel steps; Enter/Space picks up or releases; Escape returns her to the last
valid anchor.

- [ ] **Step 5: Run focused tests and typecheck**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/geometry.test.ts src/lib/parsec/physics.test.ts src/components/parsec/ParsecSprite.test.tsx`

Run: `npm --prefix webapp/frontend run typecheck`

Expected: PASS.

### Task 3: Implement Pat, Ball, Tug, Brush, Treat, and Whistle

**Files:**
- Create: `webapp/frontend/src/lib/parsec/interactions.ts`
- Create: `webapp/frontend/src/lib/parsec/interactions.test.ts`
- Modify: `webapp/frontend/src/components/parsec/ParsecToolbar.tsx`
- Modify: `webapp/frontend/src/components/parsec/ParsecToolbar.test.tsx`
- Modify: `webapp/frontend/src/lib/parsec/companionReducer.ts`
- Modify: `webapp/frontend/src/lib/parsec/companionReducer.test.ts`

**Interfaces:**
- Consumes: `ToolId`, companion state, pointer/keyboard gesture samples, and validated object/clip fallbacks.
- Produces: `beginToolInteraction(tool, state)`, `updateToolInteraction(session, sample)`, and `finishToolInteraction(session, sample)` returning only `CompanionIntent` values.

- [ ] **Step 1: Write failing state-machine tests for all six interactions**

```ts
it.each([
	['pat', 'pat-started'],
	['ball', 'ball-placed'],
	['tug', 'tug-offered'],
	['brush', 'brush-started'],
	['treat', 'treat-offered'],
	['whistle', 'recall-requested'],
] as const)('maps %s to %s without application commands', (tool, expectedType) => {
	const intents = beginToolInteraction(tool, availableState);
	expect(intents).toContainEqual(expect.objectContaining({ type: expectedType }));
	expect(intents.some((intent) => ['navigate', 'search', 'save', 'fetch'].includes(intent.type))).toBe(false);
});
```

- [ ] **Step 2: Run tests and verify failure**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/interactions.test.ts src/lib/parsec/companionReducer.test.ts src/components/parsec/ParsecToolbar.test.tsx`

- [ ] **Step 3: Implement typed sessions and fallback reactions**

Pat and brush convert directional pointer strokes into bounded direct-interaction intents. Ball creates one
draggable/throwable object with chase/retrieve/drop states. Tug maps pointer distance to normalized tension
and releases on pointer up/cancel. Treat supports placement or direct offer but creates no need meter.
Whistle recalls an excursion, cancels autonomous play, or requests an allowed excursion. Missing creative
clips use the manifest's current-sheet reaction fallback and text-only object label.

- [ ] **Step 4: Add keyboard equivalents**

Focused Ball, Tug, Brush, and Treat controls enter a keyboard interaction mode. Arrow keys move the active
object or stroke target; Enter commits; Escape cancels and restores the preceding state. Pat and Whistle
complete on button activation. Announce mode changes through a polite, concise status line, not a new
balloon.

- [ ] **Step 5: Run focused tests and typecheck**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/interactions.test.ts src/lib/parsec/companionReducer.test.ts src/components/parsec/ParsecToolbar.test.tsx`

Run: `npm --prefix webapp/frontend run typecheck`

Expected: PASS.

### Task 4: Add movable bed, hard-confinement cage, and position recovery

**Files:**
- Create: `webapp/frontend/src/lib/parsec/furniture.ts`
- Create: `webapp/frontend/src/lib/parsec/furniture.test.ts`
- Create: `webapp/frontend/src/components/parsec/ParsecRoamingLayer.tsx`
- Create: `webapp/frontend/src/components/parsec/ParsecRoamingLayer.module.css`
- Create: `webapp/frontend/src/components/parsec/ParsecRoamingLayer.test.tsx`
- Modify: `webapp/frontend/src/lib/parsec/profile.ts`
- Modify: `webapp/frontend/src/lib/parsec/profile.test.ts`
- Modify: `webapp/frontend/src/tools/parsec/ParsecPage.tsx`
- Modify: `webapp/frontend/src/tools/parsec/ParsecPage.test.tsx`

**Interfaces:**
- Consumes: normalized geometry, viewport bounds, profile persistence, and companion drop/release intents.
- Produces: `FurnitureState`, `moveFurniture`, `dropOnFurniture`, `toggleCageLatch`, `resetFurnitureHome`, and rendered bed/cage handles.

- [ ] **Step 1: Write failing confinement and position tests**

```ts
it('keeps an open cage open after drop and prevents every autonomous exit once latched', () => {
	const dropped = dropOnFurniture(companion, openCage);
	expect(dropped.cage.latched).toBe(false);
	const latched = toggleCageLatch(dropped);
	expect(canLeaveFurniture(latched, { source: 'autonomous' })).toBe(false);
	expect(canLeaveFurniture(latched, { source: 'release-command' })).toBe(true);
});

it('clamps persisted furniture after viewport shrink and can return both home', () => {
	expect(clampFurniture(offscreenProfile, smallViewport)).toEqual(inBoundsProfile);
	expect(resetFurnitureHome(inBoundsProfile)).toEqual(defaultHomeFurniture);
});
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/furniture.test.ts src/components/parsec/ParsecRoamingLayer.test.tsx src/lib/parsec/profile.test.ts`

- [ ] **Step 3: Implement furniture rules**

Bed supports `voluntary` and `timeout` modes; neither prevents explicit pickup or whistle. Cage stores
`open`, `latched-empty`, and `latched-occupied`. Dropping into an open cage changes occupancy only. Cage
toolbar activation sends Parsec inside and latches; activation while latched releases her. Only an explicit
user command changes a latched occupied cage to open. Feedback reactions can animate in place but cannot
change confinement.

- [ ] **Step 4: Implement global dragging and recovery**

Furniture handles capture pointers independently of their artwork. Approved destinations are the habitat
and viewport edge zones that do not intersect critical shell controls. Persist normalized positions only
after a successful drop; clamp on load/resize. Provide `Return bed and cage home` in settings and announce
success through the coordinator.

- [ ] **Step 5: Run focused tests and typecheck**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/furniture.test.ts src/components/parsec/ParsecRoamingLayer.test.tsx src/lib/parsec/profile.test.ts src/tools/parsec/ParsecPage.test.tsx`

Run: `npm --prefix webapp/frontend run typecheck`

Expected: PASS.

### Task 5: Add consent-controlled ordinary and intrusive roaming

**Files:**
- Create: `webapp/frontend/src/lib/parsec/safeRegions.ts`
- Create: `webapp/frontend/src/lib/parsec/safeRegions.test.ts`
- Modify: `webapp/frontend/src/components/parsec/ParsecRoamingLayer.tsx`
- Modify: `webapp/frontend/src/components/parsec/ParsecRoamingLayer.test.tsx`
- Modify: `webapp/frontend/src/lib/parsec/companionScheduler.ts`
- Modify: `webapp/frontend/src/lib/parsec/companionScheduler.test.ts`
- Modify: `webapp/frontend/src/tools/parsec/ParsecPage.tsx`
- Modify: `webapp/frontend/src/tools/parsec/ParsecPage.test.tsx`

**Interfaces:**
- Consumes: `SafeRegionSnapshot`, consent value, roaming mode, route/focus/typing state, and scheduler context.
- Produces: `collectSafeRegions(root)`, `chooseOrdinaryPerch(snapshot, random)`, consent invitation UI, and ordinary/intrusive eligibility.

- [ ] **Step 1: Write failing consent, avoidance, and pointer-isolation tests**

```tsx
it('never mounts an excursion before the one-time invitation is answered', () => {
	render(() => <RoamingHarness consent="unconfigured" />);
	expect(screen.queryByTestId('parsec-roaming-sprite')).toBeNull();
});

it('keeps the roaming root click-through and marks only interactive actors as hit targets', () => {
	expect(roamingRoot).toHaveStyle({ pointerEvents: 'none' });
	expect(sprite).toHaveStyle({ pointerEvents: 'auto' });
	expect(backgroundProbe).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/safeRegions.test.ts src/components/parsec/ParsecRoamingLayer.test.tsx src/lib/parsec/companionScheduler.test.ts`

- [ ] **Step 3: Implement the one-time invitation and ask-each-time path**

The first direct interaction while consent is `unconfigured` opens an in-character, accessible dialog with
exactly: occasional excursions, ask each time, and stay in habitat. Store the answer in the profile.
`ask-each-time` presents a non-modal permission prompt for each autonomous excursion and expires it without
changing the stored policy. Direct drag outside the habitat remains a deliberate user action but does not
silently change consent.

- [ ] **Step 4: Implement safe ordinary perches and optional intrusion**

Ordinary mode selects edge-biased destinations outside collected interactive/control/selection rectangles.
It may cross the work canvas only during direct cursor/toy play. Intrusive mode may select work-area
destinations, loiter near the pointer, and overlap controls, but actor hit targets consume manipulation
events and never synthesize click, submit, keyboard, navigation, or feature intents. Typing, serious errors,
hidden state, and reduced-distraction mode suppress autonomous intrusion.

- [ ] **Step 5: Run focused tests and typecheck**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/safeRegions.test.ts src/components/parsec/ParsecRoamingLayer.test.tsx src/lib/parsec/companionScheduler.test.ts src/tools/parsec/ParsecPage.test.tsx`

Run: `npm --prefix webapp/frontend run typecheck`

Expected: PASS.

### Task 6: Integrate settings, accessibility, route persistence, and shell failure isolation

**Files:**
- Modify: `webapp/frontend/src/components/Parsec.tsx`
- Modify: `webapp/frontend/src/components/Parsec.test.tsx`
- Modify: `webapp/frontend/src/components/AppShell.tsx`
- Modify: `webapp/frontend/src/components/AppShell.test.tsx`
- Modify: `webapp/frontend/src/tools/parsec/ParsecPage.tsx`
- Modify: `webapp/frontend/src/tools/parsec/ParsecPage.test.tsx`
- Modify: `references/writer-guide.md`
- Modify: `references/maintainer-guide.md`

**Interfaces:**
- Consumes: Tasks 1–5 and the runtime/history plans.
- Produces: one persistent, configurable, route-stable companion with a static-sprite/plain-log fallback.

- [ ] **Step 1: Write failing integrated shell tests**

```tsx
it('preserves one Parsec instance and furniture positions across tool routes', async () => {
	const identity = screen.getByTestId('parsec-companion').dataset.instanceId;
	await navigate('/lore');
	await navigate('/graph');
	expect(screen.getByTestId('parsec-companion').dataset.instanceId).toBe(identity);
	expect(readFurniturePosition('bed')).toEqual(savedBedPosition);
});

it('keeps the tool usable when the companion renderer throws', () => {
	render(() => <AppShell companionFactory={throwingCompanion} />);
	expect(screen.getByRole('main')).toBeTruthy();
	expect(screen.getByRole('log', { name: 'Parsec radio' })).toBeTruthy();
});
```

- [ ] **Step 2: Run integrated tests and verify failure**

Run: `npm --prefix webapp/frontend test -- --run src/components/Parsec.test.tsx src/components/AppShell.test.tsx src/tools/parsec/ParsecPage.test.tsx`

- [ ] **Step 3: Complete settings and accessibility surfaces**

Expose roaming consent/mode, cursor initiation, intrusive frequency, tone, expressiveness, grab physics,
bed mode, reduced distraction, reduced motion, and furniture reset using the unified profile. Respect the
OS reduced-motion query unless the user chooses an even stricter setting. Keep every action reachable by
keyboard, focus-visible, and named; log ordinary responses politely and errors assertively.

- [ ] **Step 4: Add render-error isolation and documentation**

Catch companion-render failures at the persistent shell boundary. Replace the animated actor with the
current static sprite and keep the plain radio log mounted. Document consent, intrusive behavior,
scruff/keyboard handling, bed/cage semantics, reset, privacy, and the fact that companion failure never
blocks writing tools.

- [ ] **Step 5: Run the plan gates**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec src/components/parsec src/components/Parsec.test.tsx src/components/AppShell.test.tsx src/tools/parsec`

Run: `npm --prefix webapp/frontend run typecheck`

Run: `npm --prefix webapp/frontend run build`

Run: `python tools/docs/check_agent_docs.py`

Run: `git diff --check`

Expected: all pass. Leave changes uncommitted.

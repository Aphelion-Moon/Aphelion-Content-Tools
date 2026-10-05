# Parsec Runtime Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This repository is being changed inline; do not dispatch subagents.

**Goal:** Replace Parsec's component-swapping interaction path with one persistent actor, real release motion, directly draggable furniture, and production asset-quality gates.

**Architecture:** One viewport actor remains mounted for every semantic location and receives controlled coordinates from `Parsec.tsx`. Framework-independent motion helpers decide when a destination may change and integrate release physics; furniture retains two presentation regions but never changes region until pointer release. Asset recovery follows runtime stabilization and may reuse coherent production frames instead of retaining weak unique artwork.

**Tech Stack:** SolidJS, TypeScript, Vitest, CSS modules, Python 3.11+, Pillow, production FastAPI launcher.

**Spec:** `references/architecture/parsec-runtime-recovery-design.md`

## Global Constraints

- Preserve the Solid SPA shell, tool registry, shared store, typed API client, live connection, shared search, shared references, Parsec radio, durable activity journal, and `/parsec` settings route.
- Preserve the existing local companion profile and every approved Parsec setting.
- Add a behavioral regression test and observe its expected failure before each production behavior change.
- Keep rollback-only legacy pages unchanged.
- Preserve unrelated working-tree changes and do not commit, push, reset, checkout, merge, or dispatch agents.
- Do not mark an asset accepted from structural validation alone.

---

### Task 1: Stable Actor Destination Rules

**Files:**
- Create: `webapp/frontend/src/lib/parsec/actorMotion.ts`
- Create: `webapp/frontend/src/lib/parsec/actorMotion.test.ts`
- Modify: `webapp/frontend/src/lib/parsec/companionTypes.ts`
- Modify: `webapp/frontend/src/lib/parsec/companionReducer.ts`
- Test: `webapp/frontend/src/lib/parsec/companionReducer.test.ts`

**Interfaces:**
- Produces: `shouldChooseActorDestination(previous, next): boolean`, `actorPointFromLocation(location): Point | null`, and a `motion-settled` companion intent.
- Consumes: existing `CompanionLocation`, `CompanionIntent`, `Point`, and reducer state.

- [x] **Step 1: Write failing destination-stability tests**

```ts
it('does not choose a new destination for held movement or clip-only state updates', () => {
	expect(shouldChooseActorDestination(
		{ kind: 'transition', point: { x: 40, y: 50 } },
		{ kind: 'transition', point: { x: 80, y: 90 } },
	)).toBe(false);
	expect(shouldChooseActorDestination(
		{ kind: 'perch', anchorId: 'shell-edge' },
		{ kind: 'perch', anchorId: 'shell-edge' },
	)).toBe(false);
});

it('settles release motion without replacing semantic state', () => {
	const released = reduceCompanion(heldState, {
		type: 'motion-settled',
		point: { x: 240, y: 180 },
	});
	expect(released.state.location).toEqual({ kind: 'roaming', point: { x: 240, y: 180 } });
});
```

- [x] **Step 2: Run the focused tests and verify RED**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/actorMotion.test.ts src/lib/parsec/companionReducer.test.ts`

Expected: failure because `actorMotion.ts` and `motion-settled` do not exist.

- [x] **Step 3: Implement the minimal destination helpers and reducer intent**

```ts
export function actorPointFromLocation(location: CompanionLocation): Point | null {
	return location.kind === 'transition' || location.kind === 'roaming' ? location.point : null;
}

export function shouldChooseActorDestination(previous: CompanionLocation, next: CompanionLocation): boolean {
	if (next.kind === 'transition' || next.kind === 'roaming') return false;
	if (next.kind === 'perch' && previous.kind === 'perch' && previous.anchorId === next.anchorId) return false;
	return previous.kind !== next.kind || next.kind === 'perch';
}
```

Add `motion-settled` to `CompanionIntent` and update only the final roaming point in the reducer.

- [x] **Step 4: Run the focused tests and verify GREEN**

Run the command from Step 2 and require zero failures.

- [x] **Step 5: Record the task result in this plan without committing**

Focused result: 20 tests passed across `actorMotion.test.ts` and `companionReducer.test.ts`.

### Task 2: One Persistent Actor Through Grab and Navigation

**Files:**
- Modify: `webapp/frontend/src/components/Parsec.tsx`
- Modify: `webapp/frontend/src/components/Parsec.test.tsx`
- Modify: `webapp/frontend/src/components/parsec/ParsecSprite.tsx`
- Modify: `webapp/frontend/src/components/parsec/ParsecSprite.test.tsx`
- Modify: `webapp/frontend/src/components/parsec/ParsecRoamingLayer.tsx`
- Modify: `webapp/frontend/src/components/Parsec.module.css`
- Modify: `webapp/frontend/src/components/parsec/ParsecRoamingLayer.module.css`

**Interfaces:**
- Consumes: Task 1 destination helpers and existing companion runtime subscription.
- Produces: a single `[data-parsec-actor]` DOM node with controlled `point` and `onPointChange` props.

- [x] **Step 1: Write failing component integration tests**

```ts
it('keeps the same actor node while a habitat grab becomes a transition', () => {
	const before = host.querySelector('[data-parsec-actor]');
	scruff.dispatchEvent(pointerEvent('pointerdown', pointer(7, 40, 40, 0)));
	scruff.dispatchEvent(pointerEvent('pointermove', pointer(7, 160, 100, 100)));
	expect(host.querySelectorAll('[data-parsec-actor]')).toHaveLength(1);
	expect(host.querySelector('[data-parsec-actor]')).toBe(before);
});
```

Extend the test runtime seam so the real `Parsec` component can receive state transitions without mocking the rendered actor.

- [x] **Step 2: Run focused component tests and verify RED**

Run: `npm --prefix webapp/frontend test -- --run src/components/Parsec.test.tsx src/components/parsec/ParsecSprite.test.tsx`

Expected: actor replacement or missing stable actor selector.

- [x] **Step 3: Convert `ParsecSprite` to controlled coordinates**

```ts
interface ParsecSpriteProps {
	readonly point: Point;
	readonly onPointChange: (point: Point) => void;
	readonly onRelease: (samples: readonly PointerSample[]) => void;
}
```

Remove its private point signal. Pointer movement calls `onPointChange` and dispatches `held-moved`; pointer release passes samples to the parent without remounting the actor.

- [x] **Step 4: Render exactly one actor from `Parsec.tsx`**

Keep one controlled `actorPoint` signal and one fixed actor layer. Use explicit location changes to choose habitat, bed, cage, or stable safe-perch destinations. Remove the habitat/viewport actor branches and do not call `chooseOrdinaryPerch` for ordinary state publications.

- [x] **Step 5: Run focused tests and verify GREEN**

Run the command from Step 2 and require a stable node across pointerdown, pointermove, pointerup, and a simulated route-state update.

- [x] **Step 6: Record the task result without committing**

Focused result: 19 component tests passed; TypeScript typecheck passed.

### Task 3: Production Release Simulation

**Files:**
- Modify: `webapp/frontend/src/lib/parsec/actorMotion.ts`
- Modify: `webapp/frontend/src/lib/parsec/actorMotion.test.ts`
- Modify: `webapp/frontend/src/components/Parsec.tsx`
- Modify: `webapp/frontend/src/components/Parsec.test.tsx`

**Interfaces:**
- Produces: `createReleaseSimulation(initial, bounds, mode, clock)` returning `advance(timestamp)` and `settled` state.
- Consumes: `estimateReleaseVelocity`, `stepRelease`, controlled actor coordinates, and `motion-settled`.

- [x] **Step 1: Write failing deterministic simulation tests**

```ts
it('advances full-tossing coordinates and settles inside viewport bounds', () => {
	const simulation = createReleaseSimulation(
		{ point: { x: 100, y: 100 }, velocity: { x: 800, y: -500 } },
		{ x: 0, y: 0, width: 500, height: 400 },
		'full',
	);
	const moved = simulation.advance(16 / 1000);
	expect(moved.point.x).toBeGreaterThan(100);
	expect(moved.point.y).toBeLessThan(100);
	expect(moved.settled).toBe(false);
});
```

Add literal tests for carry-only immediate settlement, full-mode bounds, low-speed settlement, and maximum-duration settlement.

- [x] **Step 2: Run `actorMotion.test.ts` and verify RED**

Expected: `createReleaseSimulation` is absent.

- [x] **Step 3: Implement the minimal deterministic simulation**

Use `stepRelease` with elapsed seconds, a 16 ms maximum integration slice, a 24 pixels-per-second settling threshold, and a 2.5 second maximum duration. Return a new immutable result on each advance.

- [x] **Step 4: Run the focused simulation tests and verify GREEN**

Require all literal motion and bounds assertions to pass.

- [x] **Step 5: Write the failing actor integration test**

Use fake animation frames to release with known velocity, advance time, assert that the same actor transform changes, and assert one final `motion-settled` intent.

- [x] **Step 6: Connect requestAnimationFrame in `Parsec.tsx`**

Start simulation after pointer release, update `actorPoint` for every animation frame, cancel any previous frame before a new gesture, and dispatch `motion-settled` once. Carry-only and reduced-motion settle synchronously.

- [x] **Step 7: Run focused actor and reducer tests and verify GREEN**

Run Tasks 1-3 focused test files and require zero failures.

- [x] **Step 8: Record the task result without committing**

Focused result: 42 tests passed across actor motion, physics, reducer, sprite, and Parsec integration; TypeScript typecheck passed.

### Task 4: Direct Furniture Manipulation and Scale

**Files:**
- Modify: `webapp/frontend/src/components/parsec/ParsecRoamingLayer.tsx`
- Modify: `webapp/frontend/src/components/parsec/ParsecRoamingLayer.test.tsx`
- Modify: `webapp/frontend/src/components/parsec/ParsecRoamingLayer.module.css`
- Modify: `webapp/frontend/src/lib/parsec/furniture.ts`
- Modify: `webapp/frontend/src/lib/parsec/furniture.test.ts`

**Interfaces:**
- Produces: one directly draggable `[data-furniture-control]` per visible item and `moveFurnitureByKeyboard(state, id, delta, anchor)`.
- Consumes: existing normalized furniture state and habitat/app-edge region selection.

- [x] **Step 1: Write failing direct-manipulation tests**

```ts
it('uses the visible furniture control as the drag surface without a detached handle', () => {
	const bed = host.querySelector('[data-furniture-id="bed"]')!;
	expect(bed.querySelector('[data-furniture-control]')).not.toBeNull();
	expect(bed.querySelector('[data-furniture-handle]')).toBeNull();
});
```

Add pointer tests that keep the current anchor during movement and change it only on release, plus keyboard arrow tests using literal normalized deltas.

- [x] **Step 2: Run roaming-layer and furniture tests and verify RED**

Run: `npm --prefix webapp/frontend test -- --run src/components/parsec/ParsecRoamingLayer.test.tsx src/lib/parsec/furniture.test.ts`

Expected: detached handle remains and direct control is absent.

- [x] **Step 3: Make the artwork control own pointer capture**

Render one button containing the object art. Apply `aria-label="Move Parsec bed"` or cage, pointer capture, pointer movement, release-region detection, Escape cancellation, and arrow-key movement to that button. Remove visible `Move` text.

- [x] **Step 4: Scale furniture presentation coherently**

Use a 96 by 96 clipped control and apply one shared nearest-neighbor scale and baseline for dogbed and every cage state. Preserve raw source pixels until Task 5 moves the transformation into the deterministic asset pipeline.

- [x] **Step 5: Run focused tests and verify GREEN**

Require direct pointer and keyboard behavior to pass with no detached-handle selector.

- [x] **Step 6: Record the task result without committing**

Focused result: 9 furniture and roaming-layer tests passed; TypeScript typecheck passed.

### Task 5: Deterministic Object Preparation and Visual Lint

**Files:**
- Modify: `tools/parsec_assets/prepare_object_frame.py`
- Modify: `tools/parsec_assets/test_prepare_object_frame.py`
- Modify: `tools/parsec_assets/build_ss13_objects.py`
- Modify: `tools/parsec_assets/test_build_ss13_objects.py`
- Create: `tools/parsec_assets/visual_lint.py`
- Create: `tools/parsec_assets/test_visual_lint.py`
- Modify: generated `webapp/frontend/src/assets/parsec/ss13-objects.png`
- Modify: generated `webapp/frontend/src/assets/parsec/ss13-objects.json`
- Modify: `references/parsec-asset-register.md`

**Interfaces:**
- Produces: `prepare_object_frame(input_path, output_path, scale, baseline_y)` and `lint_clip_frames(paths, rules): list[str]`.
- Consumes: extracted RGBA DMI frames and the existing 96 by 96 atlas builder.

- [x] **Step 1: Write failing object-scale tests**

Create a literal 16 by 12 opaque fixture, prepare it at scale 3 and baseline 78, and assert a 48 by 36 occupied alpha box whose bottom is exactly 78. Add a cage-family test proving identical scale and baseline.

- [x] **Step 2: Run object-preparation tests and verify RED**

Run: `python -m pytest tools/parsec_assets/test_prepare_object_frame.py tools/parsec_assets/test_build_ss13_objects.py -q`

Expected: the current no-scaling preparation produces the wrong occupied bounds.

- [x] **Step 3: Implement deterministic crop, scale, and baseline placement**

Crop to alpha bounds, resize with `Image.Resampling.NEAREST`, refuse dimensions larger than 96, center horizontally, and place the occupied bottom at `baseline_y`. Store scale and baseline in the source inventory.

- [x] **Step 4: Write failing visual-lint fixtures**

Use generated RGBA fixtures to prove rejection of border residue, a detached one-pixel component, more than 8 pixels of within-clip baseline jitter, more than 20 percent occupied-height discontinuity, and swapped visible eye colors.

- [x] **Step 5: Implement the visual lint and verify GREEN**

Keep thresholds explicit in a `VisualRules` dataclass. Return precise `clip/frame: reason` diagnostics without mutating source images.

- [x] **Step 6: Regenerate and inspect SS13 objects**

Run `build_ss13_objects.py` against the configured Meridian-Rift checkout. Inspect dogbed, open cage, locked cage, and occupied cage at native and 4x nearest-neighbor scale before accepting the generated atlas.

- [x] **Step 7: Update provenance and derived-transform records**

Record exact scale, baseline, source revision, hashes, and the in-app review result in the asset register.

- [x] **Step 8: Record the task result without committing**

Mark Steps 1-8 complete and record Python test and inspection results.

Focused result: 9 object-preparation and visual-lint tests passed. The rebuilt 11-object atlas uses a recorded
`3×` nearest-neighbor transform and baseline `y=90`; the locked carrier is composed over the closed-carrier base.
Native and `4×` contact review accepted the dog bed and cage family, and the furniture-family lint returned no
border residue, detached components, baseline jitter, or occupied-height discontinuity.

### Task 6: Animation Library Re-audit and Quarantine

**Files:**
- Modify: `tools/parsec_assets/validate_manifest.py`
- Modify: `tools/parsec_assets/test_validate_manifest.py`
- Modify: `webapp/frontend/src/assets/parsec/manifest.v1.ts`
- Modify only after review: production Parsec atlas PNG/JSON/anchor files
- Modify: `references/parsec-asset-register.md`
- Modify: `references/architecture/parsec-creative-sprint-plan.md`

**Interfaces:**
- Consumes: Task 5 visual lint, contact-sheet builder, motion-review builder, and current manifest.
- Produces: a production manifest containing only visually reviewed frames, with explicit coherent reuse for quarantined clips.

- [x] **Step 1: Add a failing production-quality validation test**

Run visual lint for every accepted production clip and require a recorded review status for each production frame family. The current manifest must fail because structural acceptance lacks visual-review evidence.

- [x] **Step 2: Generate review artifacts for every atlas**

Produce native, 4x nearest-neighbor, motion, and reduced-motion reviews. Inventory every clip as accepted, coherent reuse, or quarantined with a concrete reason.

- [x] **Step 3: Quarantine visibly broken or inconsistent clips**

Remove rejected frame families from production resolution. Map their semantic clips to the strongest coherent accepted clip with compatible anchors and loop mode. Do not preserve a weak unique frame for roster completeness.

- [x] **Step 4: Use image generation or manual post-processing only for reviewed replacement batches**

For each replacement batch, supply the approved Parsec references, eye laterality, transparent 96 by 96 canvas, shared palette, baseline, and motion storyboard. Post-process deterministic outputs, run visual lint, inspect contact sheets and motion review, then integrate only accepted frames.

- [x] **Step 5: Run resolved-manifest and provenance gates**

Require zero structural errors, zero production visual-lint errors, no unrecorded generated frames, and no claim that frame count alone establishes acceptance.

- [x] **Step 6: Record the audit result without committing**

Update the asset register and creative sprint plan with accepted, reused, quarantined, and human-art-backlog counts.

Audit result: 56 source clips / 274 source frames remain accepted. Four source clips / 19 source frames with
detached tail or motion pixels are quarantined, while their four semantic slots coherently reuse the reviewed
five-frame `feedback-success-wag` reaction. All 60 runtime clip IDs remain resolved. The human-art backlog is four
replacement clips. No new generated replacement batch was needed for this recovery pass.

**2026-08-26 correction:** direct enlarged review after user acceptance testing invalidated that blanket artistic
acceptance. Structural lint did not detect malformed faces, inconsistent eye clusters, cropped anatomy, or the
quality gap between older flat batches and the newer organic intrusive art. The authoritative repair roster is
now [`parsec-manual-repair-audit.md`](parsec-manual-repair-audit.md). `core-idle-seated` has been replaced; the
remaining flagged clips stay available only for feature continuity until their replacement gates pass.

### Task 7: Full Verification and Real Pointer Acceptance

**Files:**
- Modify: `references/architecture/parsec-runtime-recovery-implementation-plan.md`
- Modify after observed results: `references/architecture/parsec-creative-sprint-plan.md`

**Interfaces:**
- Consumes: Tasks 1-6.
- Produces: recorded automated gate evidence and a production-launcher acceptance checklist.

- [x] **Step 1: Run repository frontend and asset gates**

```powershell
npm --prefix webapp/frontend test -- --run
npm --prefix webapp/frontend run typecheck
npm --prefix webapp/frontend run build
python -m pytest tools/parsec_assets -q
python tools/parsec_assets/validate_manifest.py --manifest webapp/frontend/src/assets/parsec/manifest.v1.ts --register references/parsec-asset-register.md --require-resolved
python tools/docs/check_agent_docs.py
git diff --check
```

Evidence (2026-08-25): the full frontend suite passes 320 tests in 66 files; TypeScript typecheck and the
Vite production build pass; all 50 Parsec asset tests pass; resolved-manifest validation accepts 60 clips
and 293 planned frames; agent-documentation consistency passes; and `git diff --check` exits zero with only
existing LF-to-CRLF notices.

- [x] **Step 2: Launch the shipped application**

Run `cmd.exe /d /c '"Launch Aphelion Content Tools.cmd"'`, capture the loopback readiness URL, and open the production `/parsec` route.

Evidence (2026-08-25): the Windows launcher served the tracked production frontend at
`http://127.0.0.1:64146/parsec` with 84,624 catalog rows visible in the application shell.

- [x] **Step 3: Perform maintainer browser checks**

Verify one actor node, direct furniture controls, no console errors, stable navigation, profile persistence, settings, and accessible keyboard paths.

Evidence (2026-08-25): the rebuilt launcher kept exactly one actor through Parsec to Lore Editor and back,
preserved its position, and did not show the route-level Lore Editor loading fallback. Animated scruff drag,
keyboard pickup/movement/release, direct 96 by 96 bed and cage drags from habitat to viewport, furniture
keyboard movement, and full toss through bounce and settled recovery all passed. Furniture excursions no
longer collapse the expanded habitat. Ordinary settings persisted across reload and browser logs contained no
warnings or errors.

- [ ] **Step 4: Hand off the real pointer gates**

Require explicit pass/fail for habitat pickup, carry-only release, gentle release, full toss/bounce/recovery, direct bed drag, direct cage drag, drop targets, cage latch/release, navigation stability, and foreground-tab ownership.

Maintainer automation now passes habitat pickup, gentle release, full toss/bounce/recovery, direct bed and
cage excursion drags, navigation stability, and keyboard equivalents. Zoe's physical pointer-feel approval,
carry-only feel, bed/cage drop-target feel, cage latch/release feel, and genuine background-tab ownership remain
explicit acceptance gates.

- [x] **Step 5: Restore ordinary profile defaults**

Restore edge-biased presence, rare chatter, gentle momentum, expressive reactions, animation, audio enabled, and reduced distraction disabled.

Evidence (2026-08-25): the visible controls and a reload both report edge-biased presence, rare chatter,
gentle momentum, expressive reactions, playful/lightly-flirtatious tone, compact log, animation, audio enabled,
and reduced distraction disabled. Excursion consent remains unconfigured so Parsec does not invade before the
user interacts and chooses a policy.

- [ ] **Step 6: Record completion truthfully**

Mark Task 9 complete only if every automated gate and real pointer check passes. Otherwise leave each failed gate open with exact reproduction evidence.

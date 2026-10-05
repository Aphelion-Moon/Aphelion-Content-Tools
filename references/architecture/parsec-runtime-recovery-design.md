# Parsec Runtime Recovery Design

**Status:** Approved in chat on 2026-08-25; awaiting written-contract confirmation before implementation.

## Purpose

Recover Parsec's companion interactions after the production-launcher acceptance pass exposed disappearing
actors, habitat resets, page-wide flicker, unusable furniture manipulation, nonfunctional toss physics, and
visually inconsistent production artwork. The recovery preserves the SPA shell, shared component contracts,
Parsec's feedback authority, configurable behavior, local companion profile, and the approved lightweight
companion feature set.

## Acceptance failures and confirmed causes

- `Parsec.tsx` renders separate habitat and viewport actor instances. A `grabbed` intent immediately changes
  the reducer location to `transition`, which removes the pointer-owning habitat actor before the gesture can
  continue.
- The companion-state subscription chooses a new random safe perch on every publication while the location is
  roaming or perched. Held movement, clip progress, and unrelated state updates can therefore teleport the
  visible actor.
- `physics.ts` contains release integration, but production UI/runtime code never calls `stepRelease`.
  Full-tossing mode currently changes the selected release clip without moving the actor through space.
- Furniture is manipulated through a detached `Move` button. Its visible art is pointer-inert and therefore
  does not satisfy direct manipulation.
- SS13 object frames are centered without scaling inside 96 by 96 cells. Native 32-pixel furniture occupies
  only a small portion of the rendered object box.
- Manifest validation proves structural completeness, provenance, dimensions, anchors, and frame counts. It
  does not measure stray pixels, inconsistent occupied bounds, baseline jitter, palette discontinuity, or
  animation continuity. Passing the validator did not establish production visual quality.

## Recovery sequence

Interaction recovery and asset recovery are separate gates. The runtime is stabilized first so artwork can be
reviewed in its real presentation instead of an unreliable renderer.

### 1. Persistent actor and coordinate ownership

The shell will render exactly one persistent Parsec actor instance. It remains mounted while Parsec is in the
habitat, roaming, held, released, landing, resting on the bed, or inside the cage. Habitat and viewport are
destinations within one viewport coordinate model, not separate component owners.

The actor controller owns:

- current viewport-space position;
- pointer gesture identity and recent pointer samples;
- stable destination/perch selection;
- release simulation state; and
- the current presentation phase: resting, held, airborne, landing, or recovering.

Reducer state continues to own semantic companion behavior, personality reactions, clips, consent, and
furniture confinement. Visual movement does not cause the actor component to be replaced.

Habitat-local coordinates are converted to viewport coordinates when the habitat bounds change. A habitat
destination is recalculated only for an explicit destination change or layout invalidation. Ordinary reducer
publications do not randomize position.

### 2. Pointer handling and autonomous behavior

Pointer capture stays on the persistent actor for the complete grab gesture. The scruff remains the semantic
and accessible pickup target, while its hit area follows the current frame's scruff anchor.

While a direct pointer gesture, release simulation, landing clip, or recovery clip is active:

- autonomous scheduling cannot move or replace Parsec;
- safe-perch selection cannot run;
- feedback may queue according to the existing reducer rules; and
- route changes cannot reset the actor position.

Keyboard pickup and movement remain supported. Reduced-motion and carry-only modes release at the current
position without inertial travel.

### 3. Real release physics

The actor controller will drive `stepRelease` from `requestAnimationFrame` using elapsed seconds and clamped
viewport bounds. Gentle mode uses damped travel. Full-tossing mode uses gravity and bounded bounce. Simulation
ends when velocity is below the tested settling threshold or the maximum tested duration is reached.

The semantic clip sequence remains:

1. release drop or toss;
2. landing recover or landing bounce;
3. landing recover after a bounce; and
4. ordinary resting or roaming state.

The visible actor follows the simulated position throughout that sequence. Physics cannot activate application
controls and cannot move Parsec outside the available viewport.

### 4. Direct furniture manipulation

The visible nontransparent bounds of the bed or cage become the pointer drag surface. No detached visual Move
button is shown. Each item remains an accessible control with its existing label and keyboard movement support;
visible focus is drawn around the object rather than a separate handle.

Furniture uses the same viewport coordinate model as Parsec. A drag starts without changing anchors. On release,
the destination is selected from the pointer position:

- inside the expanded habitat: `habitat`;
- outside the habitat: `app-edge`.

Persisted positions are normalized against their owning region and clamped so the visible artwork remains
reachable. Returning furniture home restores the existing profile defaults.

### 5. Furniture art scale

SS13 object preparation will crop transparent padding, scale the occupied pixels by an explicit per-object
nearest-neighbor factor, and place the result on the 96 by 96 logical canvas. Bed and cage variants use one
shared scale and baseline so open, locked, and occupied states do not jump.

Source frames, provenance, hashes, and licensing remain recorded. Derived scale, crop, and placement metadata
are added to the asset record and generated source inventory.

### 6. Animation quality recovery

The current creative atlases are treated as unreviewed candidates despite their structurally resolved manifest
status. Production keeps only frames that pass both automated checks and an in-app review. A smaller coherent
set may temporarily serve multiple semantic clips; unique artwork is not retained merely to satisfy a planned
frame count.

Automated visual checks cover:

- unexpected disconnected alpha components and border residue;
- occupied alpha bounds that are implausibly small or inconsistent within a clip;
- feet-baseline and body-center jitter beyond the documented tolerance;
- anatomical left-eye neon-pink and right-eye Supermatter-yellow continuity where both eyes are visible;
- palette outliers introduced by preparation; and
- cross-frame scale discontinuities within a clip.

Automated checks do not certify artistic quality. Each atlas also receives a native-size contact sheet, an
enlarged nearest-neighbor contact sheet, an animated motion review, and an in-app review against the actual
habitat and roaming backgrounds. Rejected frames remain outside the production manifest with their reason
recorded in `references/parsec-asset-register.md`.

## Component boundaries

- `Parsec.tsx` composes the persistent actor, habitat, toolbar, radio, invitation, and furniture without
  implementing gesture or physics math.
- A focused actor-controller module owns coordinates, gesture lifecycle, release simulation, and destination
  stability.
- `ParsecSprite.tsx` renders the current frame/effect and exposes the accessible scruff target. It does not own
  a competing semantic location state.
- `ParsecRoamingLayer.tsx` becomes a pointer-inert viewport presentation layer for the single actor and directly
  draggable furniture.
- `companionReducer.ts` continues to own semantic transitions and clip choreography. Location changes do not
  imply component replacement.
- `physics.ts`, `geometry.ts`, and `safeRegions.ts` remain framework-independent and receive focused behavioral
  tests.
- `tools/parsec_assets/` owns deterministic crop, scale, visual lint, contact-sheet, and motion-review outputs.

## Testing and acceptance

Implementation follows test-first cycles. Before production changes, failing tests must reproduce:

- a grab beginning in the habitat retains the same actor DOM node through movement and release;
- state publications during a gesture do not change the actor's pointer owner or position unexpectedly;
- release velocity advances visible coordinates and completes the landing/recovery sequence;
- route or habitat expansion changes do not reset an active or settled actor;
- dragging directly on bed and cage art updates the correct furniture without a detached handle;
- furniture crosses between habitat and app-edge coordinate spaces and remains reachable;
- bed and every cage state share approved occupied bounds, scale, and baseline; and
- visual lint rejects known residue, scale discontinuity, baseline jitter, and incorrect eye continuity fixtures.

Focused tests are followed by the full frontend suite, typecheck, production build, asset tests, resolved-manifest
validation, documentation checks, and `git diff --check`.

The real `Launch Aphelion Content Tools.cmd` path must then pass a user-visible pointer acceptance run:

1. pick Parsec up from the habitat without disappearance, reset, or flicker;
2. carry her across the app and release in carry-only, gentle, and full-tossing modes;
3. observe full toss, landing, bounce, recovery, and settled position;
4. drag bed and cage directly by their artwork between habitat and app edge;
5. drop Parsec onto bed and into the cage, latch and release her;
6. navigate between tools without duplicating or resetting Parsec; and
7. verify foreground-tab autonomous ownership without simultaneous background behavior.

No creative-sprint task is complete until these real pointer checks pass. Automated structural validation cannot
substitute for this acceptance gate.

## Compatibility and non-goals

- Preserve the Solid SPA shell, tool registry, shared store, typed API client, live connection, shared search,
  shared references, Parsec radio, durable activity journal, and `/parsec` settings route.
- Preserve all approved configuration choices, including habitat-only, edge-biased, intrusive, reduced
  distraction, personality, reaction intensity, handling physics, audio, motion, bed, and cage behavior.
- Do not add product behavior to rollback-only legacy pages.
- Do not commit, push, reset, checkout, merge, or alter unrelated working-tree changes.
- Do not accept an asset solely because it fills a manifest slot or passes structural validation.

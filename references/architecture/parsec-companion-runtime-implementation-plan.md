# Parsec Companion Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan inline, task by task. Do not dispatch subagents without Zoe's explicit approval. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the deterministic, persistent, single-tab companion runtime that drives Parsec's behavior, animation manifests, familiarity, and audio without taking ownership from the existing feedback coordinator.

**Architecture:** A pure reducer consumes typed companion intents and produces layered state plus declarative effects. Browser adapters separately own scheduling, local profile persistence, active-tab election, DOM rendering, and Howler playback. The current sprite sheet remains a required fallback.

**Tech Stack:** SolidJS 1.9, TypeScript 5.7, Vitest 3, DOM/CSS transforms, native Web Locks and BroadcastChannel APIs, Howler core, versioned JSON-compatible manifests.

**Spec:** [`references/architecture/parsec-companion-design.md`](parsec-companion-design.md)

## Global Constraints

- Mount one persistent companion through the existing `AppShell`; never create a second global store or feedback coordinator.
- The companion cannot execute feature APIs, activate controls, mutate selected context, or edit records.
- Default presence is habitat-only until the one-time excursion invitation is answered.
- Default roaming after consent is edge-biased; cursor attention is passive until play begins.
- Personality is playful-flirtatious within the approved nonsexual boundary and remains configurable.
- Audio is enabled by default after browser unlock, at 30% master and 20% rare-idle relative volume.
- Only the elected active tab may schedule autonomous behavior or audio.
- Missing assets fall back to the current `parsec.png` frame mappings and text labels.
- Add behavioral tests before behavior changes; leave work uncommitted; do not dispatch agents.

---

## File structure

### New files

- `webapp/frontend/src/lib/parsec/assets.ts` and `.test.ts` — versioned animation/audio/object manifest contracts and validation.
- `webapp/frontend/src/lib/parsec/companionTypes.ts` — layered state, intents, effects, settings, and profile types.
- `webapp/frontend/src/lib/parsec/companionReducer.ts` and `.test.ts` — pure state transitions and effect production.
- `webapp/frontend/src/lib/parsec/companionScheduler.ts` and `.test.ts` — deterministic weighted eligibility and cooldowns.
- `webapp/frontend/src/lib/parsec/profile.ts` and `.test.ts` — versioned local profile, migration, import/export, quarantine.
- `webapp/frontend/src/lib/parsec/tabCoordinator.ts` and `.test.ts` — one active-tab lease.
- `webapp/frontend/src/lib/parsec/audio.ts` and `.test.ts` — injected Howler boundary, channels, unlock, cooldown, visibility.
- `webapp/frontend/src/lib/parsec/runtime.ts` and `.test.ts` — browser adapters and lifecycle orchestration.
- `webapp/frontend/src/assets/parsec/manifest.v1.ts` — current-sheet fallback manifest.

### Modified files

- `webapp/frontend/package.json` and lockfile — add `howler` and its TypeScript declarations if required.
- `webapp/frontend/src/lib/parsecEngine.ts` and `.test.ts` — consume validated manifest clips while keeping compatibility exports.
- `webapp/frontend/src/App.tsx` — start and dispose one runtime.
- `webapp/frontend/src/components/AppShell.tsx` — provide the persistent habitat/roaming anchors only.
- `webapp/frontend/src/lib/parsec/coordinator.ts` — emit feedback intents to the runtime after presentation acceptance.
- `webapp/frontend/src/tools/parsec/ParsecPage.tsx` and tests — profile, audio, personality, consent, and runtime diagnostics.

### Core interfaces

```ts
export interface CompanionState {
	readonly activity: 'resting' | 'observing' | 'responding' | 'playing' | 'roaming' | 'held' | 'landing' | 'returning' | 'sleeping';
	readonly mood: 'calm' | 'curious' | 'excited' | 'pouty' | 'anxious' | 'frustrated' | 'proud' | 'affectionate';
	readonly attention: { readonly kind: 'none' | 'cursor' | 'toy' | 'furniture' | 'feedback'; readonly id: string | null };
	readonly feedbackDuty: 'idle' | 'working' | 'success' | 'warning' | 'error';
	readonly location: CompanionLocation;
	readonly familiarity: 0 | 1 | 2 | 3;
	readonly clip: string;
	readonly queuedReaction: CompanionIntent | null;
}

export interface CompanionTransition {
	readonly state: CompanionState;
	readonly effects: readonly CompanionEffect[];
}

export function reduceCompanion(state: CompanionState, intent: CompanionIntent): CompanionTransition;
```

### Task 1: Define and validate asset manifests with current-sheet fallback

**Files:**
- Create: `webapp/frontend/src/lib/parsec/assets.ts`
- Create: `webapp/frontend/src/lib/parsec/assets.test.ts`
- Create: `webapp/frontend/src/assets/parsec/manifest.v1.ts`
- Modify: `webapp/frontend/src/lib/parsecEngine.ts`
- Modify: `webapp/frontend/src/lib/parsecEngine.test.ts`

**Interfaces:**
- Produces: `ParsecAssetManifest`, `AnimationClip`, `AnimationFrame`, `SoundCue`, `ObjectAsset`, `validateParsecManifest(manifest)`, `resolveClip(id, manifest)`, and `coreFallbackManifest`.
- Consumes: current `parsec.png`, `72 x 51` frame coordinates, and `FRAME_SETS` behavior.

- [ ] **Step 1: Write failing validation and fallback tests**

```ts
it('rejects a looping clip with no frames or reduced-motion representative', () => {
	expect(validateParsecManifest(invalidManifest)).toEqual(expect.arrayContaining([
		'clips.idle.frames must contain at least one frame',
	]));
});

it('maps every requested clip to itself or an explicit current-sheet fallback', () => {
	expect(resolveClip('search-sniff', coreFallbackManifest).id).toBe('working-patrol');
	expect(resolveClip('unknown', coreFallbackManifest).id).toBe('seated-idle');
});
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/assets.test.ts src/lib/parsecEngine.test.ts`

Expected: FAIL because manifest contracts do not exist.

- [ ] **Step 3: Implement schema version 1**

Require logical canvas width/height, source image, license/provenance ID, clips, named frames, per-frame
duration, loop mode, interruptibility, reduced-motion frame, anchors, sound cues, and fallback. Validate
finite coordinates, positive durations, unique IDs, existing referenced frames, and an acyclic fallback
chain. Build `coreFallbackManifest` from the current four rows without moving coordinates.

- [ ] **Step 4: Keep compatibility functions delegating to the manifest**

`resolveState`, `nextFrameIndex`, and existing exported constants remain available until the habitat plan
migrates their callers. Tests prove identical current-sheet background positions.

- [ ] **Step 5: Run focused tests and typecheck**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/assets.test.ts src/lib/parsecEngine.test.ts`

Run: `npm --prefix webapp/frontend run typecheck`

Expected: PASS.

### Task 2: Implement the pure layered companion reducer

**Files:**
- Create: `webapp/frontend/src/lib/parsec/companionTypes.ts`
- Create: `webapp/frontend/src/lib/parsec/companionReducer.ts`
- Create: `webapp/frontend/src/lib/parsec/companionReducer.test.ts`

**Interfaces:**
- Consumes: Task 1 clip IDs and fallbacks.
- Produces: `initialCompanionState(profile)`, `reduceCompanion(state, intent)`, `CompanionIntent`, `CompanionEffect`, and `CompanionSettings`.

- [ ] **Step 1: Write failing priority, consent, holding, and confinement tests**

```ts
it('queues a critical reaction while held and performs it after release', () => {
	const held = reduceCompanion(initial, { type: 'grabbed', point }).state;
	const warned = reduceCompanion(held, { type: 'feedback', duty: 'error', eventId: 'e1' }).state;
	expect(warned.activity).toBe('held');
	expect(warned.queuedReaction?.type).toBe('feedback');
	expect(reduceCompanion(warned, { type: 'released', velocity: zero }).state.feedbackDuty).toBe('error');
});

it('never self-releases from a closed cage', () => {
	const caged = stateAt({ kind: 'cage', closed: true });
	expect(reduceCompanion(caged, { type: 'autonomous-tick', now: 10 }).state.location).toEqual(caged.location);
});

it('does not roam before excursion consent', () => {
	expect(reduceCompanion(unconfigured, { type: 'autonomous-tick', now: 10 }).effects)
		.not.toContainEqual(expect.objectContaining({ type: 'begin-roam' }));
});
```

- [ ] **Step 2: Run reducer tests**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/companionReducer.test.ts`

Expected: FAIL because the reducer does not exist.

- [ ] **Step 3: Implement explicit transitions and declarative effects**

Effects are limited to `play-clip`, `play-sound`, `schedule-intent`, `cancel-schedule`, `move-to`,
`append-companion-line`, `update-profile`, and `request-invitation`. The reducer never calls time, random,
DOM, storage, audio, or coordinator APIs. Held state defers feedback animation but not log delivery. Closed
cage ignores autonomous exit intents. Bed accepts explicit timeout/voluntary modes without care penalties.

- [ ] **Step 4: Add personality-dependent handling reactions**

Map movement speed, repeat count, mood, familiarity, initiated-play, tone, and expressiveness to stable
reaction intent IDs. Tests assert the approved nonsexual boundary by checking that generated copy comes
only from reviewed line IDs, never free transformation.

- [ ] **Step 5: Run reducer tests and typecheck**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/companionReducer.test.ts`

Run: `npm --prefix webapp/frontend run typecheck`

Expected: PASS.

### Task 3: Add deterministic autonomous scheduling and soft familiarity

**Files:**
- Create: `webapp/frontend/src/lib/parsec/companionScheduler.ts`
- Create: `webapp/frontend/src/lib/parsec/companionScheduler.test.ts`

**Interfaces:**
- Consumes: Task 2 state/settings and an injected `RandomSource`.
- Produces: `eligibleBehaviors(context)`, `chooseBehavior(context, random)`, `nextBehaviorDelay(settings, random)`, and `familiarityAfterInteraction(profile, interaction)`.

- [ ] **Step 1: Write failing eligibility and repetition tests**

```ts
it('suppresses autonomous play while typing, hidden, caged, or handling an error', () => {
	for (const context of blockedContexts) expect(eligibleBehaviors(context)).toEqual([]);
});

it('keeps ordinary cursor chasing ineligible until play starts', () => {
	expect(eligibleBehaviors(edgeBiasedContext)).not.toContain('cursor-chase');
	expect(eligibleBehaviors({ ...edgeBiasedContext, playInitiated: true })).toContain('cursor-chase');
});

it('unlocks variants without exposing points or decay', () => {
	const next = familiarityAfterInteraction(profile, { kind: 'ball-returned', at: 100 });
	expect(next.band).toBeGreaterThanOrEqual(profile.band);
	expect(next).not.toHaveProperty('xp');
	expect(next).not.toHaveProperty('hunger');
});
```

- [ ] **Step 2: Run scheduler tests and confirm failure**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/companionScheduler.test.ts`

- [ ] **Step 3: Implement weighted selection with named cooldowns**

Return an empty set whenever visibility, typing, critical feedback, consent, cage, reduced distraction, or
focus rules block behavior. Record recent behavior IDs and per-family cooldown timestamps. Familiarity
uses bounded counters internally but exports only band, preferences, and discovered reaction IDs.

- [ ] **Step 4: Run focused tests**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/companionScheduler.test.ts`

Expected: PASS with injected deterministic random sequences.

### Task 4: Add versioned profile persistence and active-tab ownership

**Files:**
- Create: `webapp/frontend/src/lib/parsec/profile.ts`
- Create: `webapp/frontend/src/lib/parsec/profile.test.ts`
- Create: `webapp/frontend/src/lib/parsec/tabCoordinator.ts`
- Create: `webapp/frontend/src/lib/parsec/tabCoordinator.test.ts`
- Modify: `webapp/frontend/src/lib/parsec/settings.ts`
- Modify: `webapp/frontend/src/lib/parsec/settings.test.ts`

**Interfaces:**
- Consumes: Task 2 `CompanionSettings` and Task 3 familiarity data.
- Produces: `CompanionProfileV1`, `loadCompanionProfile(storage)`, `saveCompanionProfile(storage, profile)`, `exportCompanionProfile`, `importCompanionProfile`, and `createTabCoordinator(environment)`.

- [ ] **Step 1: Write failing default, migration, corruption, and lease tests**

```ts
it('defaults to uninvited, rare chatter, edge-biased recommendation, and approved audio levels', () => {
	const profile = loadCompanionProfile(emptyStorage);
	expect(profile.consent).toBe('unconfigured');
	expect(profile.settings.idleChatter).toBe('rare');
	expect(profile.settings.audio.master).toBe(0.3);
	expect(profile.settings.audio.rareIdle).toBe(0.2);
});

it('elects only one autonomous owner and hands off an expired lease', () => {
	const first = createTabCoordinator(sharedHarness('a'));
	const second = createTabCoordinator(sharedHarness('b'));
	expect([first.isLeader(), second.isLeader()].filter(Boolean)).toHaveLength(1);
	harness.expireLeader();
	expect(second.tryAcquire()).toBe(true);
});
```

- [ ] **Step 2: Run focused tests**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/profile.test.ts src/lib/parsec/tabCoordinator.test.ts src/lib/parsec/settings.test.ts`

Expected: FAIL on missing modules.

- [ ] **Step 3: Implement profile schema and migrations**

Use one localStorage document key `aphelion-parsec-profile` for small profile data. Migrate the existing
motion and idle-chatter keys exactly once. Preserve recognized fields, clamp normalized positions and
volumes, reject unknown enum values, and save corrupt source text under a timestamped quarantine key
before restoring defaults. Profile export excludes activity history.

- [ ] **Step 4: Implement tab coordination**

Prefer `navigator.locks.request('aphelion-parsec-autonomous', { ifAvailable: true })`. Fall back to a
BroadcastChannel heartbeat plus localStorage lease containing owner ID and expiry. Loss of visibility
releases or stops renewing leadership. Direct interaction in a visible tab requests leadership without
stealing an unexpired active interaction.

- [ ] **Step 5: Run focused tests and typecheck**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/profile.test.ts src/lib/parsec/tabCoordinator.test.ts src/lib/parsec/settings.test.ts`

Run: `npm --prefix webapp/frontend run typecheck`

Expected: PASS.

### Task 5: Add Howler audio and compose the browser runtime

**Files:**
- Modify: `webapp/frontend/package.json`
- Modify: frontend lockfile
- Create: `webapp/frontend/src/lib/parsec/audio.ts`
- Create: `webapp/frontend/src/lib/parsec/audio.test.ts`
- Create: `webapp/frontend/src/lib/parsec/runtime.ts`
- Create: `webapp/frontend/src/lib/parsec/runtime.test.ts`
- Modify: `webapp/frontend/src/App.tsx`
- Modify: `webapp/frontend/src/lib/parsec/coordinator.ts`
- Modify: `webapp/frontend/src/tools/parsec/ParsecPage.tsx`
- Modify: `webapp/frontend/src/tools/parsec/ParsecPage.test.tsx`

**Interfaces:**
- Consumes: Tasks 1–4 manifests, reducer, scheduler, profile, and tab coordinator.
- Produces: `CompanionAudioBus`, `createCompanionRuntime(environment)`, `startCompanionRuntime()`, and `stopCompanionRuntime()`.

- [ ] **Step 1: Add failing audio policy tests with an injected player**

```ts
it('unlocks after direct interaction and applies master and category volume', async () => {
	const bus = createCompanionAudioBus(fakePlayer, profile.settings.audio);
	await bus.unlock();
	bus.play(cue('bark', 'voice', 0.5));
	expect(fakePlayer.lastVolume).toBeCloseTo(0.15);
});

it('suppresses rare idle audio while hidden, typing, muted, or not tab leader', () => {
	for (const context of blockedAudioContexts) expect(bus.canPlay(idleCue, context)).toBe(false);
});
```

- [ ] **Step 2: Add Howler and run the failing tests**

Run: `npm --prefix webapp/frontend install howler`

Run: `npm --prefix webapp/frontend install --save-dev @types/howler`

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/audio.test.ts src/lib/parsec/runtime.test.ts`

Expected: dependency and lockfile update succeeds; tests FAIL because the bus/runtime are not implemented.

- [ ] **Step 3: Implement the audio adapter**

Lazy-load cues, support audio-sprite aliases, cap concurrent ordinary effects at two, give alerts one
reserved slot, apply per-cue and per-category cooldowns, and stop/suppress idle sounds on hidden state.
An autoplay rejection leaves audio enabled-but-locked and exposes a non-error prompt on the Parsec page.

- [ ] **Step 4: Compose one runtime lifecycle**

Start after the shared store exists; load profile, open tab coordination, subscribe to accepted feedback
intents, schedule eligible behavior only as leader, execute reducer effects through adapters, and dispose
every timer/listener/channel/audio instance on shutdown. No component creates its own autonomous timer.

- [ ] **Step 5: Add settings controls without building habitat behavior yet**

Expose Presence, Personality, Feedback, Audio, Accessibility, and Data groups on `/parsec`. Existing
motion and idle settings edit the unified profile. Tests cover defaults, persistence, mute, category
levels, consent state, and profile export/import separation.

- [ ] **Step 6: Run the plan gates**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec src/lib/parsecEngine.test.ts src/tools/parsec`

Run: `npm --prefix webapp/frontend run typecheck`

Run: `npm --prefix webapp/frontend run build`

Run: `git diff --check`

Expected: all pass. Leave changes uncommitted.

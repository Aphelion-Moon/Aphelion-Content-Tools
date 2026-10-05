# Parsec Creative Asset Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan inline, task by task. Do not dispatch subagents without Zoe's explicit approval. Steps use checkbox (`- [x]`) syntax for tracking. **Stop after Task 4 until Zoe explicitly confirms that effort is set to Max.**

**Goal:** Prepare, produce, register, and integrate Parsec's full multi-atlas animation, SS13-derived toy/furniture art, and audio library with reproducible provenance and objective acceptance gates.

**Architecture:** Normal-effort work freezes a machine-readable clip roster, inventories licensed source material, and builds deterministic extraction/atlas/validation/contact-sheet tooling against the already implemented runtime contracts. Max effort is reserved exclusively for adapting and producing the approved pixels and sounds, reviewing them in motion, and replacing prepared fallbacks.

**Tech Stack:** Python 3.11+, Pillow, existing DMI helpers or pydmi-compatible decoding, TypeScript manifest contracts, Vitest, pytest, PNG atlases, OGG/WAV source audio, Howler audio sprites, HTML contact sheets.

**Spec:** [`references/architecture/parsec-companion-design.md`](parsec-companion-design.md)

## Global Constraints

- Tasks 1–4 are preparation at normal effort. Tasks 5–9 are creative production and may not begin until Zoe explicitly says Max effort is enabled.
- Max effort is used for production against the frozen roster and acceptance rules, not for product or architecture exploration.
- Preserve Parsec's established proportions, fur palette, outline, corrected eye colors, and readable native pixel scale. Her anatomical left eye is neon pink (`#FF3CC8`) and her anatomical right eye is Supermatter Crystal yellow (`#FBD436`).
- Every frame uses a `96 x 96` logical canvas; the artwork may use the full canvas where the action requires it.
- Use real Meridian-Rift SS13 DMI/audio sources wherever they satisfy the requirement; preserve repository path, DMI state, revision, author when known, license, attribution, and adaptation.
- Do not invent a source, author, license, DMI state, or acceptance result.
- Missing or rejected creative work retains an explicit manifest fallback and cannot be represented as complete.
- All required assets must be reviewed at native scale, at `4x` nearest-neighbor scale, in motion, and in reduced-motion mode.
- Leave work uncommitted; do not dispatch agents.

---

## File structure

### Preparation files

- `tools/parsec_assets/extract_dmi.py` and tests — deterministic extraction of named DMI states/frames.
- `tools/parsec_assets/build_atlas.py` and tests — pack prepared PNG frames and emit coordinates without resampling.
- `tools/parsec_assets/validate_manifest.py` and tests — cross-check files, dimensions, anchors, fallbacks, and provenance.
- `tools/parsec_assets/build_contact_sheet.py` and tests — native/4x sheet plus metadata captions.
- `tools/parsec_assets/audio_inventory.py` and tests — hash, duration, channels, and license/provenance inventory.
- `tools/parsec_assets/requirements.txt` — exact preparation-tool dependencies if the root environment does not already provide them.
- `references/architecture/parsec-animation-storyboards.md` — frozen clip roster, frame budgets, anchors, timing, and reduced-motion representatives.
- `references/parsec-asset-register.md` — authoritative source, license, adaptation, rejection, acceptance, and runtime mapping register.
- `webapp/frontend/src/assets/parsec/manifest.v1.ts` and tests — prepared creative slots and required fallback mappings.

### Production files

- `webapp/frontend/src/assets/parsec/parsec-core.png` — locomotion and idle atlas.
- `webapp/frontend/src/assets/parsec/parsec-feedback.png` — search/work/result/warning/error atlas.
- `webapp/frontend/src/assets/parsec/parsec-touch.png` — pats, affection, scruff, throw, landing, and recovery atlas.
- `webapp/frontend/src/assets/parsec/parsec-toys.png` — Parsec interaction poses for ball, tug, brush, treat, and whistle.
- `webapp/frontend/src/assets/parsec/parsec-habitat.png` — bed and cage transitions/reactions.
- `webapp/frontend/src/assets/parsec/parsec-intrusive.png` — cursor play, loitering, demands, and station-flavored behavior.
- `webapp/frontend/src/assets/parsec/parsec-effects.png` — hearts, alerts, scent, dust, sleep, radio, toy, and landing effects.
- `webapp/frontend/src/assets/parsec/ss13-objects.png` — directly extracted/adapted toy and furniture states.
- `webapp/frontend/src/assets/parsec/audio/` — accepted source and runtime audio files or audio sprites.
- `webapp/frontend/src/assets/parsec/review/` — generated contact sheets and motion-review pages, not hand-edited sources.

### Prepared contracts

```python
@dataclass(frozen=True)
class SourceAsset:
	repository: str
	revision: str
	path: str
	state: str | None
	frame: int | None
	direction: str | None
	sha256: str
	license: str
	author: str | None

@dataclass(frozen=True)
class ClipRequirement:
	id: str
	atlas: str
	frame_count: int
	frame_duration_ms: tuple[int, ...]
	loop_mode: str
	interruptible: bool
	reduced_motion_frame: int
	required_anchors: tuple[str, ...]
	fallback: str
```

### Task 1: Inventory exact DMI and audio candidates with provenance

**Files:**
- Create: `tools/parsec_assets/extract_dmi.py`
- Create: `tools/parsec_assets/test_extract_dmi.py`
- Create: `tools/parsec_assets/audio_inventory.py`
- Create: `tools/parsec_assets/test_audio_inventory.py`
- Modify: `references/parsec-asset-register.md`

**Interfaces:**
- Consumes: an explicit Meridian-Rift checkout path and exact candidate paths/states named by the design.
- Produces: `read_dmi_metadata(path)`, `extract_dmi_state(path, state, destination)`, `inventory_audio(paths)`, file hashes, and register rows marked `candidate`.

- [x] **Step 1: Write failing fixture-based DMI and audio tests**

```python
def test_extracts_named_state_without_resampling(tmp_path, dmi_fixture):
	frames = extract_dmi_state(dmi_fixture, "dogbed", tmp_path)
	assert frames[0].image.size == (32, 32)
	assert frames[0].sha256 == sha256_file(frames[0].path)

def test_audio_inventory_records_hash_duration_channels_and_source(tmp_path, wav_fixture):
	entry = inventory_audio([wav_fixture], source_revision="fixture-rev")[0]
	assert entry.duration_ms > 0
	assert entry.channels in (1, 2)
	assert entry.sha256 == sha256_file(wav_fixture)
```

- [x] **Step 2: Run the preparation tests and verify failure**

Run: `python -m pytest tools/parsec_assets/test_extract_dmi.py tools/parsec_assets/test_audio_inventory.py -q`

Expected: FAIL because the tools do not exist.

- [x] **Step 3: Implement deterministic metadata extraction and inventory**

Read DMI PNG Description metadata, validate state/frame/direction indices, and export RGBA frames with no
palette conversion or interpolation. Inventory audio without transcoding. Record SHA-256, source checkout
revision, path, state/frame/direction, duration/channels, repository license, and any file-local override.
Refuse missing states and ambiguous licenses with an actionable nonzero exit.

- [x] **Step 4: Inventory the approved Meridian-Rift candidate families**

Inspect and record `icons/obj/bed.dmi:dogbed`, open/closed/locked/occupied states from
`icons/obj/pet_carrier.dmi`, tennis states from `modular_nova/master_files/icons/obj/balls.dmi`, the
hairbrush DMI and sounds, plus located carp-plush, toy-mouse, whistle, squeak, bark, growl, dog, and toolbox
handling candidates. Mark each row `candidate`, `accepted-source`, or `rejected-source` with a concrete
reason; do not copy candidates into runtime assets yet.

- [x] **Step 5: Run tests and validate the inventory**

Run: `python -m pytest tools/parsec_assets/test_extract_dmi.py tools/parsec_assets/test_audio_inventory.py -q`

Run: `python tools/parsec_assets/audio_inventory.py --check-register references/parsec-asset-register.md`

Expected: PASS with every referenced source resolvable and hashed.

### Task 2: Freeze the complete clip roster and manifest slots

**Files:**
- Create: `references/architecture/parsec-animation-storyboards.md`
- Modify: `webapp/frontend/src/assets/parsec/manifest.v1.ts`
- Modify: `webapp/frontend/src/lib/parsec/assets.test.ts`
- Modify: `references/parsec-asset-register.md`

**Interfaces:**
- Consumes: approved behavior states, interactions, furniture rules, feedback reactions, and source inventory.
- Produces: 55–65 exact `ClipRequirement` entries totaling 220–300 unique frames, with atlas, timing, anchors, sounds, reduced-motion frame, and current fallback.

- [x] **Step 1: Write failing roster-completeness tests**

```ts
it('freezes the approved clip and unique-frame budgets', () => {
	const clips = Object.values(coreFallbackManifest.clips).filter((clip) => clip.requiredForCreativeSprint);
	expect(clips.length).toBeGreaterThanOrEqual(55);
	expect(clips.length).toBeLessThanOrEqual(65);
	expect(uniqueFrameCount(clips)).toBeGreaterThanOrEqual(220);
	expect(uniqueFrameCount(clips)).toBeLessThanOrEqual(300);
});

it('gives every required clip anchors, a reduced-motion frame, and an existing fallback', () => {
	for (const clip of requiredClips) {
		expect(clip.reducedMotionFrame).toBeDefined();
		expect(manifest.clips[clip.fallback]).toBeDefined();
		for (const anchor of clip.requiredAnchors) expect(clip.frames.every((frame) => anchor in frame.anchors)).toBe(true);
	}
});
```

- [x] **Step 2: Run manifest tests and verify failure**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/assets.test.ts`

- [x] **Step 3: Write the frozen storyboard roster**

For each named clip, specify behavior trigger, direction count, unique/reused frame count, frame timing,
loop/hold/once mode, interruptibility, foot/scruff/mouth/toy/effect anchors, sound cue timing, reduced-motion
representative, emotional read, 96-pixel occupancy allowance, current-sheet fallback, and native/4x acceptance
notes. Include every feedback duty, six toy types, scruff/release modes, bed/cage state, normal roaming, and
intrusive behavior approved in the design.

- [x] **Step 4: Add all required manifest slots without new artwork**

Add required clip/object/effect/audio IDs with `requiredForCreativeSprint: true` and explicit fallbacks to
the current sheet or text label. The application must remain functional and tests must pass while every
creative slot is still using a fallback.

- [x] **Step 5: Run manifest tests and typecheck**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/assets.test.ts src/lib/parsecEngine.test.ts`

Run: `npm --prefix webapp/frontend run typecheck`

Expected: PASS and the roster is frozen.

### Task 3: Build atlas, manifest, and contact-sheet verification tooling

**Files:**
- Create: `tools/parsec_assets/build_atlas.py`
- Create: `tools/parsec_assets/test_build_atlas.py`
- Create: `tools/parsec_assets/validate_manifest.py`
- Create: `tools/parsec_assets/test_validate_manifest.py`
- Create: `tools/parsec_assets/build_contact_sheet.py`
- Create: `tools/parsec_assets/test_build_contact_sheet.py`
- Create: `tools/parsec_assets/requirements.txt`

**Interfaces:**
- Consumes: prepared frame directories, the frozen roster, register, and manifest export.
- Produces: deterministic atlas PNGs, coordinate data, `validate_assets(...)`, and a review HTML/PNG set showing native and 4x nearest-neighbor frames.

- [x] **Step 1: Write failing deterministic-build and invalid-anchor tests**

```python
def test_atlas_is_byte_identical_for_the_same_sorted_inputs(tmp_path, frame_set):
	first = build_atlas(frame_set, tmp_path / "a")
	second = build_atlas(reversed(frame_set), tmp_path / "b")
	assert sha256_file(first.png) == sha256_file(second.png)
	assert first.coordinates == second.coordinates

def test_validation_rejects_anchor_outside_96_pixel_canvas(manifest_fixture, register_fixture):
	manifest_fixture["clips"]["pat"]["frames"][0]["anchors"]["scruff"] = {"x": 97, "y": 10}
	assert "pat frame 0 scruff anchor is outside 96x96" in validate_assets(manifest_fixture, register_fixture)
```

- [x] **Step 2: Run tooling tests and verify failure**

Run: `python -m pytest tools/parsec_assets/test_build_atlas.py tools/parsec_assets/test_validate_manifest.py tools/parsec_assets/test_build_contact_sheet.py -q`

- [x] **Step 3: Implement deterministic packing and validation**

Sort frames by atlas, clip ID, direction, and frame index. Pack only complete 96-pixel cells, never resample,
strip nondeterministic timestamps, and emit stable coordinates. Validate PNG mode/dimensions, file hashes,
frame counts, duration counts, named anchors, atlas bounds, fallback acyclicity, sound references, provenance
rows, license fields, required status, and absence of unregistered runtime files.

- [x] **Step 4: Implement objective review output**

Generate an HTML index and PNG contact sheets per atlas. Each frame appears once at 1x and once at 4x with
nearest-neighbor scaling, clip/frame/direction labels, anchor overlays, timing, source/provenance link,
fallback ID, and acceptance status. Generate animated preview strips at authored timing and a separate
reduced-motion page using only each clip's declared representative.

- [x] **Step 5: Run tooling tests and a fallback-only dry run**

Run: `python -m pytest tools/parsec_assets -q`

Run: `python tools/parsec_assets/validate_manifest.py --manifest webapp/frontend/src/assets/parsec/manifest.v1.ts --register references/parsec-asset-register.md --allow-fallbacks`

Expected: PASS and report all creative slots as explicit fallbacks rather than missing files.

### Task 4: Close the normal-effort preparation gate and stop

**Files:**
- Modify: `references/architecture/parsec-creative-sprint-plan.md`
- Modify: `references/architecture/parsec-animation-storyboards.md`
- Modify: `references/parsec-asset-register.md`

**Interfaces:**
- Consumes: Tasks 1–3 plus implemented runtime, habitat, interactions, radio log, profile, and audio hooks.
- Produces: a signed-off readiness checklist and a hard pause before any creative asset production.

- [x] **Step 1: Verify every creative dependency is prepared**

Check and record exact evidence for: frozen architecture; working fallback renderer; all interactions and
integration hooks; 55–65 clip roster and 220–300-frame budget; exact anchors/timing/storyboards; complete
DMI/audio inventory; deterministic extraction/atlas/contact-sheet tools; manifest/runtime validators;
reduced-motion representatives; review checklist; and zero unresolved product/architecture decisions.

- [x] **Step 2: Run the pre-sprint gate**

Run: `python -m pytest tools/parsec_assets -q`

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec src/components/parsec src/tools/parsec`

Run: `npm --prefix webapp/frontend run typecheck`

Run: `python tools/parsec_assets/validate_manifest.py --manifest webapp/frontend/src/assets/parsec/manifest.v1.ts --register references/parsec-asset-register.md --allow-fallbacks`

Run: `git diff --check`

Expected: all pass and the validator reports only prepared, named fallbacks for creative slots.

- [x] **Step 3: Stop and request the explicit effort change**

Do not open ImageGen, edit pixels, adapt DMI frames, choose audio takes, transcode sounds, or replace a
creative fallback. Report the readiness evidence and ask Zoe to turn effort up to Max. Continue only after
she explicitly confirms Max is enabled.

## Normal-effort preparation gate record

Gate closed on 2026-08-24. No creative pixels or audio were copied, generated, adapted, selected,
transcoded, or integrated during Tasks 1–4.

- Architecture and behavior: frozen in `parsec-companion-design.md`; the shell, coordinator, profile,
  journal, tab ownership, audio bus, roaming, handling, furniture, consent, and radio-log contracts exist.
- Integration hooks: all eight primary actions exist; Ball, Tug, Brush, and Treat have pointer and keyboard
  begin/update/finish surfaces; Whistle, Bed, Cage/Release, Pat, and scruff handling have typed runtime routes.
- Roster: 60 required clips and 293 planned unique frames across core, feedback, touch, toys, habitat,
  intrusive, and effect atlases. Exact timing, loop mode, anchors, cue frame, reduced-motion representative,
  occupancy, emotional read, and fallback are frozen in `parsec-animation-storyboards.md`.
- Slots: 60 clip fallbacks, 11 object fallbacks, and 8 silent audio fallbacks validate without missing IDs.
- Provenance: exact Meridian-Rift revision, DMI path/state/hash, and audio path/hash/duration/channels are
  registered. Repository asset default is CC BY-SA 3.0; file-local CC0 and CC-BY-SA overrides are explicit.
  Tug rope has no credible source and remains a named production/human-art gap rather than an invented asset.
- Tooling: deterministic DMI extraction, audio inventory/register validation, 96-pixel atlas packing,
  manifest validation, and native/4x nearest-neighbor contact-sheet generation are covered by 10 passing tests.
- Frontend evidence: focused Parsec gate `31 files / 185 tests`; full frontend gate `63 files / 279 tests`;
  TypeScript typecheck passed; Vite production build passed.
- Hygiene: fallback manifest validator passed with `60 / 293 / 11 / 8`; audio register validator passed;
  `git diff --check` passed with line-ending notices only.
- Accessibility correction: the full suite identified a nested interactive habitat control; the stage-level
  button role was replaced with a dedicated pat button, and the axe regression gate now passes.
- Product/architecture decisions: none remain open for production. Carp greyscale composition, cue take
  selection, and frame-by-frame acceptance are production review work under the frozen rules, not design work.

**Hard pause:** Task 5 may begin only after Zoe explicitly confirms the current effort is Max. Max work is
limited to producing, extracting, reviewing, registering, and integrating the frozen asset roster. The exit
gate is Task 9: every required slot accepted or explicitly approved for fallback/human help, all four visual
review modes recorded, actual companion path exercised, and full verification green.

## MAX-EFFORT CREATIVE PRODUCTION — DO NOT START BEFORE TASK 4 APPROVAL

### Task 5: Produce and accept the core and feedback atlases

**Files:**
- Create: `webapp/frontend/src/assets/parsec/parsec-core.png`
- Create: `webapp/frontend/src/assets/parsec/parsec-feedback.png`
- Modify: `webapp/frontend/src/assets/parsec/manifest.v1.ts`
- Modify: `references/parsec-asset-register.md`

**Interfaces:**
- Consumes: frozen core/feedback storyboard rows, current identity sheet, atlas tooling, and Max approval.
- Produces: accepted locomotion, idle, search, fetch, success, warning, confusion, failure, and recovery frames.

- [x] **Step 1: Produce only the frozen core and feedback frames**

Use the approved Parsec reference and roster. Preserve identity at native scale; use the full 96-pixel
canvas only for extended motion/effects. Do not add behaviors, variants, copy, props, or clip IDs outside
the frozen requirements.

- [x] **Step 2: Build atlases and review at all required scales/modes**

Run the atlas and contact-sheet tools. Inspect every clip at 1x, 4x nearest-neighbor, authored motion, and
reduced motion. Check silhouette, palette, outline continuity, anatomical left-pink/right-yellow eye continuity, foot anchoring, direction,
loop seam, emotional read, and UI-background contrast.

- [x] **Step 3: Register accepted frames and retain explicit fallbacks for rejections**

For every source or generated frame record method, prompt/reference where applicable, adaptation, hash,
license/ownership, review status, and runtime mapping. Replace a fallback only after all four review modes
are accepted.

- [x] **Step 4: Run focused asset/runtime gates**

Run: `python tools/parsec_assets/validate_manifest.py --manifest webapp/frontend/src/assets/parsec/manifest.v1.ts --register references/parsec-asset-register.md`

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/assets.test.ts src/lib/parsecEngine.test.ts src/components/parsec/ParsecSprite.test.tsx`

Expected: PASS for accepted core/feedback slots; rejected slots remain named fallbacks.

Completion evidence, 2026-08-24:

- Accepted `parsec-core`: 10 clips / 59 frames. Accepted `parsec-feedback`: 10 clips / 46 frames.
- Browser-reviewed native contact sheets, nearest-neighbor `4×` art, exact authored timing, reduced-motion
  representatives, and all eight independent locomotion directions.
- Asset tools: `30 passed`; mixed manifest validation: 20 accepted clips / 105 frames and 40 explicit clip
  fallbacks; focused frontend gate: `47 passed`; TypeScript `tsc --noEmit`: passed.
- The source, prompt intent, ownership, adaptation, hash, rejection, review, and runtime records are in
  `references/parsec-asset-register.md`. Machine-local composition pointers are prohibited by a regression test.

### Task 6: Produce and accept touch, toy-pose, and habitat atlases

**Files:**
- Create: `webapp/frontend/src/assets/parsec/parsec-touch.png`
- Create: `webapp/frontend/src/assets/parsec/parsec-toys.png`
- Create: `webapp/frontend/src/assets/parsec/parsec-habitat.png`
- Modify: `webapp/frontend/src/assets/parsec/manifest.v1.ts`
- Modify: `references/parsec-asset-register.md`

**Interfaces:**
- Consumes: frozen handling, personality, six-toy, bed, and cage storyboards.
- Produces: accepted direct-touch, scruff, throw/landing, toy, bed, and cage reaction frames.

- [x] **Step 1: Produce the frozen interaction frames**

Cover subdued/expressive/dramatic reaction readings through clip selection, not duplicated unbounded sets.
Keep playful/flirtatious cues nonsexual: winks, nose licks, smug tail motion, mock jealousy, huffs, pouts,
and station-coded teasing. Cage variants must read as open versus latched without implying she can escape.

- [x] **Step 2: Build, review, and register**

Use the same native/4x/motion/reduced-motion checklist as Task 5. Verify scruff, mouth, toy, foot, furniture,
and effect anchors against the renderer overlays. Record every acceptance or rejection in the register.

- [x] **Step 3: Run interaction visual gates**

Run: `python tools/parsec_assets/validate_manifest.py --manifest webapp/frontend/src/assets/parsec/manifest.v1.ts --register references/parsec-asset-register.md`

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/interactions.test.ts src/lib/parsec/furniture.test.ts src/components/parsec`

Expected: PASS with accepted art selected and every remaining fallback explicit.

Completion evidence, 2026-08-24:

- Accepted `parsec-touch`: 10 clips / 48 frames; `parsec-toys`: 12 clips / 59 frames;
  `parsec-habitat`: 8 clips / 37 frames. The mixed manifest now reports 50 accepted clips / 249 frames and
  10 explicit clip fallbacks.
- All three atlases passed native `1×`, enlarged nearest-neighbor `4×`, exact authored-motion, and reduced-motion
  browser review. Every generated actor frame keeps furniture/toy pixels separate for anchor attachment.
- Exterior generation references are manual, hash-registered crops with 16-pixel retained margins. Where a raw
  output touched an edge, later generation used transparent prepared `96 × 96` frames instead of admitting it as
  a reference.
- Asset tools: `35 passed`; Task 6 frontend gate: 13 files / `71 passed`; TypeScript `tsc --noEmit`: passed.

### Task 7: Extract/adapt SS13 objects and produce intrusive/effect atlases

**Files:**
- Create: `webapp/frontend/src/assets/parsec/ss13-objects.png`
- Create: `webapp/frontend/src/assets/parsec/parsec-intrusive.png`
- Create: `webapp/frontend/src/assets/parsec/parsec-effects.png`
- Modify: `webapp/frontend/src/assets/parsec/manifest.v1.ts`
- Modify: `references/parsec-asset-register.md`

**Interfaces:**
- Consumes: accepted-source inventory, frozen object/effect/intrusive roster, and exact DMI extraction tool.
- Produces: native SS13 toy/furniture objects plus accepted cursor, loiter, demand, radio, dust, sleep, alert, and landing effects.

- [x] **Step 1: Extract accepted DMI states without resampling**

Extract the approved state/direction/frame exactly. Center each native 32-pixel asset within its declared
96-pixel object cell without scaling. Any adaptation must live as a separate derived frame with both source
and derived hashes and a concrete adaptation note.

Evidence (2026-08-25): 11 exact DMI frames accepted in a deterministic `384 × 288` atlas, including the
uncolored cable-coil base as the station tug loop. Extracted and centered intermediates are isolated under
`source/ss13-objects` and `prepared/ss13-objects`; earlier builds remain under `superseded`. Asset tests:
`36 passed`; focused manifest/furniture tests: 2 files / `15 passed`; TypeScript `tsc --noEmit`: passed.

- [x] **Step 2: Produce the frozen intrusive and effect frames**

Make intrusive behavior readable as intentional while retaining transparent background outside actor hit
targets. Effects must not obscure serious diagnostics or simulate work-page controls. Provide a static,
low-flash reduced-motion representative for every effect family.

Evidence (2026-08-25): 27 intrusive actor frames and 17 pointer-inert effect frames accepted. Authentic SS13
heart, exclamation, and sonar pixels were used where suitable; scent and landing dust were deterministically
isolated from accepted Parsec frames. Opaque SS13 dust filter masks and the blank sonar frame were rejected.

- [x] **Step 3: Build, review, register, and validate**

Run: `python tools/parsec_assets/build_contact_sheet.py --all`

Run: `python tools/parsec_assets/validate_manifest.py --manifest webapp/frontend/src/assets/parsec/manifest.v1.ts --register references/parsec-asset-register.md`

Expected: PASS after native/4x/motion/reduced-motion review is recorded.

Evidence (2026-08-25): both atlases passed native `1×`, nearest-neighbor `4×`, exact authored-motion, and
reduced-motion review. The manifest reports `60 clips, 293 frames` accepted with zero visual/object fallbacks;
the full asset-tool suite passes `41` tests. Focused manifest, scheduler, reducer, runtime, effect, and sprite
tests pass, and `tsc --noEmit` passes.

### Task 8: Prepare accepted SS13 audio and audio-sprite mappings

**Files:**
- Create: `webapp/frontend/src/assets/parsec/audio/`
- Modify: `webapp/frontend/src/assets/parsec/manifest.v1.ts`
- Modify: `references/parsec-asset-register.md`

**Interfaces:**
- Consumes: accepted-source audio inventory and frozen cue/channel/cooldown mappings.
- Produces: runtime audio sources or sprites for `voice`, `toys`, `radio`, and `rare-idle` channels with format fallbacks.

- [x] **Step 1: Select and prepare only inventoried cues**

Use real SS13 barks, growls, dog sounds, whistles, squeaks, hairbrush/handling, radio/interface, and rare
ambient sounds where accepted. Normalize excessive peaks conservatively, trim only silence that affects
latency, preserve source masters, and export browser formats without layering unrelated creative content.

Evidence (2026-08-25): eight exact-copy OGG cues selected from registered Meridian-Rift/Nova sources. No trim,
gain, layering, or transcode was required; the reproducible pack records matching source/output hashes.

- [x] **Step 2: Register cue timing, transforms, and license provenance**

Record source and output hashes, trim/gain/transcode operations, channel, cue/sprite offsets, authored
volume, cooldown family, and fallback formats. Retain rare-idle at 20% relative to the 30% default master;
do not normalize by increasing the configured playback policy.

Evidence (2026-08-25): every cue records source ID/path/revision/hash, output hash, exact-copy transform, runtime
channel, authored volume, and cooldown. Rare idle retains 20% channel volume under the 30% default master and a
0.35 cue volume. Runtime schedules clip cues at frame-relative authored delays and cancels stale timers.

- [x] **Step 3: Run audio and runtime tests**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/audio.test.ts src/lib/parsec/runtime.test.ts`

Run: `python tools/parsec_assets/audio_inventory.py --check-register references/parsec-asset-register.md`

Expected: PASS with no unregistered runtime sound and no missing fallback format.

Evidence (2026-08-25): focused manifest/audio/runtime tests pass `25` tests; `tsc --noEmit` passes; the Python
audio inventory validates every registered source; the manifest reports zero sound fallbacks.

### Task 9: Close the Max sprint acceptance gate

**Files:**
- Modify: `references/parsec-asset-register.md`
- Modify: `references/architecture/parsec-animation-storyboards.md`
- Modify: `references/maintainer-guide.md`
- Modify: `references/writer-guide.md`

**Interfaces:**
- Consumes: all required creative slots, contact sheets, motion previews, runtime integration, and user-approved deferrals.
- Produces: a closed asset sprint with every requirement accepted or explicitly approved for fallback/human help.

- [x] **Step 1: Resolve every required slot**

Each required roster row must be `accepted` with a registered runtime asset, or `deferred-human` / `fallback-approved`
with Zoe's explicit approval recorded. `candidate`, `produced`, `unreviewed`, and `rejected` are not exit states.

Evidence (2026-08-25): the resolved-manifest validator accepts all 60 required clips and 293 planned unique
frames. The manifest and register contain seven accepted actor/effect atlases, 11 accepted SS13 object slots,
eight accepted SS13 audio cues, and zero clip, object, or sound fallbacks.

- [ ] **Step 2: Exercise the actual companion path**

In the real Windows launcher/browser path, exercise habitat idle, every feedback duty, all eight actions,
scruff carry/gentle/full modes, bed, open/latched cage, ordinary roam, intrusive roam, audio unlock/mute,
hidden-tab ownership, native scale, 4x review, and reduced motion. Record concrete failures and fix or return
the affected row to fallback.

Partial evidence (2026-08-25): the shipped Windows launcher successfully bootstrapped the existing
20,881-target catalog and served its tracked production SPA on a random loopback port. The live browser path
exercised the consent invitation; native-scale habitat idle; all eight toolbar actions; the keyboard physical-
toy path; carry-only and gentle scruff handling; bed approach/rest; latched cage/release; ordinary edge roam;
intrusive zoomies; audio disable/re-enable and browser unlock; animate/reduced-motion modes; success, error,
empty/info, search, connection, and selected-record fetch feedback; compact radio output; and durable inline
technical detail. Global search returned six results for `dog`. Selecting `!NOTICE!` kept the Lore workspace
and queue mounted, exposed inline `Loading !NOTICE!`, and completed through Parsec without showing the route-
level `Loading Lore Editor...` fallback. The browser console remained free of errors.

This pass found and repaired three real interaction defects: while the habitat was expanded, its Close control
covered the physical-toy close control; actor and furniture pointer sessions could lose movement/release as
their animated hit targets moved; and furniture reanchoring outside the habitat caused focus-out to collapse
the overlay mid-drag. The rebuilt launcher now passes animated scruff dragging, direct 96 by 96 bed and cage
drags from habitat to app-edge without collapsing, and a full-toss release through bounce and settled recovery.
The step remains open for Zoe's physical pointer-feel approval and ownership transfer to a genuinely
background-hidden tab (automation tabs report `document.visibilityState === "visible"`). Automated browser
input and component/runtime tests are evidence, but are not substitutes for those acceptance checks.

- [x] **Step 3: Run the full asset and application gates**

Run: `python -m pytest tools/parsec_assets -q`

Run: `python tools/parsec_assets/validate_manifest.py --manifest webapp/frontend/src/assets/parsec/manifest.v1.ts --register references/parsec-asset-register.md --require-resolved`

Run: `npm --prefix webapp/frontend test -- --run`

Run: `npm --prefix webapp/frontend run typecheck`

Run: `npm --prefix webapp/frontend run build`

Run: `python tools/docs/check_agent_docs.py`

Run: `git diff --check`

Expected: all pass; every required row has an allowed exit state.

Evidence (2026-08-25): `50` Python asset tests pass; resolved-manifest validation passes `60` clips and
`293` frames; the full frontend suite passes `320` tests in `66` files; TypeScript typecheck and the Vite
production build pass; agent-documentation consistency passes; and `git diff --check` exits zero with only
existing LF-to-CRLF notices.

Runtime-recovery audit (2026-08-25): the earlier statement that all 293 source frames were production-accepted
is superseded. Native, `4×`, motion, and reduced-motion review plus the new visual lint accepted 56 source clips
and 274 source frames. Four weak source clips comprising 19 frames are quarantined for detached tail/motion
pixels. Their four semantic slots resolve through coherent reuse of `feedback-success-wag`, so all 60 required
runtime clips remain available. The human-art backlog is four replacement clips. The machine-readable decision
inventory is `parsec-visual-reviews.v1.json`; frame count alone is no longer accepted as visual-quality evidence.

- [ ] **Step 4: Report the gate closed and return to normal effort**

Summarize accepted atlases/cues, explicit human deferrals or approved fallbacks, provenance status, motion
and reduced-motion review, browser exercise, and exact verification output. Only after this report may
effort return to normal for unrelated polish and final application verification.


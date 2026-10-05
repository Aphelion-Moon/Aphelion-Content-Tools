# Parsec Asset Register

This is the canonical inventory and human-assistance backlog for Parsec artwork in Aphelion Content Tools.
Update it whenever an asset is added, replaced, derived, integrated, rejected, or relicensed.

## HD regeneration: 4 October 2026

The [current generation manifest](../webapp/frontend/src/assets/parsec/source/regeneration-20261004/manifest.json)
supersedes the September actor and effect artwork: all 60 states, 66 directional sequences, and 293 frames
now have dedicated art from one cute, furry-stylized character reference. Individual HD frames are 512×512;
pixel masters are 480×480. All sequences were converted through [PortalRabbit](https://portalrabbit.com)
Grid Artist with Ink sampling, 64 colors, and source colors preserved. Its original pixel grid is retained
at an exact 3× enlargement. Runtime frames remain 96×96, with rebuilt atlases, anchors, and compact fallback.

The scratch sequence replaces the grounded hind leg as it lifts. Every visible iris is checked after
runtime preparation. The manifest records the reference, prompts, source sheets, exact converter downloads,
individual frames, runtime inputs, and hashes. The four previous reuse states now use their own frames.
SS13 object art and audio retain their existing sources. Historical reviews and source decisions below
remain available; their old hashes and visual findings do not describe the current artwork. Automated and
agent visual checks do not constitute maintainer artistic acceptance.

Status values:

- `available` — shipped and referenced by the runtime.
- `candidate needed` — approved need with an existing fallback.
- `candidate review` — a best-effort candidate exists but is not approved for runtime use.
- `human help requested` — automated or maintainer attempts did not meet the current sprite quality.
- `superseded` — no longer used; obsolete binaries were removed in the September cleanup.

Source-inventory rows additionally use `candidate`, `accepted-source`, and `rejected-source`. An
`accepted-source` is legally and technically suitable for the later creative sprint; it is not permission to
copy it into runtime assets before the Max-effort production gate.

## Legacy fallback sprite sheet

| Field | Value |
| --- | --- |
| Asset ID | `parsec-legacy-sheet` |
| Status | `available` |
| Runtime file | [`webapp/frontend/src/assets/parsec.png`](../webapp/frontend/src/assets/parsec.png) |
| Dimensions | `432 × 204` pixels, transparent PNG |
| Cell contract | `72 × 51` pixels; 6 columns × 4 rows |
| Artwork | Derived from the current regenerated core and feedback frames; original character reference: [Husky Sprites](https://opengameart.org/content/husky-sprites) |
| License | Project-owned generated asset; historical reference CC0 |
| Local adaptation | Nearest-neighbor packing into the existing fallback cells, retaining visible iris colors |
| Runtime mapping | [`webapp/frontend/src/lib/parsecEngine.ts`](../webapp/frontend/src/lib/parsecEngine.ts) |

## Identity color contract

The maintainer corrected the eye orientation on 4 October 2026: Parsec's **anatomical left eye** is
yellow `#FBD436`; her **anatomical right eye** is neon pink `#FF3CC8`.
In a front-facing sprite, pink is on the viewer's left and yellow is on the viewer's right. A left-facing
profile shows pink; a right-facing profile shows yellow. Pink tongue pixels are separate from eye pixels.
This supersedes the September contract in preserved historical sources and preparation metadata.

The [pixel touchup record](../webapp/frontend/src/assets/parsec/source/touchups/2026-09-09/manifest.json)
records the historical actor frames, immutable sources, exact pixel edits, and eye locations. Required replay
sources live in `source/touchups/2026-09-09/originals`; selected scratch/yawn inputs live in
`source/compositions`. No historical backup tree is required for current replay or rebuilding.

## Image retention and review generation

The maintainer requested removal of all generated review files on 9 September 2026. The asset tree was
reduced from 3,662 to 701 PNG/GIF files; all stored GIF galleries, contact sheets, before/after exports,
rejected candidates, obsolete atlas bundles, and duplicate staging trees were removed. October regeneration
adds the current HD and pixel masters. The [retained-image inventory](../webapp/frontend/src/assets/parsec/source/retained-images.v1.json)
records a purpose and SHA-256 for every remaining image: current atlas/editable frames, original source
artwork, verified reference crops, and exact replay inputs.

The sections below preserve historical decisions and hashes. Links marked **artifact removed** identify
retired material; historical retention statements do not require restoring those files. Current retention
is defined by the inventory above. The [asset maintenance guide](../webapp/frontend/src/assets/parsec/README.md)
explains rebuilding and generating temporary reviews outside the source tree.

New imports no longer guess white face fill from a convex hull; open coat outlines need explicit repair.

## ImageGen reference crops

Retained source ImageGen outputs remain untouched under `source/generated`. They are not valid inputs for
later generation because the service-produced canvases contain large exterior white or checker fields. Historical
ImageGen work used the manually reviewed copies under `source/references`; each copy is a literal crop of
its registered source, retains a 16-pixel working margin around every detected artwork edge, and has a sibling
`*.trim.json` record containing the exact crop, source/output dimensions, and both hashes. The crop changes no
retained pixels. [`trim_reference_image.py`](../tools/parsec_assets/trim_reference_image.py) rejects crops that
cut occupied artwork or retain less than the declared margin.

| Reference input | Purpose | Crop `(left, top, right, bottom)` | Output dimensions | SHA-256 |
| --- | --- | --- | --- | --- |
| [`feedback-success-wag.reference.png`](../webapp/frontend/src/assets/parsec/source/references/feedback-success-wag.reference.png) | Default profile, standing proportions, and tail expression | `(61, 240, 1947, 560)` | `1886 × 320` | `55b54cd58e43b1e270ed02b27e14c2baf42e953931580f79db8d818a965c577c` |
| [`core-idle-seated.reference.png`](../webapp/frontend/src/assets/parsec/source/references/core-idle-seated.reference.png) | Seated, resting, bed, and timeout poses | `(72, 139, 2091, 555)` | `2019 × 416` | `a3724d11e4fe049accb72421d1e41601f752e4a01b43cab754f99ff7cb1b56d5` |
| [`core-walk-cardinal.reference.png`](../webapp/frontend/src/assets/parsec/source/references/core-walk-cardinal.reference.png) | Front, rear, and profile laterality/proportions | `(117, 50, 1132, 1182)` | `1015 × 1132` | `0bfdb38b343844a38699679cc719c3994d0e0de647c13c88a87a54b131835c14` |
| [`touch-scruff-calm.reference.png`](../webapp/frontend/src/assets/parsec/source/references/touch-scruff-calm.reference.png) | Self-contained scruff-lift anatomy without a visible hand or line | `(170, 211, 1807, 567)` | `1637 × 356` | `49520ff31043f5621e76d05c1487e842602dc56b237b6cead7024cf7f09e36db` |
| [`touch-release-toss.reference.png`](../webapp/frontend/src/assets/parsec/source/references/touch-release-toss.reference.png) | Airborne and landing anatomy | `(63, 167, 1977, 562)` | `1914 × 395` | `fce09dc9548b87b511eb0e4ab0b3feadc82730a3e77b934a660966bfa4f1439d` |
| [`toy-tug-grip.reference.png`](../webapp/frontend/src/assets/parsec/source/references/toy-tug-grip.reference.png) | Braced tug posture and planted-paw silhouette | `(22, 240, 2026, 530)` | `2004 × 290` | `d5aea794cfdd576b9793371628c3fb42e1f460fc1048ad24cc1338afa7d11508` |
| [`habitat-bed-approach.reference.png`](../webapp/frontend/src/assets/parsec/source/references/habitat-bed-approach.reference.png) | Right-facing approach posture and bed-side alignment | `(15, 166, 2129, 551)` | `2114 × 385` | `9f35ecdce6448adf278d037bb812475810b619824fec4a57fe808b69091cb99f` |
| [`habitat-cage-enter.reference.png`](../webapp/frontend/src/assets/parsec/source/references/habitat-cage-enter.reference.png) | Left-facing carrier entry and seated footprint | `(37, 240, 1897, 557)` | `1860 × 317` | `4b7a1328c78db678d151f2b48118dc35ca6fd35d5ffc6e570239949ce91af326` |

All eight trims were inspected at original resolution after generation on 2026-08-24. No ear, paw, tail,
motion accent, or eye pixel touches a crop edge.

## Parsec core Max production

The frozen `parsec-core` roster is accepted and active. Built-in OpenAI ImageGen produced the source strips
under project direction, using the legacy CC0 Parsec sheet, the identity-color contract above, and the exact
clip intent in [`parsec-animation-storyboards.md`](architecture/parsec-animation-storyboards.md) as visual
references. Generated outputs are project-owned generated assets; no third-party art was copied into these
strips beyond using the registered CC0 legacy sheet as a character reference.

### Accepted runtime artifacts

| Artifact | Dimensions / role | SHA-256 | Status |
| --- | --- | --- | --- |
| [`parsec-core.png`](../webapp/frontend/src/assets/parsec/parsec-core.png) | `768 × 768`; 59 frames on a `96 × 96` logical grid | `e94db4852bd18c1feb641003afc385b950ad6072530f7426bd9f97abad519ad3` | `available` |
| [`parsec-core.json`](../webapp/frontend/src/assets/parsec/parsec-core.json) | Exact atlas coordinates | `e0b3e09e75fe6d187b69a9474a445f02d9e86c039194aa6ab71558bbbb191488` | `available` |
| [`parsec-core.anchors.json`](../webapp/frontend/src/assets/parsec/parsec-core.anchors.json) | Per-frame feet, face, scruff, mouth, interaction, toy, effect, and shadow anchors | `ca29a65e6d860a7cd9bed9196c6f0d9d4f4f8458bd27013a93772b9ea92c0eb1` | `available` |

### Generated source register

All rows use built-in OpenAI ImageGen with the legacy sheet and identity contract as references. `Accepted
partial` means the retained source contributes only the named frames; unused frames remain available for
provenance but are not runtime art.

| Source | Prompt intent | SHA-256 | Review use |
| --- | --- | --- | --- |
| [`core-idle-seated.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/core-idle-seated.imagegen.png) | Four-frame seated breathing, blink, and small tail motion | `5d3bf03dc8fe1e5bb6a4c8e3633d7d534f22c36039cba6ee0872fae07ea7e879` | `accepted partial`; final frames 0, 1, and 3 |
| `core-idle-seated-tail-alternate.imagegen.png` (artifact removed) | Replacement seated tail motion with the tail attached to the body | `5f46a0fc008cd57b4c2ca93c8c7de63ec06ea7fb392754b3a3a66f2c306af692` | `accepted partial`; supplies final frame 2 |
| `core-idle-seated-repair-v2.imagegen.png` (artifact removed) | Cleaned seated strip constrained to the older flat production style | `4b2b96b528cbe97afbc6a76ce1b12e9d641d77c1a2be9f47ff945f9fce76415c` | `rejected-source`; coherent but does not meet the newer organic quality target |
| `core-idle-seated-repair-v3.imagegen.png` (artifact removed) | Four-frame organic seated idle using the stronger intrusive-mode anatomy and expression references | `87d9431653aa5380f7bd95fc59f51c4affbb8b56b0be06d81980c9bbeab1d9e1` | `accepted-source`; production uses the v4 deterministic dark-outline preparation of all four frames |
| [`core-idle-standing.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/core-idle-standing.imagegen.png) | Four-frame alert standing rest | `89fdf38bff23bef907ad3934b5f9232a2e9017fd4b0af7c705d4781de58f7707` | `accepted` |
| `core-idle-sniff.imagegen.png` (artifact removed) | Four-frame curious idle sniff | `d051b52a9bbe15d36bfb0c3512886a9e26d8e728805f0c1a6e809b9a26fc4f5a` | `accepted` |
| `core-idle-scratch.imagegen.png` (artifact removed) | Five-frame seated scratch with stable anatomy | `2d8accd0d095149a0c6a8c506dca8301e449ce80702da08587ae2cb6129c0022` | `accepted` |
| [`core-idle-scratch-repair-v2.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/core-idle-scratch-repair-v2.imagegen.png) | Organic five-frame scratch with stable seated anatomy and consistent profile eye | `b7a127204822a016d2b1d3d98fb9abe5b5191aa8c17c4f42981c45553678c683` | `accepted-source`; replaces all five production scratch frames |
| `core-idle-yawn.imagegen.png` (artifact removed) | Five-frame sleepy yawn | `ec27e137a334399135e41844c78636ae2fee9989043241a39b7a7d2e418c200b` | `accepted` |
| [`core-idle-yawn-repair-v2.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/core-idle-yawn-repair-v2.imagegen.png) | Organic five-frame yawn with coherent mouth motion and consistent profile eye | `255b20f4d804d8ed2fba827dfee57c3c58703858c2f32c8065daddcae91e16bb` | `accepted-source`; replaces all five production yawn frames |
| [`core-idle-pant.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/core-idle-pant.imagegen.png) | Four-frame comfortable seated pant | `c55658e165533723360d2d8d6967540303964ce3dc4f189d3814ced095351381` | `accepted` |
| `core-look-cursor.imagegen.png` (artifact removed) | Four-frame seated cursor-tracking head turn | `e8ff7e092e342d2308dbb1c5ca55cb056c88b49da7e75b2167f7fb7c5b7da362` | `accepted partial`; final frames 0, 2, and 3 |
| `core-look-cursor-eye-fix.imagegen.png` (artifact removed) | Edit restricted to the incorrect visible eye in cursor-look frame 1 | `4ebc043d022afd32623e2aced977124308cf2a0358fe9075c81ad9eae87396c1` | `accepted partial`; supplies final frame 1 |
| [`core-walk-cardinal.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/core-walk-cardinal.imagegen.png) | North, east, south, and west three-frame walk cycles | `5f2b15f133b2487b893103c24bf4c4c0d8033e20b45ced7929090a5a4087a1cc` | `accepted` after directional composition |
| `core-walk-diagonal.imagegen.png` (artifact removed) | Four diagonal three-frame walk cycles | `05fa3b6c5ade8d9ac34fecbf3d9e8227f664fff7525f225e5bdd9e6ee2682c95` | `accepted` after eye-laterality correction in two directions |
| [`core-return-home.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/core-return-home.imagegen.png) | Five-frame return-to-rest transition | `cc2028f39aedfb3f0ee387c36c8f183f8df72d5075c4733425220bbf6b560dfe` | `accepted` |

### Adaptation and review record

- The 2026-08-26 manual repair audit invalidated the earlier visual acceptance of `core-idle-seated`: enlarged
  review exposed malformed face pixels, inconsistent eyes, and a style-quality gap that automated lint did not
  detect. The original production clip and obsolete atlas backups were removed during the September cleanup.
- `core-idle-seated-repair-v4` was isolated from the v3 generated checker field, normalized, given a deterministic
  one-pixel dark silhouette boundary, and packed onto four
  `96 × 96` cells, then reviewed at native size, `4×` nearest-neighbor scale, authored timing, and reduced motion.
  Visual lint returned no border, component, baseline, or occupied-height errors. The per-clip review entry is
  `review/generated-candidates/core-idle-seated-repair-v4` (artifact removed).
- `core-idle-scratch-repair-v2` replaces the chopped-eye and abrupt-face sequence with one consistent organic
  seated scratch cycle. It passed native and `4×` inspection plus authored-timing and reduced-motion review under
  `review/generated-candidates/core-idle-scratch-repair-v2` (artifact removed).
- `core-idle-yawn-repair-v2` replaces the inconsistent black eye-lines and shifting face with a coherent organic
  opening, full-yawn, closing, and recovery sequence. It passed native and `4×` inspection plus authored-timing
  and reduced-motion review under
  `review/generated-candidates/core-idle-yawn-repair-v2` (artifact removed).
- Generated checkerboard and near-neutral backgrounds were isolated with
  [`postprocess_generated_strip.py`](../tools/parsec_assets/postprocess_generated_strip.py). The deterministic
  pass uses a neutral threshold of 220, retains the largest eight-connected subject component unless a clip
  explicitly permits auxiliary effect components, applies one clip-wide scale, resizes nearest-neighbor,
  normalizes to the identity palette, quantizes to 24 colors, enforces a one-pixel dark subject boundary while
  preserving registered identity/effect colors, and packs onto `96 × 96` cells.
- Direct pixel correction is limited to small identity/continuity defects. Scripted eye recoloring corrected
  diagonal south-east/south-west laterality; east/west cardinal rows were mirrored and then normalized to the
  correct profile eye. No anatomy was repaired with direct fill. The rejected anatomy candidates remain rejected.
- Seated and cursor-look clips use explicit frame-selection manifests. Every production composition now points
  only to durable project-local sources; `test_production_provenance.py` enforces that rule.
- Native `1×`, enlarged nearest-neighbor `4×`, exact authored timing, and reduced-motion representatives were
  reviewed. Locomotion was additionally reviewed as eight independent three-frame direction variants so runtime
  playback cannot spin through a 12-frame direction sheet.
- Review entry point: `review/motion/index.html` (artifact removed).
  Native contact sheets are under `review/parsec-core` (artifact removed).
  All core rows were accepted in browser review on 2026-08-24.
- Runtime mapping and timing are authoritative in
  [`manifest.v1.ts`](../webapp/frontend/src/assets/parsec/manifest.v1.ts). Direction defaults are east for
  cardinal motion and south-east for diagonal motion; callers may select any named variant.

## Parsec feedback Max production

The frozen `parsec-feedback` roster is accepted and active. Generation method, ownership, character reference,
identity contract, and post-processing rules are the same as the core atlas.

### Accepted runtime artifacts

| Artifact | Dimensions / role | SHA-256 | Status |
| --- | --- | --- | --- |
| [`parsec-feedback.png`](../webapp/frontend/src/assets/parsec/parsec-feedback.png) | `672 × 672`; 46 frames on a `96 × 96` logical grid | `267c60d4b24a3598ec6e859f565dacf242577fdf5f6e726e7ed45584da83ecd1` | `available` |
| [`parsec-feedback.json`](../webapp/frontend/src/assets/parsec/parsec-feedback.json) | Exact atlas coordinates | `730059360bd84a20adc44450018a89d63e1c79aec01e42c0fa87c1b38218e8f7` | `available` |
| [`parsec-feedback.anchors.json`](../webapp/frontend/src/assets/parsec/parsec-feedback.anchors.json) | Per-frame semantic anchors with detached effects excluded from body bounds | `1f1db004fa7c220865b8c89a111e923cc4a0735b7cce4e7b62e2c354555e1488` | `available` |

### Generated source register

| Source | Prompt intent | SHA-256 | Review use |
| --- | --- | --- | --- |
| [`search-sniff.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/search-sniff.imagegen.png) | Five-frame nose-down search with restrained scent accents | `c46b99dd1aef5ae9e559dd7e930f7c0c22412c7ae7c6e1303041fd0193fdb0f5` | `accepted`; scent accents retained as auxiliary components |
| [`fetch-dig.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/fetch-dig.imagegen.png) | Six-frame forepaw digging/snuffling fetch | `4e39f845dc73a44236e7d632c29887a42743da5fa42b16f831c04e6e799f58c3` | `accepted` |
| [`feedback-working-focus.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/feedback-working-focus.imagegen.png) | Four-frame calm, attentive work duty | `1f6cbac4be5d842bf945c390dc7d2e464cc08831c4f78a8d2b5c8c20cb8a199a` | `accepted` |
| [`feedback-success-wag.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/feedback-success-wag.imagegen.png) | Five-frame excited but brief success wag | `f1b4010d2c9e57ff73f9b2c0dc1473b6a17d12c7c70055cd4e8c8cc21082c4b5` | `accepted` |
| `feedback-success-proud.imagegen.png` (artifact removed) | Four-frame quiet proud completion pose | `67907450ce94ea3f13ee1fe58dc80b52e240b6277e56afe7f8679c46e7bee52c` | `accepted` |
| `feedback-warning-alert.imagegen.png` (artifact removed) | Four-frame serious ears-up alert with station-warning accent | `ca0b7a748995fb04aadd68388459b890a8354d037b18bb9c89ad849e23b5b547` | `accepted`; warning accent retained as an auxiliary component |
| `error-anxious.imagegen.png` (artifact removed) | Five-frame ears-back anxious response without comic exaggeration | `c747032766e20fea51d8834b7271eef0e14cb035a8873dda7310ddd98529f983` | `accepted partial`; final frames 1–4 |
| [`error-anxious-eye-fix.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/error-anxious-eye-fix.imagegen.png) | Edit restricted to reconnecting the malformed pink eye in anxious frame 0 | `4f2386adbb9ff317850bb7f97a5bf8907b72f7197a04a70e0fbfc617af5b0e48` | `accepted partial`; supplies final frame 0 |
| [`empty-confused.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/empty-confused.imagegen.png) | Four-frame seated head tilt | `745504a3e50f9563a03edba260edded96f177d44b15ea9844c3a107c9b325a3a` | `accepted`; frames 1–2 received localized eye-laterality recoloring |
| [`tool-growl.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/tool-growl.imagegen.png) | Five-frame mild playful frustration at failed tooling | `149edcca7cff3cb91c74aeafcba2b3a78a9cc08c4f4e34f4683e006cce3e6a44` | `accepted` after one-pixel detached residue removal |
| `reconnect-pant.imagegen.png` (artifact removed) | Four-frame recovered-connection pant | `c54e44805f1a2dbbc6d4a84364b016db9c085a1532a25f1e0b689277dcf1a0e5` | `accepted` after dark checkerboard residue isolation |

### Adaptation and review record

- Search scent marks and the warning triangle are the only intentional detached feedback components. Anchor
  derivation isolates the largest connected body before computing body anchors, then records effect anchors
  separately.
- The anxious final clip composes corrected frame 0 with original frames 1–4. Confused frames 1–2 received
  localized deterministic direct recoloring so front-facing yellow remains viewer-left and pink remains
  viewer-right. Tool-growl and reconnect-pant were reprocessed after the neutral-background detector was fixed;
  superseded residue-bearing frames were removed during the September cleanup.
- Native `1×`, enlarged nearest-neighbor `4×`, exact authored motion, and reduced-motion representatives were
  accepted in browser review on 2026-08-24. Contact sheets are under
  `review/parsec-feedback` (artifact removed), and the shared motion
  dashboard is `review/motion/index.html` (artifact removed).
- Runtime aliases route search, fetch, anxious, confused, growl, and pant feedback directly to these accepted
  clips. Warning duty always selects `feedback-warning-alert`; ordinary working and success duties preserve the
  specific animation supplied by the feedback coordinator.

## Parsec touch Max production

The frozen `parsec-touch` roster is accepted and active. Built-in OpenAI ImageGen produced the source strips
under project direction. The retained raw outputs stay untouched; later generations use only the reviewed
manual crops registered in [ImageGen reference crops](#imagegen-reference-crops).

### Accepted runtime artifacts

| Artifact | Dimensions / role | SHA-256 | Status |
| --- | --- | --- | --- |
| [`parsec-touch.png`](../webapp/frontend/src/assets/parsec/parsec-touch.png) | `672 × 672`; 48 frames on a `96 × 96` logical grid | `9a2550706f8ecf4c0d477716708d6cefa9e692bfe4508db6985a09eeba48ba67` | `available` |
| [`parsec-touch.json`](../webapp/frontend/src/assets/parsec/parsec-touch.json) | Exact atlas coordinates | `699d98f92cf5361603f1c43b21b1b286a449c349dcd939584e15bccedae33f1f` | `available` |
| [`parsec-touch.anchors.json`](../webapp/frontend/src/assets/parsec/parsec-touch.anchors.json) | Per-frame semantic anchors, including scruff and contact points | `8d38ec77721bb433e70cf8efba2f7a20fea210eb0be849f1b39589abf2511115` | `available` |

### Generated source register

| Source | Prompt intent | SHA-256 | Review use |
| --- | --- | --- | --- |
| [`touch-pat-soft.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/touch-pat-soft.imagegen.png) | Four-frame warm ordinary pat response | `daa28ce3925f1d7e0c1ab194c58326010e222d8690d8c10087086b498aeba0b9` | `accepted` |
| [`touch-pat-delighted.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/touch-pat-delighted.imagegen.png) | Five-frame familiar, tail-forward delight | `1723e82b235fb9b4bc58c1bf0ec54a022e8fdd6204d1bc3afc4c0e96c0a79988` | `accepted`; restrained tail accents retained |
| `touch-nose-lick.imagegen.png` (artifact removed) | Five-frame playful, nonsexual nose lick | `04bf134d75db07a35a0f38e8205146e3113493415b587e631ccc5edaa00db051` | `accepted` |
| [`touch-scruff-calm.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/touch-scruff-calm.imagegen.png) | Four-frame relaxed scruff lift with no visible holder | `7125b9814c76db050930b2231f11f5ee0105f75d0dfd205dce9ed60440ce1715` | `accepted` |
| [`touch-scruff-playful.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/touch-scruff-playful.imagegen.png) | Five-frame amused, self-contained scruff squirm | `c8862725b0858c5697533c3f3562b6c1e2f23ea062591ca8edc4305a7a589061` | `accepted` replacement |
| `touch-scruff-pout.imagegen.png` (artifact removed) | Five-frame huffy scruff pout without distress read | `6cd7f993cb466bcf51d7bd8db925012ea284b10bc116e89421125105f9491de1` | `accepted` replacement |
| [`touch-release-drop.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/touch-release-drop.imagegen.png) | Four-frame controlled low-speed release | `735b46f75e113d26c1cb61adb0a9c03e88012f66e42a14c7a105d5aa0a97690e` | `accepted partial`; frames 1–3 only |
| [`touch-release-toss.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/touch-release-toss.imagegen.png) | Six-frame playful airborne release arc | `7a8272bb28fa21d52d34d82cffe04aadb079ff612b00a518f8b7e9ecce29e2bd` | `accepted` |
| `touch-landing-bounce.imagegen.png` (artifact removed) | Six-frame squash, one bounce, and grounded recovery | `d80485192253fb4d4f9ab1084c80fd0dd64b82e41fc2d8e7185da0ae53afe076` | `accepted`; small detached dust retained |
| [`touch-landing-recover.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/touch-landing-recover.imagegen.png) | Four-frame shake-off and reorientation | `72bf8097c6578854875d1bd4cad4be799624b21ef79c4eadf6f0105009d13e4d` | `accepted`; detached shake residue removed |

### Rejection, adaptation, and review record

- `touch-scruff-playful-visible-lines-v1.imagegen.png` (artifact removed)
  (`3d4622dc0c12abfe0027e6b897ce3e4bfac0583e98750d85c3710b7c27e97c54`) and
  `touch-scruff-pout-visible-handle-v1.imagegen.png` (artifact removed)
  (`74d643935bf31601628d0c6b7739f8bccb8fb49b5d235b9ecbef7c08773f7a3b`) were rejected because they drew
  suspension lines or a holder. Replacement generation made the raised scruff fold self-contained.
- Release-drop source frame 0 showed an invalid visible grip. The final clip composes accepted
  `touch-scruff-calm` frame 0 with release-drop frames 1–3; the durable composition record is
  [`touch-release-drop.composition.json`](../webapp/frontend/src/assets/parsec/prepared/parsec-touch/touch-release-drop/touch-release-drop.composition.json).
  No repaint was used. Required composition inputs now live under `source/compositions`; other candidates were removed.
- Generated backgrounds were isolated, each clip received one clip-wide nearest-neighbor scale, the palette was
  quantized without dithering, and identity colors were normalized. The default largest-component rule removed
  the landing-recover residue; landing-bounce deliberately retained its small dust components.
- Native `1×`, enlarged nearest-neighbor `4×`, exact authored motion, and reduced-motion representatives were
  accepted in browser review on 2026-08-24. Contact sheets are under
  `review/parsec-touch` (artifact removed), and the shared motion dashboard
  is `review/motion/index.html` (artifact removed).
- Runtime mapping selects soft or delighted pat by familiarity, calm/playful/pout scruff clips from the configured
  personality and handling reaction, and drop versus toss from the configured handling physics and release speed.
  Release clips sequence through the accepted landing recovery without resetting a newer reaction from a stale
  clip-completion event.

## Parsec toys Max production

The frozen `parsec-toys` roster is accepted and active. Built-in OpenAI ImageGen produced Parsec-only motion;
the actor frames deliberately contain no ball, rope, brush, treat, whistle, hand, or cursor pixels. Real SS13
objects attach separately through the atlas's per-frame `toy` and `interaction` anchors.

### Accepted runtime artifacts

| Artifact | Dimensions / role | SHA-256 | Status |
| --- | --- | --- | --- |
| [`parsec-toys.png`](../webapp/frontend/src/assets/parsec/parsec-toys.png) | `768 × 768`; 59 frames on a `96 × 96` logical grid | `8682d8b8e3c204f69b32d3e1badefb76762b7ae72d91d9c050ed74fdd753179a` | `available` |
| [`parsec-toys.json`](../webapp/frontend/src/assets/parsec/parsec-toys.json) | Exact atlas coordinates | `32cf5412a674e0bc2213a65f0de26c00fa4265c9f1b7417e3bd9336ec28efe75` | `available` |
| [`parsec-toys.anchors.json`](../webapp/frontend/src/assets/parsec/parsec-toys.anchors.json) | Per-frame feet, face, mouth, toy, interaction, effect, scruff, and shadow anchors | `a5298bf06e7828d9c6136d8af023a535c501332f464a104bb3d371b77ca657e5` | `available` |

### Generated source register

| Source | Prompt intent | SHA-256 | Review use |
| --- | --- | --- | --- |
| `toy-ball-ready.imagegen.png` (artifact removed) | Four-frame anticipatory ball-ready hold | `4d903c4f1fae189075e5de623089178dc40e8e0ce92a61f0b72dd4f1b6ef001c` | `accepted` |
| [`toy-ball-chase.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/toy-ball-chase.imagegen.png) | Six-frame low, eager chase | `ffa711ed4a28093c28b37f979839a6d3242723c3678f73e942890d496f07dbbd` | `accepted` |
| [`toy-ball-retrieve.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/toy-ball-retrieve.imagegen.png) | Six-frame return carrying an anchor-attached ball | `f6fdd9153b97e180840190a2f95ecb948ea9996af7fa3ccc73f08fb9f2e58725` | `accepted` after localized edge-residue removal in frames 2–4 |
| `toy-ball-refuse.imagegen.png` (artifact removed) | Four-frame impish refusal | `33dbf78215efcd7a69be07f0ac211886b74b0c54f2f70f4a702bae612c0eb24d` | `accepted` |
| [`toy-tug-grip.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/toy-tug-grip.imagegen.png) | Four-frame planted tug grip | `277690161562c498e37ad88e79ded0d6b6083b4fb145ec992bd1742505957b3e` | `accepted` |
| [`toy-tug-pull.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/toy-tug-pull.imagegen.png) | Six-frame braced pulling loop | `45c63179c44cd35bee17208074288af0eec46ce2817015be9780d2b9da3765e1` | `accepted` replacement |
| [`toy-tug-win.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/toy-tug-win.imagegen.png) | Five-frame proud tug victory | `139ff34b2991bc2c8f3d03e1eb66d92b6187be84a2352e7dc05d4eab7007b53b` | `accepted` after localized edge-residue removal in frame 2 |
| [`toy-tug-tumble.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/toy-tug-tumble.imagegen.png) | Five-frame dramatic tug tumble | `77cc2357cb98b4019deb85d0ec2fbc324566de544f58e56c0a2cb29f91dc3315` | `accepted partial`; frames 0–3 |
| [`toy-brush-content.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/toy-brush-content.imagegen.png) | Five-frame content brushing loop | `b5a127a4f44eeb3ecdd8f7faa88203cba24149da164d4dac8a62153bcda74cfe` | `accepted` |
| [`toy-brush-impatient.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/toy-brush-impatient.imagegen.png) | Four-frame impish brushing impatience | `c7ce61e3d4796d733779b48d55122376c0e060d0258fe4ccb6dc322ff63de517` | `accepted`; detached emphasis residue removed |
| `toy-treat-accept.imagegen.png` (artifact removed) | Five-frame gentle treat acceptance | `ede9610471f4259bd6c7806ad66ca7a6dc588bf605d64898e5a7df348df06915` | `accepted`; detached wag residue removed |
| `toy-whistle-recall.imagegen.png` (artifact removed) | Five-frame alert recall and return | `09e1fdfd0c2cc4ac12ac8becf71662c0c14cb5f3f9b88bc025bfb0de4c23ad93` | `accepted` |

### Rejection, adaptation, and review record

- The first ball-retrieve source drew a generic ball into the actor strip and was rejected. The first tug-grip
  source had no planted grip or tension. Two tug-pull attempts read as walk and run cycles instead of a stationary
  pull. The four rejected binaries were removed; their historical filenames were:
  `toy-ball-retrieve-drawn-object-v1` (`277f34764e538c78afdd1367de7b0618d1db9b42c750ae380cd97f3ab7991bfc`),
  `toy-tug-grip-unbraced-v1` (`31670fd510f598235e46d764766f7413a416c4b681c861e359a932602e5e2484`),
  `toy-tug-pull-walk-cycle-v1` (`9d07e65dbbecb6436f748248d4ac7d35718050baf05dc87766be0e59a1f50ef3`),
  and `toy-tug-pull-run-v2` (`faf7dd8aa815556bc97aaabe184c7537b511630584efb8cbc85e1a01fa846d45`).
- ImageGen's transparent-canvas noise prevented silhouette-based strip detection in retrieve, tug-pull, tug-win,
  brush-impatient, and treat-accept. The recorded equal-panel split isolates each known authored panel before the
  ordinary foreground, scale, palette, and identity passes; its regression test covers the failure mode.
- Ball-retrieve frames 2–4 and tug-win frame 2 had tiny detached pixels along the far canvas edge. The approved
  localized alpha erase removed only the recorded rectangles. Intermediate frames, review output, and the first atlas were removed after integration.
- The generated tumble's final frame had invalid bipedal anatomy. The final clip composes generated frames 0–3
  with the accepted seated recovery frame from `touch-landing-recover`; the durable selection is
  [`toy-tug-tumble.composition.json`](../webapp/frontend/src/assets/parsec/prepared/parsec-toys/toy-tug-tumble/toy-tug-tumble.composition.json).
- Native `1×`, enlarged nearest-neighbor `4×`, exact authored motion, and reduced-motion representatives were
  accepted in browser review on 2026-08-24. Contact sheets are under
  `review/parsec-toys` (artifact removed), and the shared motion dashboard is
  `review/motion/index.html` (artifact removed).
- Runtime mapping uses ready, chase, and retrieve for ordinary ball play; a new impish personality may refuse.
  Tug uses grip and pull, then selects victory or a dramatic tumble from handling settings. Brush uses content or
  impatient personality motion, treat uses accept, and both whistle entry points use the accepted recall clip.

## Parsec habitat Max production

The frozen `parsec-habitat` roster is accepted and active. It contains actor-only bed and carrier transitions;
no generated frame includes furniture, bars, latches, bedding, props, hands, cursors, or effect glyphs. The real
SS13 dog bed and pet-carrier states remain separately rendered objects.

### Accepted runtime artifacts

| Artifact | Dimensions / role | SHA-256 | Status |
| --- | --- | --- | --- |
| [`parsec-habitat.png`](../webapp/frontend/src/assets/parsec/parsec-habitat.png) | `672 × 576`; 37 frames on a `96 × 96` logical grid | `54735ca3102dc55da782b24b98e01cce262c3ba041fc0f8d443fa277e025c116` | `available` |
| [`parsec-habitat.json`](../webapp/frontend/src/assets/parsec/parsec-habitat.json) | Exact atlas coordinates | `857bf0ba97bf7b0af0c712ef77d3f794b77d4ac7df582eb45a61b287bb42572e` | `available` |
| [`parsec-habitat.anchors.json`](../webapp/frontend/src/assets/parsec/parsec-habitat.anchors.json) | Per-frame semantic anchors for actor/furniture alignment | `b5dc3d3109592ea9f0d05a42b3624ec4969cef781d60b5151fdb8cf6b69b1d1a` | `available` |

### Generated source register

| Source | Prompt intent | SHA-256 | Review use |
| --- | --- | --- | --- |
| [`habitat-bed-approach.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/habitat-bed-approach.imagegen.png) | Four-frame intentional approach to an invisible bed anchor | `5da338190cd153daa30ac096a0b6878c5edb553243e988524b321ee14b198f77` | `accepted`; supplies the registered tight bed reference |
| [`habitat-bed-lie-down.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/habitat-bed-lie-down.imagegen.png) | Five-frame natural standing-to-lying transition | `a4dec1d2227b829422fc9f514b5efb0ce68207dee1191d0f45d75f6c49f3b83b` | `accepted` |
| [`habitat-bed-sleep.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/habitat-bed-sleep.imagegen.png) | Five-frame breathing, blink, and ear-twitch sleep loop | `1e1a2f1bd74d286c4854cc2ba76e2af31a3b3d7bc1b9305591a99ed0afb59a6d` | `accepted`; closed-eye frame intentionally contains no eye color |
| [`habitat-bed-timeout-pout.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/habitat-bed-timeout-pout.imagegen.png) | Four-frame playful timeout huff and pout | `ecefb81a83b8dc3d9544d9b0c6b64fb4d37059621724571887e2670d0a5a6f02` | `accepted` |
| [`habitat-cage-enter.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/habitat-cage-enter.imagegen.png) | Five-frame approach, lower, and seated entry into an invisible carrier footprint | `71ab58c6f108101e55a004cf045c95c1d1f81491f50dd51d289152277a2a235a` | `accepted`; supplies the registered tight cage reference |
| `habitat-cage-open-idle.imagegen.png` (artifact removed) | Four-frame calm, aware open-carrier idle | `b55c806c11a38b647a610c56dfc0f06ac5c33abc41d7c86d02853db982ca88dd` | `accepted` |
| [`habitat-cage-latched-pout.imagegen.png`](../webapp/frontend/src/assets/parsec/source/generated/habitat-cage-latched-pout.imagegen.png) | Five-frame latched-carrier huff and pout without escape behavior | `5baa7835b77541c9a439864193fee3359d3cd490cb576071810428b84861b243` | `accepted` |
| `habitat-cage-release.imagegen.png` (artifact removed) | Five-frame seated rise and relieved exit | `c112d1a883be7181b8c7f50af7818c971639871c1eaa00dc22c85c5dea7b70b1` | `accepted` |

### Adaptation and review record

- Bed motion uses a right-facing profile with only the anatomical-left pink eye; carrier motion uses a
  left-facing profile with only the anatomical-right yellow eye. Exact-color inspection passed all visible-eye
  frames. The sleep blink closes the eye rather than inventing a second color.
- The bed-approach and cage-enter outputs were cropped manually to 16 pixels beyond every occupied edge before
  they became generation references. The lie-down source touched its raw canvas bottom and was therefore never
  admitted as a trim-controlled reference; sleep and timeout generation instead used its transparent prepared
  `96 × 96` frames, which contain no exterior white field.
- All eight sources used recorded equal-panel isolation, one clip-wide scale, nearest-neighbor reduction, palette
  normalization, and one connected actor component per prepared frame. Final clip compositions point only to
  durable project-local prepared sources.
- Native `1×`, enlarged nearest-neighbor `4×`, exact authored motion, and reduced-motion representatives were
  accepted in browser review on 2026-08-24. Contact sheets are under
  `review/parsec-habitat` (artifact removed), and the shared dashboard is
  `review/motion/index.html` (artifact removed).
- Bed commands sequence approach, lie-down, then voluntary sleep or timeout pout. Cage commands sequence entry
  into open idle, latch to a pout that never self-releases, and explicit release through the accepted exit clip.

## SS13 object production

The frozen 11-object roster is accepted and active. Each object comes from Meridian-Rift revision
`df0fb67eae69497be39e1dfc7f618f3d7964d3d5`. Preparation crops transparent DMI padding, applies an explicit
`3×` nearest-neighbor scale, and places the occupied bottom at baseline `y=90` on a transparent `96 × 96` cell.
The locked carrier composites the DMI's lock overlay onto the closed-carrier base before that shared transform.
The atlas remains separate from Parsec's actor sheets so furniture and toys can move independently.

| Artifact | Dimensions / role | SHA-256 | Status |
| --- | --- | --- | --- |
| [`ss13-objects.png`](../webapp/frontend/src/assets/parsec/ss13-objects.png) | `384 × 288`; 11 scaled SS13 objects on a `96 × 96` logical grid | `762cca715e1e084da9c0ad027e94fc44d32e3bec937514015971523e59820aac` | `accepted` |
| [`ss13-objects.json`](../webapp/frontend/src/assets/parsec/ss13-objects.json) | Exact atlas coordinates | `8be601b054c89b7bdbbb9cbb441a7337035331a815f989291babdf0817ff5c66` | `available` |
| [`ss13-objects.sources.json`](../webapp/frontend/src/assets/parsec/ss13-objects.sources.json) | Per-object DMI revision, state, crop, scale, baseline, source, extracted-frame, composition, and prepared-frame hashes | `9c64f336aee1e99bb00ea3e415ce13783c308c9913d420359b1e013ca8e400a8` | `accepted` |
| `review/ss13-objects/index.html` (artifact removed) | Native and `4×` nearest-neighbor contact review for all 11 objects | generated from accepted prepared frames | `accepted` |

- The dog bed and carrier states replace the temporary text furniture art. Open, latched, and occupied cage
  states select the matching runtime frame while retaining accessible move controls.
- The greyscale carp plush is the DMI's authored `map_plushie_carp` state and was accepted after native atlas
  review. The red toolbox is accepted as a station-flavored interaction prop.
- The tug toy uses the DMI's uncolored `coil` base from `icons/obj/stack_objects.dmi`. Dream Maker normally tints
  cable coils; the exact neutral loop reads cleanly as an improvised station tug without inventing new art.
- Extracted and prepared intermediates are namespaced under `source/ss13-objects` and `prepared/ss13-objects`.
  Earlier no-tug, flat-preparation, and alpha-premultiplied builds were removed after source selection.
- A regression test found that masked Pillow paste premultiplied partially transparent pixels. Production uses
  alpha compositing over a transparent canvas, then nearest-neighbor integer scaling so source colors remain exact.
- Recovery review accepted the dog bed and all four cage states at native and `4×` scale. Visual lint reports no
  border residue, detached components, baseline jitter, or occupied-height discontinuity for that furniture family.

## Parsec intrusive Max production

The five intrusive clips are accepted and active as a separate pointer-inert actor atlas. Generation used only
manually trimmed or already transparent project-local `96 × 96` references. No cursor image, work control, or
opaque background is present in the accepted frames.

| Artifact | Dimensions / role | SHA-256 | Status |
| --- | --- | --- | --- |
| [`parsec-intrusive.png`](../webapp/frontend/src/assets/parsec/parsec-intrusive.png) | `576 × 480`; 27 actor frames | `c3928ed0028bddd58429f7ec3d666a4988b15d527ea19ab071bb96a8bdfd0642` | `available` |
| [`parsec-intrusive.json`](../webapp/frontend/src/assets/parsec/parsec-intrusive.json) | Exact atlas coordinates | `ba5024257fbd4d41032888a3dbf6bd3897f3dc28a98a75c81d341a15d8ee1f4a` | `available` |
| [`parsec-intrusive.anchors.json`](../webapp/frontend/src/assets/parsec/parsec-intrusive.anchors.json) | Per-frame semantic anchors | `27a514aaa4e744dc496a64b44961e5536455c9c6dc375731448f42a60fcb3d92` | `available` |

- Cursor stalk, cursor pounce, loiter, demand-attention, and zoomies passed native `1×`, nearest-neighbor `4×`,
  authored-motion, and reduced-motion review under `review/parsec-intrusive`.
- Zoomies frames 0, 1, 3, 4, 5, and 6 had an exact neon-pink nose pixel cluster replaced with black only inside
  six recorded rectangles. Frame 2 required no repair; all original candidates remain available.
- The autonomous scheduler is connected to runtime selection. Intrusive presence maps its five existing behavior
  families to all five accepted clips; ordinary presence retains restrained core/feedback clips.

## Parsec effects production

The five effect clips are accepted as a separate pointer-inert overlay atlas. Effects never receive pointer events
and reduced motion selects the frozen representative frame instead of running the animation.

| Artifact | Dimensions / role | SHA-256 | Status |
| --- | --- | --- | --- |
| [`parsec-effects.png`](../webapp/frontend/src/assets/parsec/parsec-effects.png) | `480 × 384`; 17 effect frames | `ecb2aee466b2f5c573fb7d9b30b1352aba9a94318fec58614e5848f8318365d7` | `available` |
| [`parsec-effects.json`](../webapp/frontend/src/assets/parsec/parsec-effects.json) | Exact atlas coordinates | `45158202d1bf049590d1f53efa47b3a7b7de4ecb6d258153855228b83dfa27a8` | `available` |
| [`parsec-effects.anchors.json`](../webapp/frontend/src/assets/parsec/parsec-effects.anchors.json) | Per-frame overlay anchors | `a5e50a0a32611c0876d41e29902dab73700c509c4063843d28cfb58b6935c3a0` | `available` |

- Hearts use exact frames 0, 3, and 7 from `icons/mob/simple/animal.dmi:heart`.
- Station alert uses both exact `icons/mob/telegraphing/telegraph.dmi:exclamation` frames plus one deterministic
  35% alpha fade derived from the second frame.
- Radio ping uses visible frames 1, 3, and 6 from `icons/effects/effects.dmi:sonar_ping`; the authentic blank frame
  0 was rejected by the nonblank-frame gate.
- Scent isolates only exact `(80, 220, 235, 255)` accent pixels from accepted `search-sniff` frames 0–3.
- Landing dust isolates only detached auxiliary components from accepted `touch-landing-bounce` frames 0–3.
  `icons/mob/dust_animation.dmi:dust.1` through `dust.4` were rejected because they are opaque game-side filter
  masks rather than standalone visible dust art.
- All five families passed native `1×`, nearest-neighbor `4×`, authored-motion, and reduced-motion review under
  `review/parsec-effects`.

## Parsec audio production

All eight frozen audio slots are accepted and active. Runtime OGG files are byte-exact copies of their registered
Meridian-Rift sources: no silence trim, gain, layering, or transcoding was required. The source pack is reproducible
through `tools/parsec_assets/build_audio_pack.py` and its overwrite/fidelity regression tests.

| Cue | Source register ID | Runtime channel | Authored volume | Cooldown ms | Output SHA-256 |
| --- | --- | --- | ---: | ---: | --- |
| `voice-bark` | `audio-bark-1` | voice | 0.75 | 2,000 | `ca9e2a5e7b0b5cb168b2abbed19cac2ba603c623166b6fd977e5c2330081da4b` |
| `voice-growl` | `audio-dog-growl-1` | voice | 0.60 | 2,500 | `10a6ed88ea5bdf205f740c030ca29feff93a1d56dacb8a494b12ce2c402d7c1f` |
| `toy-squeak` | `audio-squeak-1` | effect | 0.55 | 900 | `5cb7dbab5a01285f4aea9f287aed9497ca5e6393140041e0cf64ff1b54c8007d` |
| `toy-brush` | `audio-brush-soft` | effect | 0.35 | 1,500 | `050067e4ea0166eaf9d6ad8942f444e8a28626866c36e05876d06c1cf81eda0e` |
| `toy-whistle` | `audio-whistle` | effect | 0.50 | 3,000 | `cff9705d18ce9556763a8c41aeecd72279e38465a3dfaeac56f8d214fce1b557` |
| `toy-handling` | `audio-toolbox-pickup` | effect | 0.35 | 600 | `0de003f1c8c9c54513b95c96ce9340eee3b65a2267efb1ed589ef7b4f9796844` |
| `radio-alert` | `audio-radio-receive` | alert | 0.45 | 800 | `d2580a30c8ec86c4ee54eca6b2e1d50a5fb07cc893703d627ee4d069605e88cc` |
| `rare-idle` | `audio-dog-growl-long-1` | rare-idle | 0.35 | 45,000 | `6812c247aaa9f230d9f863fa39a05b7133879811aca73f59e7db19b0cc5140e1` |

[`parsec-audio.sources.json`](../webapp/frontend/src/assets/parsec/audio/parsec-audio.sources.json) records each
source path/revision/hash, output hash, exact-copy transform, channel, authored volume, and cooldown. Its SHA-256 is
`ed11e853c55cc1b89830d8c4a269e055ea6033c6384a42371bb7208b21599401`.

- Audio remains enabled by default at 30% master. The rare-idle cue is additionally constrained by the 20% channel
  setting and 0.35 authored volume, for a default effective gain of 2.1% before Howler playback.
- Runtime schedules cues at the cumulative authored duration preceding their declared frame, cancels stale cue
  timers when the actor clip changes, and retains tab-leader, visibility, typing, concurrency, mute, and cooldown gates.
- `sound/items/radio/radio_receive.ogg` replaces the earlier toolbox-open placeholder for the alert channel.

## Meridian-Rift source inventory

The source checkout was inspected at revision `df0fb67eae69497be39e1dfc7f618f3d7964d3d5`. Unless a row
records a file-local exception, the recorded asset license is the repository README's Creative Commons
Attribution-ShareAlike 3.0 default. Authors are left as unrecorded when the repository contains no finer attribution.
Hashes are for the complete source file, before any extraction or adaptation.

### DMI candidates

| Asset ID | Status | Source path | DMI state | Dirs × frames | Revision | SHA-256 | License | Author / attribution | Notes |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- |
| `ss13-dogbed` | `accepted-source` | `icons/obj/bed.dmi` | `dogbed` | 1 × 1 | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `de4bea42f897c5870a295cdbdd9acc340df564a81765cec338945345d6026357` | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Exact frame extracted, alpha-cropped, and prepared at `3×` with baseline `y=90`. |
| `ss13-carrier-open` | `accepted-source` | `icons/obj/pet_carrier.dmi` | `pet_carrier_open` | 1 × 1 | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `63f335bbaffc8bf27f3e9a7706b8077f63b0f6a7e9c7f5f96bb9cffb31abcf5a` | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Open cage/habitat candidate. |
| `ss13-carrier-closed` | `accepted-source` | `icons/obj/pet_carrier.dmi` | `pet_carrier_closed` | 1 × 1 | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `63f335bbaffc8bf27f3e9a7706b8077f63b0f6a7e9c7f5f96bb9cffb31abcf5a` | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Closed but not semantically latched. |
| `ss13-carrier-locked` | `accepted-source` | `icons/obj/pet_carrier.dmi` | `pet_carrier_locked` over `pet_carrier_closed` | 1 × 1 | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `63f335bbaffc8bf27f3e9a7706b8077f63b0f6a7e9c7f5f96bb9cffb31abcf5a` | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | The authored state is only a lock overlay; production composites it onto the closed carrier before shared preparation. |
| `ss13-carrier-occupied` | `accepted-source` | `icons/obj/pet_carrier.dmi` | `pet_carrier_occupied` | 1 × 1 | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `63f335bbaffc8bf27f3e9a7706b8077f63b0f6a7e9c7f5f96bb9cffb31abcf5a` | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Occupancy treatment may be unsuitable if it obscures Parsec; review at production. |
| `ss13-tennis-ball` | `accepted-source` | `modular_nova/master_files/icons/obj/balls.dmi` | `tennis_classic` | 1 × 1 | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `43938986d723b8035653ba107fc63fa2106bf082fd09f1be723a939d42bb38d7` | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Nova Sector contributors | Default ball candidate; color variants remain available but are not rostered. |
| `ss13-hairbrush` | `accepted-source` | `modular_nova/modules/hairbrush/icons/hairbrush.dmi` | `brush` | 1 × 1 | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `9dcaf79b407ad47aa7c2759c36339663975174d4a2c4df48152ca4fb3c15b39f` | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Nova Sector contributors | Brush-tool candidate. Its sound has separate CC0 attribution below. |
| `ss13-toy-mouse` | `accepted-source` | `icons/obj/toys/toy.dmi` | `toy_mouse` | 1 × 1 | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `d207d30a2b55b259687c8679fa5c42b7291740f03ff8470c214f445a8f8758b2` | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Sixth lightweight toy candidate. |
| `ss13-carp-plush` | `accepted-source` | `icons/obj/toys/plushes.dmi` | `map_plushie_carp` | 1 × 1 | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `619a5749d74b1eb4e3404d26842eb781ea9b7cfa56909289289fa98aea49d973` | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Authored greyscale map state accepted after native atlas review. |
| `ss13-toolbox` | `accepted-source` | `icons/obj/storage/toolbox.dmi` | `red` | 1 × 1 | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `19d0d10907a834e3291b2f35ede0d81bdbb60c35f19ff2577b705e9b985f88a1` | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Station-flavored interaction prop; not a primary toy. |
| `ss13-tug-rope` | `accepted-source` | `icons/obj/stack_objects.dmi` | `coil` | 1 × 1 | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `cffe1747e4fc71e597831cb80c74c1a55022ea40b86e79b2a2eae4c3b57a96bf` | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Exact uncolored cable-coil base accepted as an improvised station tug loop. |
| `ss13-effect-heart` | `accepted-source` | `icons/mob/simple/animal.dmi` | `heart` | 1 × 8 | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `425c1eda2a0fb682abe43a1a07b62c159eb86cabb0e39c3eb9da2c217f8a1e51` | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Exact frames 0, 3, and 7 accepted. |
| `ss13-effect-station-alert` | `accepted-source` | `icons/mob/telegraphing/telegraph.dmi` | `exclamation` | 1 × 2 | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `bc649d2643418ce302435f321ccf1f2e8099df40d7f28bdf42d6b4dbcaa058f7` | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Both exact frames accepted; final frame is a recorded 35% alpha derivation. |
| `ss13-effect-radio-ping` | `accepted-source` | `icons/effects/effects.dmi` | `sonar_ping` | 1 × 7 | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `45758c6884179113f5b4ef725a2c2fb43e793e02191b340ddee6f7c2bd5c4804` | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Visible frames 1, 3, and 6 accepted; blank frame 0 rejected. |

### Audio candidates

| Asset ID | Status | Source path | Revision | SHA-256 | Duration ms | Channels | License | Author / attribution | Notes |
| --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| `audio-bark-1` | `accepted-source` | `modular_nova/modules/emotes/sound/voice/bark1.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `ca9e2a5e7b0b5cb168b2abbed19cac2ba603c623166b6fd977e5c2330081da4b` | 315 | 1 | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Nova Sector contributors | Accepted exact-copy voice bark. |
| `audio-bark-2` | `candidate` | `modular_nova/modules/emotes/sound/voice/bark2.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `19801c0e009f7c4cfb095032f5048c5d4995a91f898c382ef3a310a316010cd9` | 465 | 1 | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Nova Sector contributors | Voice candidate; take selection deferred to Max production. |
| `audio-dog-growl-long-1` | `accepted-source` | `modular_nova/modules/emotes/sound/voice/dgrowl.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `6812c247aaa9f230d9f863fa39a05b7133879811aca73f59e7db19b0cc5140e1` | 3086 | 2 | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Nova Sector contributors | Accepted exact-copy rare idle cue at 2.1% default effective gain. |
| `audio-dog-growl-long-2` | `candidate` | `modular_nova/modules/emotes/sound/voice/dgrowl2.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `54825faa8d0b374ae127a1632482543760490a21ac4f8489f7f74f9d1179ea42` | 2633 | 2 | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Nova Sector contributors | Dramatic/personality candidate; preview before selection. |
| `audio-brush-soft` | `accepted-source` | `modular_nova/modules/hairbrush/sounds/brush.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `050067e4ea0166eaf9d6ad8942f444e8a28626866c36e05876d06c1cf81eda0e` | 1258 | 2 | `CC0` | Caitlin_100, Hairbrush.mp3, Freesound 365499 | Exact attribution is stored beside the source. Runtime selection still waits for Max review. |
| `audio-brush-rough` | `accepted-source` | `modular_nova/modules/hairbrush/sounds/rough_brush.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `b791855f14bff5981b076c6158a215d96d3c69b6600afb6465a925d140675b4c` | 1699 | 2 | `CC0` | Caitlin_100, Hairbrush.mp3, Freesound 365499 | Exact attribution is stored beside the source. Runtime selection still waits for Max review. |
| `audio-toolbox-drop` | `candidate` | `sound/items/handling/toolbox/toolbox_drop.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `dd00b84944d6153c499acca511a2d3a4595f0dffe3e3c8c1e4b1c6ad17c9f395` | 750 | 1 | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | No finer file-local attribution was found. |
| `audio-toolbox-open` | `accepted-source` | `sound/items/handling/toolbox/toolbox_open.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `cda0a6bfbaefcdc32d8076db63bc10f4f2ac2584243294ae4eaa0f0f50e63f12` | 396 | 1 | `CC-BY-SA (version unrecorded)` | sadboysuss | Attribution and license are recorded in `sound/items/attributions.txt`. |
| `audio-toolbox-pickup` | `accepted-source` | `sound/items/handling/toolbox/toolbox_pickup.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `0de003f1c8c9c54513b95c96ce9340eee3b65a2267efb1ed589ef7b4f9796844` | 614 | 1 | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Accepted exact-copy handling cue. |
| `audio-radio-receive` | `accepted-source` | `sound/items/radio/radio_receive.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `d2580a30c8ec86c4ee54eca6b2e1d50a5fb07cc893703d627ee4d069605e88cc` | 443 | 2 | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Accepted exact-copy station-radio alert cue. |
| `audio-toolbox-rustle` | `accepted-source` | `sound/items/handling/toolbox/toolbox_rustle.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `3b2199cf1a41768d0210b01eaefb2b050b630a44381e03f54b3f168efdca514f` | 530 | 1 | `CC-BY-SA (version unrecorded)` | sadboysuss | Attribution and license are recorded in `sound/items/attributions.txt`. |
| `audio-squeak-1` | `accepted-source` | `sound/items/toy_squeak/toysqueak1.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `5cb7dbab5a01285f4aea9f287aed9497ca5e6393140041e0cf64ff1b54c8007d` | 109 | 1 | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Accepted exact-copy toy cue. |
| `audio-squeak-2` | `candidate` | `sound/items/toy_squeak/toysqueak2.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `a22862bd61c19682b59905a80e1e6dbc0b3073666253a64dfbac47eb06d0d7d8` | 153 | 1 | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Toy-channel candidate. |
| `audio-squeak-3` | `candidate` | `sound/items/toy_squeak/toysqueak3.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `70ce2fd2155cd75925a7960c46dc6a8a04da5bd4b5f5d9a38400a0b940e81891` | 108 | 1 | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Toy-channel candidate. |
| `audio-whistle` | `accepted-source` | `sound/items/whistle/whistle.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `cff9705d18ce9556763a8c41aeecd72279e38465a3dfaeac56f8d214fce1b557` | 1116 | 2 | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Accepted exact-copy recall cue. |
| `audio-dog-growl-1` | `accepted-source` | `sound/mobs/non-humanoids/dog/growl1.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `10a6ed88ea5bdf205f740c030ca29feff93a1d56dacb8a494b12ce2c402d7c1f` | 610 | 1 | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Accepted exact-copy short growl. |
| `audio-dog-growl-2` | `candidate` | `sound/mobs/non-humanoids/dog/growl2.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `80a90d6f218db37e707111137a574aad2031a0b1f8bb6b53d819a7ccf925acae` | 1008 | 1 | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Short reaction candidate. |
| `audio-mouse-squeak` | `candidate` | `sound/mobs/non-humanoids/mouse/mousesqueek.ogg` | `df0fb67eae69497be39e1dfc7f618f3d7964d3d5` | `7587eb9b03bfb77000cdb7c9acb6aac87e24e222e34f034b32a46152478df8dc` | 151 | 1 | `CC-BY-SA-3.0 (repository asset default)` | Unrecorded; Meridian-Rift/tgstation contributors | Toy-mouse candidate; production review must avoid implying Parsec herself squeaked. |

## Frozen creative roster

Rows remain explicit fallbacks until their production task is accepted. Exact clip-level timing and acceptance rules are in
[`parsec-animation-storyboards.md`](architecture/parsec-animation-storyboards.md).

| Atlas family | Required clips | Planned unique frames | Current status | Runtime fallback |
| --- | ---: | ---: | --- | --- |
| `parsec-core` | 10 | 59 | `accepted` | Legacy sheet retained as an emergency fallback |
| `parsec-feedback` | 10 | 46 | `accepted` | Legacy sheet retained as an emergency fallback |
| `parsec-touch` | 10 | 48 | `8 accepted; 2 coherent reuse` | Detached-tail sources are quarantined; reviewed success-wag motion resolves both pat reactions |
| `parsec-toys` | 12 | 59 | `10 accepted; 2 coherent reuse` | Detached-tail sources are quarantined; reviewed success-wag motion resolves brush-content and tug-win |
| `parsec-habitat` | 8 | 37 | `accepted` | Current sheet retained as an emergency fallback; SS13 furniture remains separately attached |
| `parsec-intrusive` | 5 | 27 | `accepted` | Current sheet retained as an emergency fallback |
| `parsec-effects` | 5 | 17 | `accepted` | Actor-only response retained as an emergency fallback |
| **Total** | **60** | **293** | **56 accepted sources; 4 coherent reuse; 19 source frames quarantined** | **All 60 runtime slots resolve; 4 replacement clips remain in the human-art backlog** |

Prepared non-clip slots: 11 accepted SS13 objects and 8 accepted audio cues. Every visual family passed native
`1×`, `4×` nearest-neighbor, authored-motion, and reduced-motion review.

### Runtime-recovery visual audit

The 2026-08-25 recovery audit supersedes the earlier frame-count-only acceptance claim. The versioned inventory
[`parsec-visual-reviews.v1.json`](../webapp/frontend/src/assets/parsec/parsec-visual-reviews.v1.json) records an
explicit status and reason for every production clip. Consolidated native and `4×` sheets are under
`review/runtime-recovery` (artifact removed), and every clip now has
standard authored-motion and reduced-motion output under
`review/motion` (artifact removed).

Four source families visibly shed detached tail or motion pixels at `4×` and are no longer production-resolved:
`touch-pat-soft`, `touch-pat-delighted`, `toy-brush-content`, and `toy-tug-win`. Their 19 source frames remain in
the repository for audit and later human replacement work, while their semantic runtime slots coherently reuse
the reviewed five-frame `feedback-success-wag` reaction. Production validation now runs visual lint over every
accepted source family, permits only recorded action/effect-specific exceptions, and rejects missing reviews.

## Legacy fallback animation rows

| State | Status | Sheet cells | Frames | Runtime use | Notes |
| --- | --- | --- | ---: | --- | --- |
| Seated idle | `available` | Row 0, columns 0–3 | 4 | No active work | Loopable seated posture with tail movement |
| Working patrol | `available` | Row 1, columns 0–5 | 6 | Active jobs and generic fetch/search fallback | Horizontal motion is supplied by the component |
| Happy | `available` | Row 2, columns 0–1 | 2 | Success and ordinary pat | Short one-shot reaction |
| Twerking | `available` | Row 3, columns 0–2 | 3 | Hidden repeated-pat reaction | Reuses a non-loopable sit/stand source sequence intentionally |

## Requested animations

Production animations use the legacy sheet's character identity as a reference, corrected yellow/pink eye
detail, transparent backgrounds, and the versioned `96 × 96` logical canvas. The legacy `72 × 51` cells remain
fallback-only.

| Asset ID | Desired state | Status | Priority | Intended event | Current fallback | Acceptance notes |
| --- | --- | --- | --- | --- | --- | --- |
| `parsec-search-sniff` | Nose-down sniffing loop | `available` | High | Search started or active | Working patrol | Accepted as runtime clip `search-sniff` |
| `parsec-fetch-dig` | Digging/snuffling loop | `available` | High | Delayed fetch | Working patrol | Accepted as runtime clip `fetch-dig` |
| `parsec-working-focus` | Calm attentive duty loop | `available` | High | Generic save, export, or index work | Working patrol | Accepted as runtime clip `feedback-working-focus` |
| `parsec-error-anxious` | Ears-back anxious whine | `available` | High | Error or lost connection | Seated idle | Accepted as runtime clip `error-anxious`; serious rather than comic |
| `parsec-empty-confused` | Head tilt | `available` | High | Empty search or unresolved context | Seated idle | Accepted as runtime clip `empty-confused` |
| `parsec-success-wag` | Excited tail-wag reaction | `available` | Medium | Save, export, or job success | Happy | Accepted as runtime clip `feedback-success-wag` |
| `parsec-success-proud` | Quiet proud completion hold | `available` | Medium | Low-distraction success | Happy | Accepted as runtime clip `feedback-success-proud` |
| `parsec-warning-alert` | Ears-up station alert | `available` | High | Actionable warning | Seated idle | Accepted as runtime clip `feedback-warning-alert` |
| `parsec-reconnect-pant` | Stationary panting | `available` | Medium | Long work, polling, or recovered connection | Seated idle | Accepted as runtime clip `reconnect-pant` |
| `parsec-invalid-disapprove` | Still disapproving stare | `candidate needed` | Medium | Invalid or rejected action | Seated idle | Subtle motion; avoid relying on text alone to communicate rejection |
| `parsec-tool-growl` | Braced growl | `available` | Medium | Tool or code failure | Seated idle | Accepted as runtime clip `tool-growl`; distinct from anxious data-safety errors |
| `parsec-lick` | Nose/hand lick reaction | `candidate needed` | Low | Pat interaction | Happy | Frozen for Task 6 as `touch-nose-lick` |

## Requested Parsec-specific icons

The frontend currently has no general icon-library dependency. Functional rollout must use text, existing
semantic colors, and accessible labels rather than adding a dependency solely for Parsec. These optional
pixel icons may be added by a human or accepted best-effort art pass when they improve scanning at native
size.

| Asset ID | Status | Priority | Intended use | Functional fallback | Acceptance notes |
| --- | --- | --- | --- | --- | --- |
| `parsec-icon-sniff` | `candidate needed` | Low | Search preview and asset documentation | Text label `Search` | Nose or scent mark; recognizable at 12–16 pixels |
| `parsec-icon-dig` | `candidate needed` | Low | Fetch preview | Text label `Fetching` | Paw or small displaced-dirt mark without visual noise |
| `parsec-icon-station-alert` | `candidate needed` | Medium | Warning/error preview | Existing semantic border plus text | Must remain distinct without color |
| `parsec-icon-wrench` | `candidate needed` | Low | Tooling/code-job preview | Text label `Tooling` | SS13 engineering flavor; no trademarked third-party icon copy |
| `parsec-icon-context` | `candidate needed` | Low | Shared selected-context preview | Text label `Context` | Communicates a pinned or selected record rather than generic search |

## Candidate review checklist

- Provenance, author, source URL, and license are recorded.
- The asset contains no unapproved human-authored lore, names, or descriptive copy.
- Transparent edges are clean at native size.
- Pixel scale, outline weight, fur palette, proportions, and corrected anatomical eye laterality match the identity contract.
- Animation is legible at `1×` and at enlarged nearest-neighbor scale.
- Loop endpoints do not jump unless the animation is explicitly a one-shot reaction.
- Existing frame coordinates and state behavior remain unchanged unless a versioned migration is documented.
- Reduced-motion mode has a representative static frame.
- The intended event, fallback, tests, and runtime mapping are recorded above.

## Candidate evaluation log

### 2026-08-24 — generated high-priority action sheet rejected

A built-in image-generation edit used the legacy sheet as its strict reference and attempted four
four-frame rows for sniffing, digging, anxious whining, and head tilting. The candidate was not copied
into the repository or connected to runtime code. It failed the native-scale review because it introduced
a dark non-transparent backdrop, changed the eye color and fur markings, used cells far larger than
`72 × 51`, and varied Parsec's silhouette and proportions between rows. It remained rejected; the later
per-clip `96 × 96` production pass superseded its fallbacks without reusing any rejected pixels.

### 2026-08-24 — first Max core-sheet candidate rejected

Built-in image generation used the legacy sheet as an edit target for the frozen core roster. The candidate
was not copied into the repository or connected to runtime code. It was RGB `1100 × 1429`, baked a pale
checkerboard instead of producing alpha, omitted most required frames and row structure, and retained incorrect
legacy eye colors. It is rejected. The corrected anatomical left-pink/right-yellow identity contract applies to
all subsequent candidates.

### 2026-08-24 — Task 5 per-clip rejections and corrections

- The first `core-idle-standing` attempt remained seated; it was rejected and regenerated as an actual standing
  loop.
- The first `core-idle-scratch` attempt broke leg/body anatomy; it was rejected rather than repaired with direct
  fill. A new anatomically stable strip replaced it.
- An early `core-idle-pant` attempt yielded blank/unusable cells; it was rejected and regenerated.
- A `feedback-working-focus` candidate exposed an incorrect second profile eye; it was rejected and regenerated.
- `core-look-cursor` frame 1 had the wrong visible profile eye. A tightly scoped ImageGen eye edit supplied only
  that frame; the other three accepted frames remain from the original strip.
- `core-idle-seated` frame 2 had a detached tail. Only that frame was rejected and replaced from the registered
  tail-alternate source. The rejected prepared frames were removed after integration.
- `error-anxious` frame 0 contained disconnected pink eye bars. A tightly scoped ImageGen eye edit replaced only
  frame 0; original frames 1–4 remain. The rejected preparation is retained under
  `prepared/superseded/error-anxious-disconnected-eye`.
- `empty-confused` frames 1–2 had swapped front-facing eye laterality. Their anatomy and motion were sound, so a
  deterministic localized eye recolor was accepted under the user-authorized direct-fill boundary.
- `tool-growl` exposed one detached background pixel, and `reconnect-pant` exposed a darker checker pattern that
  the first neutral-background threshold missed. Root-cause tests changed the postprocessor threshold and
  connected-component rule; both clips were regenerated. The residue-bearing preparations remain under
  `prepared/superseded`.
- The first motion dashboard flattened each four-direction walk sheet into one 12-frame loop. The art was valid,
  but playback would rotate Parsec between directions. Named three-frame direction variants and eight separate
  motion reviews corrected the runtime contract without changing accepted pixels.

### 2026-08-24 — Task 5 acceptance

All 59 core frames and 46 feedback frames passed blank-frame, component, anchor, identity, native `1×`, enlarged
`4×`, authored-motion, and reduced-motion review. Current source strips, selected-frame composition inputs, output hashes, and runtime mappings are retained;
superseded candidates and review exports have been removed.

## Maintenance locations

- Product behavior and event design:
  [`references/architecture/parsec-feedback-design.md`](architecture/parsec-feedback-design.md)
- Runtime sprite component:
  [`webapp/frontend/src/components/parsec/ParsecSprite.tsx`](../webapp/frontend/src/components/parsec/ParsecSprite.tsx)
- Versioned atlas manifest, mappings, and fallbacks:
  [`webapp/frontend/src/assets/parsec/manifest.v1.ts`](../webapp/frontend/src/assets/parsec/manifest.v1.ts)
- Accepted sprite sheets:
  [`parsec-core.png`](../webapp/frontend/src/assets/parsec/parsec-core.png),
  [`parsec-feedback.png`](../webapp/frontend/src/assets/parsec/parsec-feedback.png),
  [`parsec-touch.png`](../webapp/frontend/src/assets/parsec/parsec-touch.png), and
  [`parsec-toys.png`](../webapp/frontend/src/assets/parsec/parsec-toys.png), and
  [`parsec-habitat.png`](../webapp/frontend/src/assets/parsec/parsec-habitat.png)
- Single human-edit character sheet and authoritative cell map:
  `human-reference/README.md` (artifact removed)
- Safe sheet builder and staging importer:
  [`build_character_reference.py`](../tools/parsec_assets/build_character_reference.py) and
  [`split_character_reference.py`](../tools/parsec_assets/split_character_reference.py)
- Maintainer visual-review dashboard:
  `webapp/frontend/src/assets/parsec/review/motion/index.html` (artifact removed)
- Generated sources, prepared frames, and retained rejected candidates:
  [`webapp/frontend/src/assets/parsec`](../webapp/frontend/src/assets/parsec)
- Settings, previews, attribution, and history:
  [`webapp/frontend/src/tools/parsec/ParsecPage.tsx`](../webapp/frontend/src/tools/parsec/ParsecPage.tsx)
- In-app discoverability: the **Parsec** page links this register, the runtime sheet, its upstream source,
  and license; exact diagnostics appear in its recent-history list separately from character-facing copy.


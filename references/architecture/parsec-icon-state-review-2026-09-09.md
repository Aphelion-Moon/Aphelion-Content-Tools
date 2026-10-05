# Parsec icon-state review, 9 September 2026

## Visual standard and scope

The simple `core-idle-standing` profile and the cardinal walking set establish pixel density, flat coat
colors, contained silhouettes, and readable eye placement. The intrusive set is useful for expressive
poses, but added detail is not itself an improvement. The maintainer rejected a detailed seated-idle
candidate during this review; production uses the later simple profile instead.

All 60 required states retain the 96px transparent cell contract and 293 planned unique frames. Review
artifacts cover 66 sequences because the two walking clips each have four directions. Seventeen
families received replacement frames:

| Area | Replaced families |
| --- | --- |
| Core | `core-idle-seated`, `core-idle-sniff`, `core-look-cursor`, `core-walk-diagonal` |
| Feedback | `feedback-success-wag`, `feedback-success-proud`, `feedback-warning-alert`, `reconnect-pant` |
| Handling | `touch-nose-lick`, `touch-scruff-pout`, `touch-landing-bounce` |
| Toys | `toy-ball-ready`, `toy-ball-refuse`, `toy-treat-accept`, `toy-whistle-recall` |
| Habitat | `habitat-cage-open-idle`, `habitat-cage-release` |

The two pat states, tug win, and contented brushing reuse the repaired wag frames. Reuse now preserves
each state's own sound cues and loop mode. The simple seated idle holds for 2600ms, breathes for 800ms,
blinks for 120ms, and settles for 900ms. Reduced motion uses its open-eyed resting pose.

The maintainer corrected the contract after the first review: the anatomical left eye is pink and the
right eye is Supermatter yellow. Left-facing profiles and the frontal viewer-left eye show yellow.
Walking selects authored directional frames without mirroring. Preserved generation files document
the earlier reversed contract; the current runtime and touchup record supersede it.
The landing crouch's 22% occupied-height range is intentional compression and recovery; its review uses
the existing `intentional-pose-range` classification. Small detached scruff marks were removed through
a new source revision rather than exempted from residue validation.

All eight toolbar actions have icons and labels. Existing object-atlas art supplies ball, tug, brush, bed,
and cage; small flat pixel glyphs supply pat, treat, and whistle. Selection, keyboard focus, disabled
states, and the cage's Release action remain explicit. Draggable toys use the same art as their controls.

## Function repairs

- Reduced-motion one-shot clips finish on their authored schedule, so landing and furniture sequences
  continue while displaying a still pose.
- Cancelled actor gestures retain the last position and release with zero velocity. Escape ends pointer
  capture once. Toy capture also ends on Escape, close, lost capture, and disposal.
- Habitat pats use the same runtime path as the toolbar. Closed-cage controls explain why interactions
  are unavailable and retain the explicit Release action.
- Ask-each-time consent requests a single excursion and remains ask-each-time after approval. Competing
  feedback and explicit actions invalidate pending requests. The scheduler respects active work,
  handling, play, landing, and return animations.
- Saving habitat-only settings recalls an excursion. A setting changed while held takes effect when
  the gesture settles, preserving pointer ownership during the gesture.
- Ending brushing returns to idle; a looping brush response no longer blocks future autonomy forever.
- Habitat furniture placement and dragging use the same stage bounds. Actor placement no longer
  includes the toolbar and radio log when converting normalized bed/cage coordinates.
- The bounded Python suite runner supports an explicit `pytest` runner. Parsec's function-based asset
  tests were previously dispatched through `unittest`, producing zero collected tests.

## Maintainer-marked ear and forehead follow-up

The maintainer rejected the first pixel pass: it left white bridges between the ears, strips outside
the forehead, and a wedge behind the diagonal walking head. The next pass reviewed all 276 actor
frames and changed 168 of them using explicit pixel edits. It opened the ear gaps, traced all five
search-sniff forehead contours, and preserved the white inside both diagonal ears. The draft cuts on
turned heads were narrowed before integration to preserve ears, backs, and tails.

This pass removed another 11,727 opaque background pixels. The cumulative touchup ledger now records
19,557 cleared pixels across 174 frames. The 665 recorded pink eye pixels, 1,799 yellow eye pixels,
and 253 coral tongue pixels remained unchanged. Atlas coordinates and authored timings are unchanged.

The generated galleries and before/after sheets were removed at the maintainer's request after review.
The cumulative source-to-production edit ledger remains fully replayable. Required originals now live
under `source/touchups/2026-09-09/originals`; the extra intermediate ear-pass backup was removed.

The new regression cases failed on the previous production artwork at the marked ear and forehead
locations. After integration, all 83 asset tests passed, including both-ear preservation, the lowered
head's inner ear, exact source replay, and all 276 actor atlas crops. TypeScript and the production
Vite build passed, as did Ruff and Pyright. The rebuilt app was opened through the running maintained
launcher and the seated sprite inspected in the habitat. The gallery's file URL was blocked by browser
policy, so its raster frames and generated sequence timings were inspected directly; the gallery was
not browser-tested in this follow-up. These checks protect identified defects; they do not establish
artistic acceptance. The earlier full Python resource-warning failure below remains unresolved.

## Provenance and review artifacts

The first pixel pass inspected all 276 actor frames and the legacy fallback sheet. It removed 7830
exterior-fill pixels across 116 frames, including the seated jaw and sniffing muzzle/foreleg gap. The
importer's automatic convex-hull face rescue was the source of attached white fill; it has been removed.
White fur, eye highlights, and tongue colors are preserved by explicit edits rather than a global white
color key. Eye edits distinguish anatomical sides and exclude pink tongues and closed-eye poses.

- [Pixel touchup inventory](../../webapp/frontend/src/assets/parsec/source/touchups/2026-09-09/manifest.json)
  binds every exact edit and eye location to a preserved source hash. Edits reject mismatched source
  hashes, unexpected original colors, duplicate coordinates, and out-of-bounds pixels.
- [Generation inventory](../../webapp/frontend/src/assets/parsec/source/generated/review-20260909/generation.json)
  records retained source artwork, hashes, and actions. Imported staging copies were removed.
- [Retained-image inventory](../../webapp/frontend/src/assets/parsec/source/retained-images.v1.json)
  lists the 701 remaining images and why each is needed. The cleanup removed 2,961 redundant images
  net, including all stored review galleries. It relocated 286 required originals into the source tree
  without changing their bytes; production atlas and editable-frame pixels are unchanged.
- [Asset maintenance guide](../../webapp/frontend/src/assets/parsec/README.md) explains regenerating
  temporary reviews and human-edit sheets when needed. Generated outputs belong outside source control.

Preparation uses the maintained `postprocess_generated_strip`, `outline_prepared_tree`, `build_atlas`,
`derive_frame_anchors`, and `build_motion_review` tools. Atlas coordinates are rebuilt deterministically;
only anchors belonging to replaced artwork change. No game sprites or generated DreamMaker were edited.

## Verification

The follow-up pixel pass passed 73 asset tests, including exact source-to-production replay, all 276
actor atlas crops, the corrected profile/front eye orientation, iris-edge colors, and the seated
transparency regression. The full frontend check passed 341 tests in 66 files, typecheck, and build.
After the final shoulder-contour refinement, all 73 asset tests and the production build passed again.
Ruff and Pyright passed; the bounded documentation/testing group passed 20 tests. The rebuilt app was
opened through the still-running maintained launcher and the final seated sprite checked in the habitat.
No additional full Python baseline run was attempted; the earlier unrelated socket warning below remains.

- `npm run check`: API schema generation, TypeScript, all 341 frontend tests in 66 files, and the
  production Vite build passed. Parsec introduces no HTTP schema changes.
- The maintained bounded Python runner passed `docs_and_testing` (20 tests) and `parsec_assets`
  (62 tests), including production asset validation and preserved-source hashes.
- Ruff and Pyright passed with zero errors. The writer-guide documentation checks passed (5 tests).
- `git diff --check` passed. The final working-tree inventory preserves unrelated existing changes;
  verification logs and inventories are retained locally under `.tmp/parsec-review-20260909/`.

The full bounded Python run also recorded an unrelated unclosed-socket ResourceWarning in
`webapp_core` / `test_version_and_session_metadata`; its 142 tests passed, but the runner correctly marks
that resource-warning gate unsuccessful. The other bounded groups completed. Do not call this a clean
repository-wide Python pass.

The real `Launch Aphelion Content Tools.cmd` entry point started the production SPA on loopback. Browser
checks exercised habitat consent, cage disable/release, toolbar icons, keyboard interactions, and the
new idle. A final reduced-motion bed check reached the resting pose inside the habitat stage; motion
was restored to Animate afterward. The application remains open for review, so launcher shutdown
was not checked. Existing catalog/graph revision staleness and unconfigured map collaboration are visible
application conditions unrelated to this change. Human approval of the final art remains distinct from
structural validation and automated interaction tests.

Changes remain uncommitted.

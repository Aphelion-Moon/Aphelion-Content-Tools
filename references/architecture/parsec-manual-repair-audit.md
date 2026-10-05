# Parsec Manual Sprite Repair Audit

For current replacements, see the [9 September review](parsec-icon-state-review-2026-09-09.md).
The tables below retain the historical 26 August findings; the later review supersedes its listed
17 families, including the seated idle rejected by the maintainer for style mismatch.

**Date:** 2026-08-26  
**Scope:** every production character clip, effect family, and SS13 object at native size and `4×`
nearest-neighbor scale. Authored motion remains a separate acceptance gate for each replacement.

The earlier blanket visual acceptance is not reliable. Structural lint found residue and bounds errors, but it
did not detect malformed faces, inconsistent eye clusters, pose-to-pose anatomy drift, or the visible quality
gap between the older flat animation batches and the newer organic intrusive-mode art.

Status meanings:

- `integrated repair` — replacement is in the production prepared set and atlas.
- `accepted current` — no blocking defect was found in the enlarged manual review.
- `repair required` — production remains available for feature continuity, but it is not artistically accepted.
- `coherent reuse` — the prior broken source was removed during September cleanup; runtime uses a reviewed substitute.

All six character atlases received the recorded `dark-silhouette-outline-tree-v1` preparation after the
2026-08-26 enlarged review. It replaces exposed white or gray matte pixels on the main actor silhouette with a
one-pixel dark boundary while leaving detached toy/effect components intact. The pre-pass prepared trees and
runtime atlases were formerly kept under `prepared/superseded/outline-pass-2026-08-26` and
`superseded/runtime-before-outline-pass-v1`; September cleanup removed both. Current `prepared/`
trees, source replay records, and root atlases are the rebuild authority. This mechanical cleanup does not change any `repair required`
classification below; those clips still need new or manually rebuilt faces, eyes, and pose continuity.

## Core

| Clip | Status | Manual finding |
| --- | --- | --- |
| `core-idle-seated` | integrated repair | Replaced all four malformed old frames with organic repair v4, including a deterministic dark silhouette boundary; historical old frames and atlases were removed during September cleanup; current manifests and replay/source records preserve provenance. |
| `core-idle-standing` | accepted current | Stable profile, baseline, face, and attached tail. |
| `core-idle-sniff` | repair required | Reads substantially smaller and flatter than the quality target. |
| `core-idle-scratch` | integrated repair | Replaced all five chopped-eye/face frames with organic repair v2 and reviewed the authored scratch cycle. |
| `core-idle-yawn` | integrated repair | Replaced all five black-eye-line and shifting-face frames with organic repair v2 and reviewed the authored yawn cycle. |
| `core-idle-pant` | accepted current | Stable silhouette and readable mouth cycle. |
| `core-look-cursor` | repair required | Head scale and face construction jump between frames. |
| `core-walk-cardinal` | accepted current | Strongest older directional set; all four directions remain readable. |
| `core-walk-diagonal` | repair required | Perspective and pose continuity are inconsistent, especially the south-west row. |
| `core-return-home` | accepted current | Transition is readable and does not expose a blocking face defect. |

## Feedback

| Clip | Status | Manual finding |
| --- | --- | --- |
| `search-sniff` | accepted current | Coherent nose-down search; cyan scent pixels are intentional. |
| `fetch-dig` | accepted current | Coherent digging motion and face placement. |
| `feedback-working-focus` | accepted current | Stable seated focus loop. |
| `feedback-success-wag` | repair required | Frame 2 has a blown-out face/eye and frame 3 has an inconsistent eye cluster. |
| `feedback-success-proud` | repair required | Frame 2 eye collapses into a horizontal slit unrelated to the pose. |
| `feedback-warning-alert` | repair required | Frame 2 jumps in scale and body construction beneath the alert effect. |
| `error-anxious` | accepted current | Large pose range is intentional and readable. |
| `empty-confused` | accepted current | Front-facing eye laterality is correct and the head tilt is coherent. |
| `tool-growl` | accepted current | Growl posture remains readable; no detached residue remains. |
| `reconnect-pant` | repair required | Frame 0 uses an oversized, poorly integrated eye cluster. |

## Touch and handling

| Clip | Status | Manual finding |
| --- | --- | --- |
| `touch-pat-soft` | coherent reuse | Prior broken source was removed from retained assets; runtime uses `feedback-success-wag`. |
| `touch-pat-delighted` | coherent reuse | Prior broken source was removed from retained assets; runtime uses `feedback-success-wag`. |
| `touch-nose-lick` | repair required | Frame 2 contains a malformed multicolor eye/face cluster. |
| `touch-scruff-calm` | accepted current | Stable self-contained lift with no visible holder. |
| `touch-scruff-playful` | accepted current | Coherent playful held motion. |
| `touch-scruff-pout` | repair required | Frame 3 contains a large dark-red eye block. |
| `touch-release-drop` | accepted current | Controlled release reads coherently. |
| `touch-release-toss` | accepted current | Airborne sequence is readable despite its intentional pose range. |
| `touch-landing-bounce` | repair required | Eye treatment and body scale vary materially across the bounce. |
| `touch-landing-recover` | accepted current | Grounded recovery is coherent. |

## Toys

| Clip | Status | Manual finding |
| --- | --- | --- |
| `toy-ball-ready` | repair required | Final frame eye is muted and poorly integrated. |
| `toy-ball-chase` | accepted current | Coherent run cycle at the intended smaller action scale. |
| `toy-ball-retrieve` | accepted current | Search-to-return sequence is readable. |
| `toy-ball-refuse` | repair required | Frames 1-2 lose the normal eye/face construction. |
| `toy-tug-grip` | accepted current | Braced posture is stable. |
| `toy-tug-pull` | accepted current | Pull loop is stable. |
| `toy-tug-win` | coherent reuse | Prior broken source was removed from retained assets; runtime uses `feedback-success-wag`. |
| `toy-tug-tumble` | accepted current | Large pose range is intentional and readable. |
| `toy-brush-content` | coherent reuse | Prior broken source was removed from retained assets; runtime uses `feedback-success-wag`. |
| `toy-brush-impatient` | accepted current | Rear turn is intentional and returns to a coherent seat. |
| `toy-treat-accept` | repair required | Frame 3 has a broken eye-line and frame 4 is cropped at the cell edge. |
| `toy-whistle-recall` | repair required | Final frame has an inconsistent salmon eye cluster. |

## Habitat, intrusive mode, effects, and objects

| Family | Status | Manual finding |
| --- | --- | --- |
| Bed clips | accepted current | Approach, lie-down, sleep, and timeout sequences are readable. |
| `habitat-cage-enter` | accepted current | Entry-to-seat sequence is readable. |
| `habitat-cage-open-idle` | repair required | Final frame face and eye cluster are malformed. |
| `habitat-cage-latched-pout` | accepted current | Pout range is intentional and readable. |
| `habitat-cage-release` | repair required | Final frame loses the visible profile eye. |
| Intrusive clips | accepted current | These five clips establish the organic quality target for replacements. |
| Effect clips | accepted current | Detached dust, hearts, radio ping, scent, and station alert pixels are intentional. |
| SS13 objects | accepted current | Bed and cage sources are clean at `4×`; remaining acceptance issue is in-app scale and interaction feel. |

## Repair order

The historical `parsec-character-sheet.png` handoff and its staging exports were removed during
September cleanup. Current editing authority is the cumulative touchup manifest, immutable originals,
and composition sources described in the [asset maintenance guide](../../webapp/frontend/src/assets/parsec/README.md).
The following list records the August backlog; the September review above supersedes repaired families.

1. Always-visible core faces and locomotion: scratch, yawn, cursor look, sniff, and diagonal walk.
2. High-frequency feedback and handling: success wag/proud, warning, reconnect, nose lick, scruff pout, and bounce.
3. Toys and cage transitions: ball ready/refuse, treat, whistle, cage open, and cage release.
4. Rebuild each affected atlas only after the replacement clip passes per-clip structural, native, `4×`, motion,
   reduced-motion, and in-app review.

Per-clip enlarged sheets are generated with
[`build_clip_audit.py`](../../tools/parsec_assets/build_clip_audit.py) under
an external scratch directory. The historical
`webapp/frontend/src/assets/parsec/review/manual-repair-audit/` output was removed during September cleanup.

# Parsec Animation Storyboards

Status: frozen pre-production roster, 2026-08-24

This is the production contract for Parsec's creative sprint. It contains 60 required clips and 293 planned
unique frames. The runtime manifest carries the same IDs, atlas assignments, frame budgets, required anchor
sets, reduced-motion representative, and explicit legacy fallback. No row in this document means that art
or audio has been accepted.

## Fixed production rules

- Every authored frame occupies one unscaled `96 × 96` RGBA cell. Empty transparent area is permitted.
- Directional walking covers all eight directions: four cardinal directions in one clip and four diagonals
  in the other. Three gait phases per direction produce 12 unique frames in each clip.
- `I` means interruptible. Every rostered clip is interruptible so serious feedback, direct handling, and
  confinement can take control without waiting for cosmetic motion.
- Timing values are ordered frame durations in milliseconds. `×N` expands to N identical values.
- Reduced motion (`RM`) is a zero-based frame index. The renderer holds that frame and suppresses translation,
  bounce, flash, particles, and repeated audio.
- Sound entries name prepared manifest slots and the zero-based frame where the cue begins. They remain silent
  fallbacks until a source is accepted during Max production.
- `standard` occupancy preserves the current recognizable body scale within roughly the central `72 × 64`
  region. `extended` may use the full canvas for limbs, thrown motion, or effects. `effect` keeps the actor
  silhouette static and uses only the effect region.

## Anchor contract

Anchor coordinates are integral logical pixels in the inclusive range `0..95`. These neutral template points
are used when a pose does not require anatomical displacement: `feet (48,82)`, `face (48,30)`, `scruff (48,24)`,
`mouth (56,34)`, `interaction (48,44)`, `toy (62,48)`, `effect (48,12)`, and `shadow (48,84)`. During production,
each required anchor is moved to the exact anatomical or effect attachment point in that frame; absence,
fractional coordinates, and out-of-canvas values fail validation. Feet and shadow remain stable across a
stationary loop. A moving loop may change feet but cannot introduce visible ground sliding at native scale.

All rows are reviewed at native scale, `4×` nearest-neighbor scale, authored cadence, and RM hold. In addition
to the row-specific read, acceptance requires stable fur palette, outline, proportions, anatomical left
neon-pink eye (`#FF3CC8`), anatomical right Supermatter-yellow eye (`#FBD436`), clean
transparency, correct anchors, no accidental one-pixel noise, and no loop seam unless the clip is a one-shot.

## `parsec-core` — 10 clips, 59 frames

| ID | Trigger / storyboard | Dirs | Frames | Timing ms | Mode | I | Required anchors | Sound | RM | Occupancy | Required read | Fallback |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| `core-idle-seated` | Default habitat rest; breathe, blink, small tail movement | 1 | 4 | `320,320,180,420` | loop | yes | feet, face, scruff | — | 0 | standard | Calm and available, not frozen | `seated-idle` |
| `core-idle-standing` | Alert rest between movements | 1 | 4 | `260×4` | loop | yes | feet, face, scruff | — | 0 | standard | Curious readiness | `seated-idle` |
| `core-idle-sniff` | Context-aware idle investigation | 1 | 4 | `180,180,240,300` | loop | yes | feet, face, mouth | rare-idle@1 | 0 | standard | Nose-led curiosity | `working-patrol` |
| `core-idle-scratch` | Rare self-directed idle | 1 | 5 | `140,120,120,160,320` | once | yes | feet, face | rare-idle@1 | 4 | extended | Loose, ordinary canine life | `seated-idle` |
| `core-idle-yawn` | Rare low-energy idle | 1 | 5 | `180,180,260,220,420` | once | yes | feet, face, mouth | rare-idle@2 | 4 | standard | Sleepy without implying neglect | `seated-idle` |
| `core-idle-pant` | Long session or recovered work | 1 | 4 | `220×4` | loop | yes | feet, face, mouth | — | 0 | standard | Comfortable exertion | `seated-idle` |
| `core-look-cursor` | Passive cursor observation after consent | 1 | 4 | `180,180,180,360` | hold | yes | feet, face | — | 3 | standard | Attentive, never chasing | `seated-idle` |
| `core-walk-cardinal` | Edge-biased movement N/E/S/W, three gait phases each | 4 | 12 | `120×12` | loop | yes | feet, face | — | 0 | standard | Grounded readable locomotion | `working-patrol` |
| `core-walk-diagonal` | Edge-biased movement NE/SE/SW/NW, three phases each | 4 | 12 | `120×12` | loop | yes | feet, face | — | 0 | standard | Same stride and scale as cardinal | `working-patrol` |
| `core-return-home` | Whistle/cancel excursion path into habitat | 1 | 5 | `120,120,120,160,260` | once | yes | feet, face | toy-whistle@0 | 4 | standard | Willing recall, no teleport read | `working-patrol` |

## `parsec-feedback` — 10 clips, 46 frames

| ID | Trigger / storyboard | Dirs | Frames | Timing ms | Mode | I | Required anchors | Sound | RM | Occupancy | Required read | Fallback |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| `search-sniff` | Search accepted and running; nose sweeps a small arc | 1 | 5 | `150,150,180,150,240` | loop | yes | feet, face, mouth, effect | — | 2 | standard | Actively searching | `working-patrol` |
| `fetch-dig` | Delayed record/catalog fetch; forepaws dig without debris spam | 1 | 6 | `110×6` | loop | yes | feet, face, interaction, effect | — | 0 | extended | Work continues, not stalled | `working-patrol` |
| `feedback-working-focus` | Generic save/export/index work | 1 | 4 | `220×4` | loop | yes | feet, face | — | 0 | standard | Concentrated and calm | `working-patrol` |
| `feedback-success-wag` | Save/export/job success | 1 | 5 | `120,100,100,120,300` | once | yes | feet, face, effect | voice-bark@2 | 4 | extended | Excited but brief celebration | `happy-reaction` |
| `feedback-success-proud` | Quiet completion after noisy success is suppressed | 1 | 4 | `160,160,220,420` | hold | yes | feet, face | — | 3 | standard | Smug, proud posture | `happy-reaction` |
| `feedback-warning-alert` | Actionable warning; ears rise before radio detail | 1 | 4 | `120,140,220,360` | once | yes | feet, face, effect | radio-alert@1 | 3 | standard | Serious and legible without comedy | `seated-idle` |
| `error-anxious` | Failed request, disconnect, or data-safety error | 1 | 5 | `160,180,220,220,360` | loop | yes | feet, face | voice-growl@1 | 3 | standard | Ears back; concern, not slapstick | `seated-idle` |
| `empty-confused` | Empty result or unresolved context | 1 | 4 | `180,220,220,420` | once | yes | feet, face | — | 2 | standard | Clear head tilt | `seated-idle` |
| `tool-growl` | Code/tool failure distinct from user-data danger | 1 | 5 | `140,140,180,180,320` | once | yes | feet, face, mouth | voice-growl@2 | 4 | standard | Frustration directed at tooling | `seated-idle` |
| `reconnect-pant` | Connection restored or long poll ends | 1 | 4 | `200×4` | loop | yes | feet, face, mouth | — | 0 | standard | Relief and recovery | `seated-idle` |

## `parsec-touch` — 10 clips, 48 frames

| ID | Trigger / storyboard | Dirs | Frames | Timing ms | Mode | I | Required anchors | Sound | RM | Occupancy | Required read | Fallback |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| `touch-pat-soft` | Ordinary pat or keyboard pat | 1 | 4 | `140,140,180,320` | once | yes | feet, face, interaction | — | 3 | standard | Warm acceptance | `happy-reaction` |
| `touch-pat-delighted` | Familiar expressive pat reaction | 1 | 5 | `110,110,140,180,320` | once | yes | feet, face, interaction, effect | voice-bark@2 | 4 | extended | Tail-forward delight | `happy-reaction` |
| `touch-nose-lick` | Rare affectionate direct response | 1 | 5 | `120,140,180,160,320` | once | yes | feet, face, mouth, interaction | — | 4 | extended | Playful nonsexual affection | `happy-reaction` |
| `touch-scruff-calm` | Slow carry under subdued handling reactions | 1 | 4 | `180×4` | hold | yes | face, scruff | — | 0 | standard | Relaxed dangling posture | `seated-idle` |
| `touch-scruff-playful` | Expressive carry or self-initiated play | 1 | 5 | `130×5` | loop | yes | face, scruff | voice-bark@2 | 0 | extended | Squirming, amused engagement | `happy-reaction` |
| `touch-scruff-pout` | Repeated or unwanted dramatic carry | 1 | 5 | `180×5` | loop | yes | face, scruff | voice-growl@1 | 0 | standard | Complaining/pouting, never distressed harm | `seated-idle` |
| `touch-release-drop` | Carry-only or low-speed release | 1 | 4 | `90,110,140,260` | once | yes | feet, face, scruff | toy-handling@2 | 3 | extended | Controlled settle | `working-patrol` |
| `touch-release-toss` | Full-tossing release arc pose sequence | 1 | 6 | `80,80,90,100,120,220` | once | yes | feet, face, scruff | — | 5 | extended | Playful momentum, no injury read | `working-patrol` |
| `touch-landing-bounce` | Physics landing and one allowed bounce | 1 | 6 | `70,80,90,100,140,260` | once | yes | feet, face, effect | toy-handling@0 | 5 | extended | Squash/recover with stable final ground | `working-patrol` |
| `touch-landing-recover` | Return to ordinary grounded behavior | 1 | 4 | `100,120,160,300` | once | yes | feet, face | — | 3 | standard | Shakes off and reorients | `seated-idle` |

## `parsec-toys` — 12 clips, 59 frames

| ID | Trigger / storyboard | Dirs | Frames | Timing ms | Mode | I | Required anchors | Sound | RM | Occupancy | Required read | Fallback |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| `toy-ball-ready` | Ball placed or held near Parsec | 1 | 4 | `160,140,140,320` | hold | yes | feet, face, mouth, toy | toy-squeak@1 | 3 | standard | Focus locked on ball | `seated-idle` |
| `toy-ball-chase` | User throws ball | 1 | 6 | `90×6` | loop | yes | feet, face, toy | — | 0 | extended | Fast chase without UI-obscuring trail | `working-patrol` |
| `toy-ball-retrieve` | Pickup, carry, and return | 1 | 6 | `110×6` | once | yes | feet, face, mouth, toy | toy-squeak@0 | 5 | standard | Ball clearly held at mouth anchor | `working-patrol` |
| `toy-ball-refuse` | Rare familiar playful refusal | 1 | 4 | `180,180,220,420` | once | yes | feet, face, toy | — | 3 | standard | Teasing, not broken pathing | `seated-idle` |
| `toy-tug-grip` | Tug offered within interaction range | 1 | 4 | `130,130,180,260` | hold | yes | feet, face, mouth, toy | toy-squeak@1 | 3 | standard | Secure bite and braced stance | `seated-idle` |
| `toy-tug-pull` | Pointer tension changes | 1 | 6 | `100×6` | loop | yes | feet, face, mouth, toy | — | 0 | extended | Tension readable through body line | `working-patrol` |
| `toy-tug-win` | User releases under high tension | 1 | 5 | `90,100,120,180,320` | once | yes | feet, face, mouth, toy | voice-bark@2 | 4 | extended | Triumphant possession | `happy-reaction` |
| `toy-tug-tumble` | Sudden release under dramatic reactions | 1 | 5 | `80,90,100,160,320` | once | yes | feet, face, toy | toy-handling@3 | 4 | extended | Comic tumble without injury | `twerking-reaction` |
| `toy-brush-content` | Directional strokes at comfortable cadence | 1 | 5 | `160×5` | loop | yes | feet, face, interaction | toy-brush@1 | 0 | standard | Content lean into brush | `happy-reaction` |
| `toy-brush-impatient` | Rough/repeated strokes or impish mood | 1 | 4 | `140,180,220,360` | once | yes | feet, face, interaction | toy-brush@1 | 3 | standard | Huffy but safe boundary cue | `seated-idle` |
| `toy-treat-accept` | Treat offered directly or placed | 1 | 5 | `110,120,140,180,320` | once | yes | feet, face, mouth, toy | toy-squeak@1 | 4 | standard | Enjoyment without hunger/debt | `happy-reaction` |
| `toy-whistle-recall` | Recall, cancel excursion, or allowed invitation | 1 | 5 | `100,120,140,180,280` | once | yes | feet, face, effect | toy-whistle@0 | 4 | standard | Immediate attention then movement | `working-patrol` |

## `parsec-habitat` — 8 clips, 37 frames

| ID | Trigger / storyboard | Dirs | Frames | Timing ms | Mode | I | Required anchors | Sound | RM | Occupancy | Required read | Fallback |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| `habitat-bed-approach` | Bed command or voluntary hangout | 1 | 4 | `120,120,160,260` | once | yes | feet, face, interaction | — | 3 | standard | Intentional approach | `working-patrol` |
| `habitat-bed-lie-down` | Enter bed area and settle | 1 | 5 | `120,140,160,200,360` | once | yes | feet, face, interaction | toy-handling@2 | 4 | standard | Body aligns with bed | `seated-idle` |
| `habitat-bed-sleep` | Voluntary rest or long timeout | 1 | 5 | `360,360,180,360,520` | loop | yes | feet, face, effect | rare-idle@2 | 0 | standard | Comfortable sleep, no care obligation | `seated-idle` |
| `habitat-bed-timeout-pout` | Temporary timeout bed mode | 1 | 4 | `260×4` | loop | yes | feet, face | voice-growl@1 | 0 | standard | Pout distinguishes timeout from sleep | `seated-idle` |
| `habitat-cage-enter` | Cage command or scruff drop into open cage | 1 | 5 | `110,120,140,180,300` | once | yes | feet, face, interaction | toy-handling@3 | 4 | standard | Clean transition into opening | `working-patrol` |
| `habitat-cage-open-idle` | Inside an open cage | 1 | 4 | `280×4` | loop | yes | feet, face | — | 0 | standard | Aware she may leave | `seated-idle` |
| `habitat-cage-latched-pout` | Hard confinement while latch is closed | 1 | 5 | `220×5` | loop | yes | feet, face | voice-growl@2 | 0 | standard | Reactive pout/huff; never self-release | `seated-idle` |
| `habitat-cage-release` | User opens/releases cage | 1 | 5 | `110,120,140,180,300` | once | yes | feet, face, interaction | voice-bark@2 | 4 | standard | Relief or playful smugness | `happy-reaction` |

## `parsec-intrusive` — 5 clips, 27 frames

| ID | Trigger / storyboard | Dirs | Frames | Timing ms | Mode | I | Required anchors | Sound | RM | Occupancy | Required read | Fallback |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| `intrusive-cursor-stalk` | Intrusive mode autonomously tracks cursor | 1 | 5 | `120×5` | loop | yes | feet, face | — | 0 | standard | Mischievous stalking | `working-patrol` |
| `intrusive-cursor-pounce` | Eligible autonomous cursor play | 1 | 6 | `80,80,90,100,140,260` | once | yes | feet, face, interaction | voice-bark@2 | 5 | extended | Playful pounce with isolated hit target | `working-patrol` |
| `intrusive-loiter` | Sits at an approved or intrusive perch | 1 | 4 | `300×4` | loop | yes | feet, face | — | 0 | standard | Deliberately in the way, not a loading state | `seated-idle` |
| `intrusive-demand-attention` | Configured attention request | 1 | 5 | `130,130,160,220,360` | once | yes | feet, face, effect | voice-bark@1 | 4 | extended | Flirty/playful insistence, nonsexual | `happy-reaction` |
| `intrusive-zoomies` | Rare high-energy excursion | 1 | 7 | `80×7` | loop | yes | feet, face, effect | rare-idle@0 | 0 | extended | Chaotic but never activates controls | `twerking-reaction` |

## `parsec-effects` — 5 clips, 17 frames

| ID | Trigger / storyboard | Dirs | Frames | Timing ms | Mode | I | Required anchors | Sound | RM | Occupancy | Required read | Fallback |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| `effect-hearts` | Affection or delighted pat overlay | 1 | 3 | `140,180,300` | once | yes | effect | — | 2 | effect | Low-density hearts, no flashing | `happy-reaction` |
| `effect-station-alert` | Warning/error emphasis | 1 | 3 | `120,180,360` | once | yes | effect | radio-alert@0 | 2 | effect | SS13 alert read distinct without color | `seated-idle` |
| `effect-scent-trail` | Search/sniff feedback | 1 | 4 | `160×4` | loop | yes | effect | — | 0 | effect | Subtle scent marks, low visual noise | `working-patrol` |
| `effect-radio-ping` | New compact-log line | 1 | 3 | `120,160,320` | once | yes | effect | radio-alert@0 | 2 | effect | Radio cue, never resembles a work control | `seated-idle` |
| `effect-dust-landing` | Toss landing or energetic stop | 1 | 4 | `80,100,140,260` | once | yes | feet, effect | toy-handling@0 | 3 | effect | Small grounded puff with no screen shake | `working-patrol` |

## Prepared object and audio slots

The manifest registers 11 accepted SS13 object slots: dog bed; open, closed, locked, and occupied cage; tennis
ball; hairbrush; toy mouse; carp plush; toolbox; and the uncolored cable-coil state used as a station tug loop.
Accessible text/CSS remains only as an emergency fallback if an object sheet cannot load.

Eight audio slots are accepted: `voice-bark`, `voice-growl`, `toy-squeak`, `toy-brush`, `toy-whistle`,
`toy-handling`, `radio-alert`, and `rare-idle`. All are exact-copy OGG files with registered source/output hashes,
authored volume, cooldown, runtime channel, and frame-relative cue timing in
[`parsec-asset-register.md`](../parsec-asset-register.md).

## Production review record

Each row receives four independent statuses in the asset register: native `1×`, `4×` nearest-neighbor,
authored motion, and reduced motion. A clip can move from `fallback` to `accepted` only when all four pass.
A failed review returns the slot to its named fallback. `candidate`, `produced`, and `unreviewed` are not
completion states.

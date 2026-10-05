# Parsec Companion, Radio Log, and Activity History Design

Status: approved on 2026-08-24; implementation pending

This design supersedes the balloon-presentation and session-only history portions of
[`parsec-feedback-design.md`](parsec-feedback-design.md). It preserves that design's typed feedback
coordinator, event ownership, voice policy, search/fetch lifecycle reporting, and page-owned exact
diagnostics.

## Product intent

Parsec is both the Solid SPA's central character-facing feedback authority and an optional lightweight
companion. She should make long writing, research, and maintenance sessions feel alive without turning
the application into a care obligation. There is no hunger, health, neglect, currency, experience bar,
or punishment loop.

The default experience is consent-based and restrained:

- Parsec lives in an expandable habitat in the persistent sidebar.
- Her habitat expands over the sidebar without reflowing the active tool page.
- She does not leave the habitat until the user directly interacts with her and answers a one-time
  invitation.
- The default roaming mode is edge-biased and nonblocking.
- Cursor watching is passive until the user initiates play.
- Idle chatter is Rare by default.
- Audio is enabled by default after the browser permits playback.
- Companion state and history are local to this browser profile.

The explicitly configurable Intrusive mode may let Parsec cross work areas, loiter near the cursor,
sit over controls, demand attention, and initiate more play. Even in that mode she never activates a
control, changes selected context, edits a record, starts work, or obscures a serious warning with a
joke.

## Approved presentation

The selected habitat is the expandable layout:

1. A comfortable default playfield in the existing sidebar module.
2. A compact row of eight primary controls immediately below it.
3. A compact SS13-radio-style live log below the controls.
4. A temporary expanded playfield that overlays the sidebar rather than changing page geometry.

Anchored speech balloons are removed. Parsec's animation is the immediate visual response and the
radio log is the durable textual response. Errors may briefly expand the log and play an enabled alert
sound, but they do not cover the work page.

The eight primary actions are Pat, Ball, Tug, Brush, Treat, Whistle, Bed, and Cage. Scruff-grabbing is
a direct pointer interaction rather than a toolbar slot. Native-size pixel icons use accessible names
and focus/hover descriptions. An overflow surface holds settings and station-flavored variants.

## Responsibility boundaries

### Existing Parsec coordinator

`ParsecCoordinator` remains the only character-facing application-feedback authority. Feature owners
continue to execute their own requests and retain exact inline status. They emit typed lifecycle events;
the coordinator owns priority, delay, deduplication, reviewed voice, log delivery, and history recording.

The coordinator does not execute searches, fetches, saves, jobs, navigation, or mutations. It does not
become a second API client or global domain store.

### Companion engine

`CompanionEngine` is a pure deterministic state machine for habitat behavior, roaming, toys, cursor
attention, familiarity, handling, furniture, and animation selection. It consumes typed intents from
direct interactions, timers, route context, visibility, settings, and Parsec feedback. It owns no DOM,
storage, sound, or feature APIs.

### Renderer

`ParsecRenderer` owns DOM rendering only. The persistent `AppShell` mounts exactly one instance. The
habitat and roaming layer display the same stateful Parsec; excursions move her between rendering
anchors instead of creating another mascot.

The full-page roaming root is pointer-transparent. Only Parsec, active toys, furniture, and explicit
handles receive pointer events. Intrusive mode may visually overlap content but cannot send clicks to
underlying controls while Parsec is being directly manipulated.

### Profile, journal, audio, and tabs

- `CompanionProfileStore` persists versioned settings, consent, soft familiarity, unlocks, preferences,
  and normalized furniture positions.
- `ActivityJournal` stores the Parsec transcript and structured application events in IndexedDB.
- `CompanionAudioBus` owns browser audio unlocking, manifests, master/category volume, concurrency,
  cooldowns, and visibility suppression.
- `CompanionTabCoordinator` elects one active tab for autonomous motion and audio using the Web Locks
  API when available and `BroadcastChannel` plus a renewable lease as the fallback.
- `ParsecAssetRegistry` validates versioned animation, toy, furniture, effect, audio, anchor, fallback,
  and provenance manifests.

## Layered behavior model

Behavior is composed rather than represented by one ever-growing animation enum:

- Activity: resting, observing, responding, playing, roaming, held, landing, returning, or sleeping.
- Mood: calm, curious, excited, pouty, anxious, frustrated, proud, or affectionate.
- Attention: habitat object, cursor, toy, application work, or none.
- Feedback duty: idle, working, success, warning, or error.
- Location: habitat, app-edge perch, free-roaming position, bed, cage, or transition.
- Familiarity: a small number of internal behavioral bands with no visible score.

Critical feedback interrupts autonomous behavior, but does not jerk Parsec out of the pointer while she
is held. The radio log updates immediately and she performs the applicable reaction after release.
User-initiated play outranks idle chatter. Serious errors and destructive or security-sensitive warnings
suppress jokes.

Autonomous selection uses weighted eligible behaviors, repetition avoidance, and per-behavior cooldowns.
Eligibility considers consent, route, recent behavior, familiarity, focus, typing, visibility, active
work, furniture state, and roaming settings.

## Consent, roaming, and cursor behavior

Direct interaction with an unconfigured Parsec presents one in-character invitation:

- Allow occasional excursions.
- Ask each time.
- Stay in the habitat.

Until one is chosen she remains confined. Settings can change this choice later.

Default edge-biased roaming uses shell chrome, margins, and safe perches. Parsec crosses the working
canvas only for an explicit cursor or toy interaction and avoids visible interactive controls and text.
Intrusive mode may disregard those visual avoidance rules while retaining the no-activation boundary.

In ordinary mode Parsec may watch the cursor, blink, turn her head, or track it with her eyes. She only
chases, pounces, or physically interacts after direct play begins. Intrusive mode may initiate cursor
play according to its frequency and focus settings.

## Handling and personality

Parsec has a dedicated scruff grab zone. Pointer capture keeps her held during fast movement. A held
animation may be calm, playful, pouty, or squirming depending on mood, familiarity, repetition, movement
speed, and whether she initiated play.

Grab physics is independently configurable:

- Carry only.
- Gentle momentum, the default.
- Full tossing and bouncy landings.

Handling-reaction intensity is separately configurable as subdued, expressive (default), or dramatic.
Normal mode defaults to gentle momentum; Intrusive mode recommends full tossing but does not force it.

Parsec's default personality is warm, playful, affectionate, and lightly flirtatious. This means winks,
nose licks, attention seeking, smug tail wags, mock jealousy, and teasing SS13 banter. It is never
sexualized. Her tone is independently configurable as warm, playful-flirtatious, or impish.

## Toys and primary interactions

All core interactions are available immediately. Familiarity unlocks alternate skins, autonomous uses,
rarer reactions, preferences, and station-flavored surprises rather than withholding basic controls.

- Pat: petting, nose boops, chin scratches, and affectionate reactions.
- Ball: drag, throw, chase, retrieve, carry, drop, and occasional playful refusal.
- Tug: pointer-driven tension, pulling, release, victory, and tumble behavior.
- Brush: directional strokes with contented, impatient, or huffy reactions.
- Treat: place or offer directly; no hunger state, need, debt, or penalty.
- Whistle: recall Parsec, cancel an excursion, or invite her out when allowed.
- Bed: command her to lie down at a movable hangout or temporary timeout spot.
- Cage: command her inside and close the door; the action then becomes Release.

Dropping Parsec into an open cage leaves it open. The user closes it through the latch. A closed cage is
hard confinement: Parsec never self-releases, but she may react, sleep, speak, play with reachable items,
and perform application-feedback reactions. The bed never hard-locks her; its current mode decides when
she may get up.

The bed and cage are draggable outside the habitat into approved app-edge areas. Their one global pair
of normalized positions persists across routes and is clamped after resizing. Settings provide one
recovery action to return both home. Meridian-Rift already provides useful source states including
`dogbed` in `icons/obj/bed.dmi` and open, closed, locked, and occupied carrier states in
`icons/obj/pet_carrier.dmi`.

## Radio log and durable activity history

The compact live log shows three to five recent lines by default. It is scrollable, timestamped, uses
SS13-radio-inspired channel styling, shows unread state, and expands briefly for actionable errors.
Display modes are configurable: compact live log, collapsed indicator, or expanded transcript.

Each Parsec transcript entry records her exact reviewed line, timestamp, severity, source tool, reaction,
and the journal event ID. The connected structured activity entry records event type, lifecycle phase,
tool, route, context identifier, duration, result count, outcome, and allowed technical detail.

The journal never stores complete lore document bodies. Secret-shaped values are redacted before
persistence. The local activity history is useful operational evidence, not a tamper-proof security
audit trail.

Retention choices are 7 days, 30 days, 90 days (default), one year, or until manually cleared. The
Parsec page supports filters, JSON/CSV export, clear history, storage status, and recovery from a failed
migration. Companion-profile export/import is separate from activity-history export; importing a profile
does not fabricate historical activity.

## Profile and settings

The local profile contains settings, consent, furnishings, familiarity bands, interaction preferences,
discovered reactions, toy tendencies, and cosmetic unlocks. It does not contain care debt, hunger,
health, currency, lore bodies, or punishment metrics.

Settings are grouped into Presence, Personality, Interaction, Feedback, Audio, Accessibility, and Data.
Important defaults are:

- Idle chatter: Rare.
- Chat presentation: compact live log.
- Roaming: edge-biased after explicit consent.
- Cursor behavior: passive observation until play begins.
- Tone: playful-flirtatious within the nonsexual boundary.
- Handling reactions: expressive.
- Grab physics: gentle momentum.
- Audio: enabled after browser unlock.
- Master volume: 30%.
- Rare-idle channel: 20% relative to master.
- Activity retention: 90 days.

## Audio

Howler core supplies a small, consistent Web Audio/HTML audio boundary with grouped volume, overlapping
effects, format fallbacks, and audio sprites. Audio activates after the first browser-permitted user
interaction and persists its enabled state locally.

Channels are voice/canine reactions, toys/handling, radio/interface, and rare idle/environmental sounds.
Only the elected active tab may play. Hidden documents, inactive windows, typing, reduced-distraction
mode, and serious errors suppress idle audio. Intrusive mode increases behavior eligibility, never volume,
and cannot bypass mute or cooldowns.

Relevant research: [Howler](https://howlerjs.com/),
[browser autoplay behavior](https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay), and
[Page Visibility](https://developer.mozilla.org/en-US/docs/Web/API/Document/visibilitychange_event).

## Rendering and asset architecture

The selected runtime extends the existing DOM/CSS sprite engine. This preserves isolated pointer hit
targets, click-through behavior, straightforward accessibility, the existing Solid shell, and the current
fallback sheet. A full-canvas engine would complicate reliable interaction with the productivity UI.

The design adapts useful patterns from [oneko.js](https://github.com/adryd325/oneko.js) (directional
movement and contextual idle states), [desksprite](https://github.com/welltilln/desksprite) (home/roam,
dragging, throwing, return behavior, tab pausing, and data-driven skins), and
[deskopilot](https://github.com/Louis-7/deskopilot) (pure event/state separation and art-only packages).
PixiJS remains a future escalation path for a materially larger multi-character or particle-heavy game.

The new art uses versioned JSON manifests and multiple packed atlases. Frames share a `96 x 96` logical
canvas and may use the complete space when the action requires it. Ordinary poses preserve Parsec's
recognizable proportions, fur palette, outline, anatomical left neon-pink eye, anatomical right Supermatter-yellow eye, and native-size legibility. Each frame records
foot, scruff, mouth, toy, effect, and interaction anchors as applicable.

Planned atlases:

- `parsec-core`: eight-direction movement and rich idle life.
- `parsec-feedback`: search, fetch, working, success, warning, confusion, failure, and recovery.
- `parsec-touch`: pats, licks, scruff handling, drops, throws, landings, and recovery.
- `parsec-toys`: ball, tug, brush, treat, and whistle sequences.
- `parsec-habitat`: bed and cage transitions and states.
- `parsec-intrusive`: cursor stalking, demands, loitering, and station-flavored autonomous behavior.
- `parsec-effects`: hearts, alert marks, scent, dust, sleep, radio, toy, and landing effects.

The production target is approximately 55 to 65 named clips and 220 to 300 unique frames after mirroring
and intentional reuse. Each clip defines timing, loop mode, interruptibility, reduced-motion frame, anchors,
allowed moods, sound cues, and fallback.

Furniture and toys use a separate SS13-native atlas so 32-pixel DMI source states retain their palette and
provenance. Candidate sources already present in Meridian-Rift include tennis balls, hairbrush art and
sounds, a dog bed, occupied pet carriers, carp plushes, toy mice, whistles, squeaks, barks, growls, dog
sounds, and toolbox handling sounds.

Every extracted, adapted, generated, rejected, or accepted asset records source URL or repository, exact
path and DMI state, source revision, author where known, license, adaptation, and runtime mapping in
[`references/parsec-asset-register.md`](../parsec-asset-register.md). Meridian-Rift's README identifies its
icons and sounds as CC BY-SA 3.0 unless otherwise indicated; derived assets retain compatible attribution
and share-alike terms.

## Accessibility, performance, and failure isolation

- Authored animation uses its declared cadence; movement and physics are frame-independent.
- The update loop sleeps when Parsec and toys are stationary and stops while the document is hidden.
- Motion uses transforms and does not reflow work pages.
- Reduced motion disables autonomous roaming, throwing, bouncing, zoomies, and large transitions while
  retaining static direct-interaction feedback.
- Every tool and command has a keyboard equivalent, visible focus, and an accessible name.
- Ordinary log updates are polite live-region messages; actionable errors are assertive. Superseded and
  idle events are not repeatedly announced.
- Manifest validation fails development gates. Missing runtime assets use declared fallbacks and text labels.
- Corrupt profile data is quarantined and recoverable without touching lore or repository data.
- A companion failure falls back to the current static sprite and plain activity log. Search, editing,
  navigation, and other shared-shell behavior remain usable.

## Creative sprint gate

Normal-effort implementation stops before creative production. Entry to the Max-effort sprint requires:

- Approved and frozen architecture.
- Implemented manifest contracts, fallback renderer, interactions, and integration hooks.
- Exact clip roster, frame counts, anchors, timing, and storyboards.
- Complete DMI/audio inventory and provenance decisions.
- Contact-sheet and DMI-extraction tooling.
- Asset acceptance tests, reduced-motion representatives, and review checklist.
- No unresolved product or architecture decision.

At that point the agent must stop and explicitly ask Zoe to turn effort up to Max. Max effort is used for
production work, not design exploration.

The sprint exits only when every required asset is accepted, registered, integrated, reviewed at native
and enlarged nearest-neighbor scale, exercised in motion and reduced-motion modes, and passes the prepared
gates. A required rejected asset exits only through Zoe's explicit approval to retain its fallback or mark
human help required. After the gate is closed, effort can return to normal for final verification and polish.

## Verification requirements

- Pure tests for state transitions, scheduling, priorities, tab leadership, profile migrations, retention,
  redaction, manifest validation, physics, collision, and familiarity.
- Component tests for the radio log, eight controls, scruff interactions, bed/cage commands, furniture
  recovery, settings, accessibility, reduced motion, and fallback rendering.
- Integration tests for search, lore-selection fetches, mutations, background work, connection changes,
  activity persistence, multi-tab behavior, and profile import/export.
- Visual checks at supported desktop and narrow widths, native pixel scale, and enlarged nearest-neighbor
  scale.
- Audio checks for unlock, mute, category volume, cooldown, hidden-tab suppression, and active-tab ownership.
- Frontend generation, tests, typecheck, production build, repository Python/documentation gates, diff
  hygiene, and the real Windows launcher/browser path.

All work remains uncommitted unless Zoe explicitly authorizes commits. No subagents may be dispatched
without her explicit approval.

# Parsec Feedback, Search, and Idle-Behavior Design

Status: feedback routing implemented; presentation and history sections superseded on 2026-08-24

The anchored-balloon and session-history decisions in this document are historical. The approved
replacement is the compact SS13-style radio log plus browser-local IndexedDB activity journal in
[`parsec-companion-design.md`](parsec-companion-design.md). The typed coordinator, event ownership,
priority, delayed feedback, deduplication, reviewed voice, search/fetch reporting, and page-owned exact
diagnostics in this document remain normative.

## Purpose

Parsec is the shared Solid SPA's character-facing authority for user feedback. She explains searches,
fetches, saves, background work, connection changes, validation failures, and other meaningful activity
without replacing the durable technical status owned by each tool page.

The design preserves the existing application shell, tool registry, selected context, typed API client,
live-state owner, and page-local interaction state. Parsec coordinates presentation; she does not become a
second networking layer or take domain logic away from the feature that owns it.

## Product requirements

- Use the existing Parsec art assets and pixel-art presentation.
- Present messages in Parsec's compact station-radio log; do not restore the superseded balloon overlay.
- Keep her voice playful, warm, canine-coded, and occasionally Space Station 13-coded.
- Use asterisk-delimited physical actions and emotive interjections without letter replacement.
- Route meaningful fetch, search, loading, success, error, and background-job feedback through Parsec.
- Keep exact errors, durable statuses, logs, validation details, and accessible regions at their owning page.
- Provide context-aware idle chatter as a user setting. Default to `rare`.
- Preserve reduced-motion support and the shared SPA component contracts.
- Keep an explicit art and animation register so humans can extend or replace artwork later.

## Approaches considered

### Coordinator with typed events — selected

Feature owners continue to execute searches, fetches, mutations, and jobs. They report typed lifecycle
events to a Parsec coordinator. The coordinator applies interruption priority, deduplication, voice,
animation, balloon timing, history, and accessibility policy.

This is the selected approach because it makes Parsec authoritative over presentation without coupling the
mascot component to every API contract.

### Parsec-owned I/O broker — rejected

All searches and fetches could be executed through a Parsec service. That is a literal interpretation of
central authority, but it would make unrelated tool behavior depend on mascot infrastructure, duplicate the
typed API client, and create a frontend god object.

### Decorated notification strings — rejected

The current `announce` helpers could merely add character copy. This is small, but it cannot represent
started, delayed, empty, superseded, cancelled, or recovered work and would leave search and fetch feedback
fragmented across components.

## Responsibility boundary

Feature code owns:

- The request and its cancellation or supersession.
- Domain-specific state and durable inline output.
- Exact errors, validation details, result counts, logs, and retry controls.
- Deciding which lifecycle event actually occurred.

The Parsec coordinator owns:

- Whether an event warrants a visible balloon.
- Voice selection and contextual phrasing.
- Balloon priority, replacement, queueing, deduplication, and dwell time.
- Parsec animation and reaction selection.
- Announcement history and the character-facing accessible announcement.
- Idle chatter eligibility, frequency, context, and suppression.

The `Parsec` Solid component owns rendering only. It consumes coordinator state and renders the sprite,
anchored balloon, and interaction affordances. It must not call APIs or inspect tool-specific stores.

## Event model

The coordinator accepts a discriminated `ParsecEvent` union rather than arbitrary display strings. Each
event includes a stable type, source tool, phase, timestamp, and optional context or technical detail.

Initial event families:

| Family | Phases or variants | Examples |
| --- | --- | --- |
| Search | started, completed, empty, failed, superseded | Global search and catalog filtering |
| Fetch | started, delayed, completed, failed, cancelled | Loading a lore selection or refreshing data |
| Mutation | completed, failed | Save, remove, review, assignment, export |
| Job | started, progress, completed, failed | Catalog generation and content-graph scans |
| Connection | connected, disconnected, polling, recovered | Live WebSocket and polling fallback |
| Validation | warning, blocked, failed | Unsafe paths, stale stages, invalid writer input |
| Navigation | context-changed | Active page and shared selected context |
| Interaction | pat, repeated-pat | Happy and easter-egg reactions |
| Idle | contextual | Chatter selected by the idle policy, never emitted by pages |

Events may carry `summary`, `technicalDetail`, `resultCount`, `query`, `selectionLabel`, `jobLabel`,
`dedupeKey`, or `replacesKey` where appropriate. Values are rendered as text, never HTML. Character copy
must not obscure or mutate `technicalDetail`.

Existing `announce`, `announceSuccess`, and `announceError` calls remain compatibility wrappers during the
migration. They report generic typed events through the coordinator. Feature surfaces are then migrated to
specific events as their tests are updated.

## Priority and interruption policy

The coordinator displays at most one balloon and keeps a small bounded queue. Repeated events with the same
dedupe key replace or coalesce instead of stacking.

Priority order:

1. Error, dangerous validation, or disconnected state.
2. Blocked work or action-required warning.
3. Successful user-initiated mutation or completed background job.
4. Delayed fetch, active search, or progress update.
5. Contextual idle chatter.

Higher-priority events may replace lower-priority balloons. Idle chatter never queues and disappears as
soon as real work begins. Search keystrokes do not create one balloon per query; a new query supersedes the
previous search event. Very short fetches do not flash a loading balloon. A delayed threshold provides
Parsec feedback only when the load lasts long enough to be perceptible.

Errors receive the longest dwell time, progress messages the shortest, and ordinary messages an adaptive
middle duration based on length. The announcement history retains the event even after its balloon closes.

## Anchored balloon (superseded)

This section records the earlier selection only. The radio-log presentation in
[`parsec-companion-design.md`](parsec-companion-design.md) now controls implementation.

The selected layout is the anchored balloon.

- Parsec's stage grows upward when a balloon is present; it does not overlap or reflow the application page.
- The balloon remains inside the sidebar rail and above the sprite.
- A balloon tail points at Parsec's current horizontal position and is clamped away from rounded corners.
- Parsec pauses horizontal patrol while speaking. Her selected animation may continue in place.
- Closing the balloon resumes the state implied by active work.
- The sprite remains visible at all times.
- The balloon targets one short physical action plus one useful sentence, normally no more than three lines.
- Long technical details stay inline and in the announcement log.
- Success, warning, and error styling uses the app's existing semantic tokens. Meaning never depends on color
  alone.
- Reduced-motion mode selects a representative static frame, disables patrol and balloon motion, and keeps
  all text and timing behavior intact.

The current `432 × 204` transparent sheet remains the runtime source for existing states. It is divided into
`72 × 51` cells. New artwork must follow the same cell dimensions or explicitly version the engine contract.

## Voice policy

Parsec's voice is assembled from reviewed, event-specific lines rather than transforming arbitrary text.
The policy may add:

- Asterisk-delimited physical actions such as `*sniffs.*`, `*wuffs softly.*`, or
  `*tilts her head in confusion.*`.
- Canine terms such as sniffing, digging, barking, tail-wagging, and growling at code.
- Light SS13 references such as station notices, the quartermaster, atmos, engineering, or a suspicious
  toolbox when they fit the event.
- Warmth, playful exaggeration, and emotive punctuation in moderation.

The policy must not:

- Replace `r` or `l` with `w`, distort technical names, or make text harder to understand.
- Joke over destructive, security-sensitive, or data-loss warnings.
- Invent successful outcomes, hide uncertainty, or paraphrase away required action.
- Include unescaped user or repository text as markup.
- Repeat an idle line until the other eligible lines for that context have cycled.

Examples:

| Event | Balloon copy |
| --- | --- |
| Search started | `*sniffs.* Digging through the selected context…` |
| Search empty | `*tilts her head in confusion.* No matching records in this context.` |
| Fetch delayed | `*snuffles around the catalog.* Still fetching that entry!` |
| Save completed | `*wags her tail excitedly!* Override saved and regenerated.` |
| Tool failed | `*growls angrily at the code.* That job failed; the exact error is below.` |
| Connection lost | `*whines anxiously…* I lost the live station link and switched to polling.` |

## Search and fetch behavior

Global search remains tied to the shared selected context. It reports debounced lifecycle events to Parsec
and exposes durable results and errors in the search surface.

- Typing starts or supersedes a search event only after the existing debounce.
- Parsec adopts a search/working state immediately but only speaks when the request crosses the delayed
  threshold, returns no results, fails, or reaches a meaningful user-triggered completion.
- Result counts can appear in a completion balloon when the user explicitly submitted a search. Routine
  incremental typing updates the result list without repeated success balloons.
- Selecting a result updates shared context through the existing store and may produce a short confirmation
  only when the context change is otherwise ambiguous.

Other fetches use the same lifecycle. Page-local loading indicators remain available for regions where
Parsec is outside the viewport, the shell is unavailable, or progress needs a persistent spatial anchor.
They do not replace Parsec's character-facing explanation.

## Idle chatter

The `/parsec` page gains an idle-chatter setting stored locally alongside the motion preference:

| Setting | Eligible quiet interval |
| --- | --- |
| Off | Never |
| Rare | Randomized 8–12 minutes; default |
| Occasional | Randomized 4–7 minutes |
| Frequent | Randomized 2–4 minutes |

Idle chatter is eligible only when:

- The document is visible.
- No balloon, error, blocked action, active request, or background job needs attention.
- The user is not typing in an input, textarea, or editable surface.
- The applicable cooldown has elapsed.
- The active route or selected context supplies a reviewed contextual line.

Context sources are route, selected shared context, active job family, connection mode, and the most recent
meaningful event category. Idle lines never quote lore content or repository text without an explicit event
template. A context change resets the timer so Parsec does not interrupt the user's first interaction with a
page.

## Settings and history

The existing `/parsec` route remains the settings, preview, attribution, and durable activity-history surface.
It gains:

- Idle chatter: Off, Rare, Occasional, Frequent.
- Preview controls for each event family and animation state.
- A visible link to the Parsec asset register and canonical sprite sheet.
- Browser-local history that separates Parsec's character-facing line from retained technical detail when
  both exist, with filters, retention, JSON/CSV export, and explicit clear confirmation.

Motion and idle preferences remain browser-local. They are not writer records and do not enter pull
requests.

## Accessibility

- The balloon is a polite live region for ordinary feedback and an assertive alert only for errors requiring
  immediate attention.
- Replaced or superseded search events are not announced to assistive technology.
- Parsec remains keyboard-pattable with a visible focus indication and an explicit label.
- Physical-action text is meaningful without the animation.
- Reduced motion prevents patrol and transition animation without suppressing feedback.
- Technical errors remain available as selectable text in their owning surface and history.

## Art and animation workflow

The canonical inventory and backlog live in
[`references/parsec-asset-register.md`](../parsec-asset-register.md). Every runtime Parsec bitmap, derived
sheet, requested animation, custom icon, license, and source link must be recorded there.

Best-effort animation passes follow this workflow:

1. Preserve the current sheet and frame mappings as the style and compatibility reference.
2. Create candidate action frames separately at `72 × 51` with transparency and nearest-neighbor scaling.
3. Compare candidates against the existing silhouette, palette, outline, eye color, proportions, and motion
   cadence.
4. Integrate only candidates that remain legible at native size and loop without visible jumps.
5. Record accepted frames and coordinates in the asset register and engine tests.
6. Leave an unaccepted item marked `human help requested` with the candidate problem and intended event.

Missing custom art never blocks functional feedback. Each requested state has an existing fallback. Adding
new art may extend the sheet or add a separately versioned action sheet, but it must not move existing frame
coordinates silently.

## Verification

Implementation requires:

- Pure tests for priority, queue bounds, deduplication, delayed loading, voice selection, idle eligibility,
  frequency persistence, and frame mapping.
- Component tests for anchored-tail positioning inputs, patrol pause/resume, accessible live regions,
  keyboard patting, reduced motion, and long-message containment.
- Integration tests for global search, lore-selection fetches, save success, errors, live disconnection, and
  background jobs.
- Visual checks at the shell's supported desktop widths and narrow fallback width.
- Pixel-art review at native scale and enlarged nearest-neighbor scale for every accepted frame.
- The normal frontend typecheck, test, build, API generation, Python gates, documentation checks, and real
  launcher/browser path.

## Rollout

1. Add coordinator types, policy tests, settings persistence, and compatibility wrappers.
2. Render the anchored balloon through coordinator state using the existing sheet.
3. Migrate global search and lore-selection loading first.
4. Migrate mutations, background jobs, live connection feedback, and remaining announcement calls.
5. Add context-aware idle chatter and `/parsec` preview controls.
6. Make best-effort action-animation passes and integrate only accepted artwork.
7. Update maintainer and writer documentation and complete the integrated launcher verification.

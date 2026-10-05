# Parsec Feedback, Search, and Idle Behavior Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan inline, task by task. Do not dispatch subagents without Zoe's explicit approval. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Parsec the shared SPA's typed, playful feedback coordinator with an anchored speech balloon, context-aware rare-by-default idle chatter, search/fetch lifecycle reporting, durable diagnostics, and a maintainable art pipeline.

**Architecture:** Feature owners keep their API calls and durable inline state, then emit discriminated lifecycle events to a Parsec coordinator. Pure policy modules select priority, copy, animation, dwell time, and idle eligibility; the coordinator publishes one active feedback item through the existing shared app store while retaining a bounded queue and announcement history. The `Parsec` component remains render-only and uses the existing sprite engine and canonical sheet.

**Tech Stack:** SolidJS 1.9, TypeScript 5.7, Vitest 3, CSS Modules, Vite 6, browser `localStorage`, the existing typed API client and shared Solid store, transparent pixel-art PNG sheets.

**Spec:** [`references/architecture/parsec-feedback-design.md`](parsec-feedback-design.md)

## Global Constraints

- Preserve the shared `AppShell`, tool registry, selected context, typed API client, live owner, and shared app-store contracts.
- Keep exact errors, durable statuses, logs, validation details, and accessible regions at their owning page.
- Parsec owns character-facing routing and presentation; she does not execute feature APIs.
- Use asterisk actions, canine behavior, and occasional SS13 references without `r`/`l` letter replacement.
- Idle chatter settings are `off`, `rare`, `occasional`, and `frequent`; default is `rare` with an 8–12 minute randomized quiet interval.
- Do not add a frontend icon dependency solely for Parsec.
- Preserve all existing sprite coordinates. New action art uses `72 × 51` transparent cells or a separately versioned sheet.
- Add or update behavioral tests before changing behavior.
- Keep changes in the current working tree. Do not commit, push, reset, checkout, merge, or dispatch agents.

---

## File structure

### New files

- `webapp/frontend/src/lib/parsec/types.ts` — typed event, feedback, animation, priority, and settings contracts.
- `webapp/frontend/src/lib/parsec/voice.ts` — pure reviewed copy selection with no arbitrary text transformation.
- `webapp/frontend/src/lib/parsec/voice.test.ts` — copy, detail preservation, and forbidden-letter-replacement coverage.
- `webapp/frontend/src/lib/parsec/policy.ts` — pure priority, dwell, deduplication, delay, and idle-eligibility rules.
- `webapp/frontend/src/lib/parsec/policy.test.ts` — deterministic policy tests.
- `webapp/frontend/src/lib/parsec/coordinator.ts` — bounded runtime queue, timers, compatibility reporting, and singleton API.
- `webapp/frontend/src/lib/parsec/coordinator.test.ts` — fake-timer queue and interruption tests.
- `webapp/frontend/src/lib/parsec/settings.ts` — browser-local chatter preference persistence.
- `webapp/frontend/src/lib/parsec/settings.test.ts` — defaults, round trips, and storage-failure tests.
- `webapp/frontend/src/lib/parsec/idle.ts` — start/stop idle scheduler using current app context and coordinator.
- `webapp/frontend/src/lib/parsec/idle.test.ts` — visibility, focus, route, active work, and cooldown tests.

### Modified files

- `webapp/frontend/src/store/appStore.ts` and `.test.ts` — active Parsec feedback, active route, and compatible announcement detail.
- `webapp/frontend/src/lib/notify.ts` — compatibility wrappers routed through the coordinator.
- `webapp/frontend/src/components/Parsec.tsx`, `.module.css`, and `.test.tsx` — anchored balloon and render-only sprite behavior.
- `webapp/frontend/src/lib/parsecEngine.ts` and `.test.ts` — speaking/patrol helpers and accepted action-sheet mappings.
- `webapp/frontend/src/components/GlobalSearch.tsx` and accessibility tests — typed search lifecycle events.
- `webapp/frontend/src/components/LoadingIndicator.tsx` — delayed fetch lifecycle reporting.
- `webapp/frontend/src/tools/loreEditor/LoreEditorPage.tsx` and tests — selection-specific fetch keys and durable errors.
- `webapp/frontend/src/lib/live.ts` plus a new focused `live.test.ts` — connection loss and recovery events.
- `webapp/frontend/src/components/AppShell.tsx` — active route context only.
- `webapp/frontend/src/App.tsx` — start and dispose the idle scheduler.
- `webapp/frontend/src/tools/parsec/ParsecPage.tsx`, `.module.css`, and tests — chatter setting, previews, history detail, attribution, and asset links.
- Existing mutation callers under `tools/fileManagement`, `tools/loreEditor`, `tools/contentGraph`, `components/SharedReferences.tsx`, and `components/OpenFileActions.tsx` — migrate generic calls to typed event helpers without removing inline state.
- `references/maintainer-guide.md` and `references/writer-guide.md` — coordinator contract and user settings.
- `references/parsec-asset-register.md` — candidate/accepted animation results and coordinates.
- `webapp/frontend/src/assets/parsec-actions.png` — create only if at least one candidate passes native-size review.

---

### Task 1: Define Parsec events, voice, and pure policy

**Files:**
- Create: `webapp/frontend/src/lib/parsec/types.ts`
- Create: `webapp/frontend/src/lib/parsec/voice.ts`
- Create: `webapp/frontend/src/lib/parsec/voice.test.ts`
- Create: `webapp/frontend/src/lib/parsec/policy.ts`
- Create: `webapp/frontend/src/lib/parsec/policy.test.ts`

**Interfaces:**
- Produces: `ParsecEvent`, `ParsecFeedback`, `ParsecAnimation`, `ParsecPriority`, `IdleChatterPreference`, `voiceForEvent(event)`, `priorityForEvent(event)`, `dwellMsForFeedback(feedback)`, `shouldDelayFeedback(event)`, and `canEmitIdle(context)`.
- Consumes: no app store, DOM, timers, or API client; these modules remain pure.

- [x] **Step 1: Write failing voice and policy tests**

```ts
import { describe, expect, it } from 'vitest';
import { voiceForEvent } from './voice';

describe('Parsec voice', () => {
	it('uses a canine action without changing technical identifiers', () => {
		const feedback = voiceForEvent({
			type: 'fetch', phase: 'failed', tool: 'lore-editor',
			summary: 'Could not load /obj/item/radio.',
			technicalDetail: 'HTTP 500: /obj/item/radio',
			dedupeKey: 'lore:/obj/item/radio',
		});
		expect(feedback.text).toContain('*growls');
		expect(feedback.technicalDetail).toBe('HTTP 500: /obj/item/radio');
		expect(feedback.text).not.toContain('/obj/item/wadio');
	});

	it('uses the approved empty-search reaction', () => {
		const feedback = voiceForEvent({
			type: 'search', phase: 'empty', tool: 'global-search',
			query: 'radio', resultCount: 0, dedupeKey: 'global-search',
		});
		expect(feedback.text).toBe('*tilts her head in confusion.* No matching records in this context.');
	});
});
```

```ts
import { describe, expect, it } from 'vitest';
import { priorityForEvent, shouldDelayFeedback } from './policy';

describe('Parsec policy', () => {
	it('orders errors above blocked work, success, progress, and idle', () => {
		expect(priorityForEvent({ type: 'fetch', phase: 'failed', tool: 'lore-editor', summary: 'Failed' }))
			.toBeGreaterThan(priorityForEvent({ type: 'validation', phase: 'blocked', tool: 'file-management', summary: 'Blocked' }));
		expect(priorityForEvent({ type: 'mutation', phase: 'completed', tool: 'lore-editor', summary: 'Saved' }))
			.toBeGreaterThan(priorityForEvent({ type: 'fetch', phase: 'started', tool: 'lore-editor', summary: 'Loading' }));
	});

	it('delays started searches and fetches but not their failures', () => {
		expect(shouldDelayFeedback({ type: 'search', phase: 'started', tool: 'global-search', query: 'radio' })).toBe(true);
		expect(shouldDelayFeedback({ type: 'fetch', phase: 'failed', tool: 'lore-editor', summary: 'Failed' })).toBe(false);
	});
});
```

- [x] **Step 2: Run the focused tests and confirm the missing modules fail**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/voice.test.ts src/lib/parsec/policy.test.ts`

Expected: FAIL because `./voice` and `./policy` do not exist.

- [x] **Step 3: Implement the exact contracts**

Define a discriminated union whose shared fields are:

```ts
export type ParsecEvent =
	| ({ type: 'search'; phase: 'started' | 'completed' | 'empty' | 'failed' | 'superseded'; query: string; resultCount?: number } & EventBase)
	| ({ type: 'fetch'; phase: 'started' | 'delayed' | 'completed' | 'failed' | 'cancelled'; summary: string } & EventBase)
	| ({ type: 'mutation'; phase: 'completed' | 'failed'; summary: string } & EventBase)
	| ({ type: 'job'; phase: 'started' | 'progress' | 'completed' | 'failed'; summary: string } & EventBase)
	| ({ type: 'connection'; phase: 'connected' | 'disconnected' | 'polling' | 'recovered' } & EventBase)
	| ({ type: 'validation'; phase: 'warning' | 'blocked' | 'failed'; summary: string } & EventBase)
	| ({ type: 'navigation'; phase: 'context-changed'; route: string } & EventBase)
	| ({ type: 'interaction'; phase: 'pat' | 'repeated-pat' } & EventBase)
	| ({ type: 'idle'; phase: 'contextual'; route: string } & EventBase)
	| ({ type: 'notice'; phase: 'info' | 'success' | 'error'; summary: string } & EventBase);

export interface EventBase {
	readonly tool: string | null;
	readonly technicalDetail?: string;
	readonly dedupeKey?: string;
	readonly replacesKey?: string;
}

export type ParsecAnimation = 'idle' | 'working' | 'happy' | 'twerking' | 'search' | 'fetch' | 'anxious' | 'confused' | 'growl' | 'pant';
export type ParsecPriority = 10 | 40 | 60 | 80 | 100;

export interface ParsecFeedback {
	readonly id: number;
	readonly text: string;
	readonly kind: 'info' | 'success' | 'warning' | 'error';
	readonly animation: ParsecAnimation;
	readonly priority: ParsecPriority;
	readonly tool: string | null;
	readonly technicalDetail: string | null;
	readonly dedupeKey: string | null;
	readonly at: number;
}
```

Implement `voiceForEvent` with reviewed maps for every family and no generic UwU text transformation. Compatibility summaries may be appended verbatim after the reviewed physical action. Implement exact priorities `100`, `80`, `60`, `40`, and `10`; delay only `search.started` and `fetch.started`; use dwell times of 8 seconds for errors, 6 seconds for blocked warnings, 4–6 seconds for other real feedback based on length, and 4 seconds for idle.

- [x] **Step 4: Run focused tests**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/voice.test.ts src/lib/parsec/policy.test.ts`

Expected: PASS.

- [x] **Step 5: Review checkpoint**

Run: `git diff --check -- webapp/frontend/src/lib/parsec`

Expected: no output. Leave changes uncommitted.

---

### Task 2: Add the coordinator and shared-store publication contract

**Files:**
- Create: `webapp/frontend/src/lib/parsec/coordinator.ts`
- Create: `webapp/frontend/src/lib/parsec/coordinator.test.ts`
- Modify: `webapp/frontend/src/store/appStore.ts`
- Modify: `webapp/frontend/src/store/appStore.test.ts`
- Modify: `webapp/frontend/src/lib/notify.ts`

**Interfaces:**
- Consumes: Task 1 `ParsecEvent`, `ParsecFeedback`, `voiceForEvent`, priority, delay, and dwell functions.
- Produces: `reportParsec(event): number`, `dismissParsec(id): void`, `reactParsec(animation, durationMs?): void`, `createParsecCoordinator(environment)`, `appState.parsecFeedback`, `setParsecFeedback`, and compatibility `announce`, `announceSuccess`, `announceError`.

- [x] **Step 1: Write failing coordinator tests using injected timers**

```ts
it('replaces delayed progress with a higher-priority error and never later resurrects progress', () => {
	const harness = createHarness();
	const coordinator = createParsecCoordinator(harness.environment);
	coordinator.report({ type: 'fetch', phase: 'started', tool: 'lore-editor', summary: 'Loading', dedupeKey: 'entry:radio' });
	harness.advanceBy(200);
	coordinator.report({ type: 'fetch', phase: 'failed', tool: 'lore-editor', summary: 'Load failed', technicalDetail: 'HTTP 500', dedupeKey: 'entry:radio' });
	harness.advanceBy(1000);
	expect(harness.published.at(-1)?.kind).toBe('error');
	expect(harness.published.some((item) => item?.text.includes('Still fetching'))).toBe(false);
});

it('bounds the pending queue and drops idle feedback before real work', () => {
	const harness = createHarness();
	const coordinator = createParsecCoordinator(harness.environment);
	coordinator.report({ type: 'idle', phase: 'contextual', route: '/lore-editor', tool: 'parsec' });
	for (let index = 0; index < 8; index += 1) {
		coordinator.report({ type: 'mutation', phase: 'completed', tool: 'lore-editor', summary: `Saved ${index}`, dedupeKey: `save:${index}` });
	}
	expect(coordinator.pendingCount()).toBeLessThanOrEqual(5);
	expect(coordinator.snapshot().some((item) => item.priority === 10)).toBe(false);
});
```

- [x] **Step 2: Run the focused tests and confirm failure**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/coordinator.test.ts src/store/appStore.test.ts`

Expected: FAIL because the coordinator and feedback store fields are missing.

- [x] **Step 3: Extend the shared store without adding a second global state path**

Add `parsecFeedback: ParsecFeedback | null` and `activeRoute: string` to `AppState`. Extend announcements with `technicalDetail`, keeping `message` as the stable character-facing value consumed by existing callers. Extend the store's Parsec animation type with Task 1's declared states, add setters, and ensure store-test cleanup returns these fields to defaults.

- [x] **Step 4: Implement the dependency-injected coordinator and singleton wrappers**

The coordinator environment must inject `now`, `setTimer`, `clearTimer`, `publish`, and `record` so fake-timer tests do not depend on browser rendering. Use a five-item queue, dedupe by key, cancel delayed started-events when replaced, and publish `null` when the current item expires. The singleton environment writes only through `appStore` setters.

- [x] **Step 5: Route compatibility notification helpers through the coordinator**

Map current calls as follows:

```ts
announce(message, 'info', tool) -> notice.info
announceSuccess(message, tool) -> notice.success
announceError(error, tool) -> notice.error with technicalDetail equal to the exact error string
react(state, duration) -> reactParsec(state, duration)
```

Keep exported names until every current import is migrated. Do not remove durable inline error assignments from callers.

- [x] **Step 6: Run focused store/coordinator/component compatibility tests**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/coordinator.test.ts src/store/appStore.test.ts src/components/Parsec.test.tsx`

Expected: PASS after updating the existing component fixture to read `appState.parsecFeedback.text`.

- [x] **Step 7: Review checkpoint**

Run: `git diff --check -- webapp/frontend/src/lib/notify.ts webapp/frontend/src/lib/parsec webapp/frontend/src/store`

Expected: no output. Leave changes uncommitted.

---

### Task 3: Render the anchored balloon and pause patrol while speaking

**Files:**
- Modify: `webapp/frontend/src/components/Parsec.tsx`
- Modify: `webapp/frontend/src/components/Parsec.module.css`
- Modify: `webapp/frontend/src/components/Parsec.test.tsx`
- Modify: `webapp/frontend/src/lib/parsecEngine.ts`
- Modify: `webapp/frontend/src/lib/parsecEngine.test.ts`

**Interfaces:**
- Consumes: `appState.parsecFeedback`, `dismissParsec`, Task 1 animation names, existing sprite sheet and motion preference.
- Produces: a render-only balloon stage whose CSS tail receives the clamped sprite anchor as `--parsec-anchor-x`.

- [x] **Step 1: Add failing component and engine tests**

```ts
it('renders one anchored speech balloon and keeps exact diagnostics out of it', () => {
	reportParsec({ type: 'fetch', phase: 'failed', tool: 'lore-editor', summary: 'Could not load entry', technicalDetail: 'HTTP 500 secret detail' });
	const balloon = host.querySelector('[data-parsec-balloon]');
	expect(balloon?.textContent).toContain('*growls');
	expect(balloon?.textContent).not.toContain('HTTP 500 secret detail');
	expect(balloon?.getAttribute('role')).toBe('alert');
	expect(host.querySelector('[data-parsec-stage]')).toHaveClass(styles.speaking);
});

it('clamps the tail away from both stage corners', () => {
	expect(clampBalloonAnchor(-10, 240, 72)).toBe(18);
	expect(clampBalloonAnchor(230, 240, 72)).toBe(222);
});
```

- [x] **Step 2: Run focused tests and confirm failure**

Run: `npm --prefix webapp/frontend test -- --run src/components/Parsec.test.tsx src/lib/parsecEngine.test.ts`

Expected: FAIL because anchored-stage markup and `clampBalloonAnchor` are absent.

- [x] **Step 3: Move balloon state entirely to coordinator publication**

Remove the component-local bubble signal and timer. Render `appState.parsecFeedback` directly. Patting reports an interaction event once; it must not separately call `showBubble`. Preserve keyboard activation and repeated-pat behavior.

- [x] **Step 4: Implement speaking-stage geometry**

Use a fixed 72-pixel sprite floor plus an auto-sized balloon region above it. Keep the outer stage `overflow: visible` vertically while constraining the balloon to the rail width. Render a CSS triangle tail using the published `--parsec-anchor-x`. Update that variable when horizontal position changes and freeze horizontal patrol while feedback is active. Continue the current frame loop in place.

The balloon uses `role="alert"` only for error feedback and `role="status" aria-live="polite"` otherwise. Error, warning, success, and info each receive text plus semantic border treatment; no meaning relies on border color alone.

- [x] **Step 5: Implement reduced-motion and long-copy containment**

Reduced motion selects frame zero, disables patrol and balloon transition, and leaves the balloon readable. Clamp line width, allow normal wrapping, and prevent page overlap at the shell's narrow fallback width.

- [x] **Step 6: Run component, engine, and accessibility tests**

Run: `npm --prefix webapp/frontend test -- --run src/components/Parsec.test.tsx src/lib/parsecEngine.test.ts src/components/GlobalSearch.accessibility.test.tsx`

Expected: PASS.

- [x] **Step 7: Review checkpoint**

Run: `git diff --check -- webapp/frontend/src/components/Parsec.tsx webapp/frontend/src/components/Parsec.module.css webapp/frontend/src/lib/parsecEngine.ts`

Expected: no output. Leave changes uncommitted.

---

### Task 4: Route global search and loading lifecycles through Parsec

**Files:**
- Modify: `webapp/frontend/src/components/GlobalSearch.tsx`
- Modify: `webapp/frontend/src/components/GlobalSearch.accessibility.test.tsx`
- Modify: `webapp/frontend/src/components/globalSearch.test.ts`
- Modify: `webapp/frontend/src/components/LoadingIndicator.tsx`
- Create: `webapp/frontend/src/components/LoadingIndicator.test.tsx`
- Modify: `webapp/frontend/src/tools/loreEditor/LoreEditorPage.tsx`
- Modify: `webapp/frontend/src/tools/loreEditor/LoreEditorPage.test.tsx`

**Interfaces:**
- Consumes: `reportParsec(event)` and existing selected context.
- Produces: deduplicated search and fetch events while preserving listbox status, inline errors, and regional progress indicators.

- [x] **Step 1: Add failing global-search lifecycle tests**

```ts
it('supersedes an earlier search and reports an empty current result once', async () => {
	vi.useFakeTimers();
	vi.spyOn(api, 'post').mockResolvedValue({ results: [], semantic_search: { mode: 'hybrid', model_id: 'test', reason: null } });
	const report = vi.spyOn(parsecCoordinator, 'reportParsec');
	input.value = 'radio';
	input.dispatchEvent(new InputEvent('input', { bubbles: true }));
	await vi.advanceTimersByTimeAsync(250);
	expect(report).toHaveBeenCalledWith(expect.objectContaining({ type: 'search', phase: 'started', dedupeKey: 'global-search' }));
	expect(report).toHaveBeenCalledWith(expect.objectContaining({ type: 'search', phase: 'empty', query: 'radio', resultCount: 0 }));
});
```

Keep the existing assertions for related-result boosting, semantic fallback text, combobox status, keyboard navigation, and Axe.

- [x] **Step 2: Add failing delayed-loading tests**

Test that mounting an announcing `LoadingIndicator` reports `fetch.started`, unmounting reports
`fetch.completed`, and unmounting before the coordinator's delayed threshold never publishes a balloon.
Require a stable `feedbackKey` prop so nested loads replace their own event rather than unrelated work.

- [x] **Step 3: Run focused tests and confirm failure**

Run: `npm --prefix webapp/frontend test -- --run src/components/GlobalSearch.accessibility.test.tsx src/components/LoadingIndicator.test.tsx src/tools/loreEditor/LoreEditorPage.test.tsx`

Expected: FAIL because lifecycle reporting and `feedbackKey` are absent.

- [x] **Step 4: Report search phases without narrating each keystroke**

Emit `search.started` after the existing 200 ms debounce. Use `dedupeKey: 'global-search'`. Emit
`superseded` when a later request invalidates an earlier request, `empty` only when both page matches and API
results are empty, `completed` for explicit Enter activation or useful result completion, and `failed` with
the exact caught message as `technicalDetail`. Keep the existing hidden combobox status as the durable
accessible result-count owner.

- [x] **Step 5: Upgrade `LoadingIndicator` and Lore Editor keys**

Replace `announceThroughParsec` with `reportThroughParsec` plus required `feedbackKey` when enabled. Report
started on mount, completed on cleanup only if no failure event replaced it, and let the coordinator suppress
short loads. Use keys `route:${tool.id}`, `lore-entry:${selected()?.id}`, and `lore-groups` at the current
call sites. Keep the authoring-pane-only Suspense boundary.

- [x] **Step 6: Run focused tests**

Run: `npm --prefix webapp/frontend test -- --run src/components/GlobalSearch.accessibility.test.tsx src/components/globalSearch.test.ts src/components/LoadingIndicator.test.tsx src/tools/loreEditor/LoreEditorPage.test.tsx`

Expected: PASS.

- [x] **Step 7: Review checkpoint**

Run: `git diff --check -- webapp/frontend/src/components/GlobalSearch.tsx webapp/frontend/src/components/LoadingIndicator.tsx webapp/frontend/src/tools/loreEditor/LoreEditorPage.tsx`

Expected: no output. Leave changes uncommitted.

---

### Task 5: Route connection, job, mutation, validation, and navigation feedback

**Files:**
- Create: `webapp/frontend/src/lib/live.test.ts`
- Modify: `webapp/frontend/src/lib/live.ts`
- Modify: `webapp/frontend/src/components/AppShell.tsx`
- Modify: `webapp/frontend/src/tools/fileManagement/ExportPanel.tsx`
- Modify: `webapp/frontend/src/tools/fileManagement/RepositoryPanel.tsx`
- Modify: `webapp/frontend/src/tools/fileManagement/ToolRunner.tsx`
- Modify: `webapp/frontend/src/tools/contentGraph/ContentGraphPage.tsx`
- Modify: `webapp/frontend/src/tools/contentGraph/ModularDebugPanel.tsx`
- Modify: `webapp/frontend/src/tools/loreEditor/EntryEditor.tsx`
- Modify: `webapp/frontend/src/tools/loreEditor/GroupManager.tsx`
- Modify: `webapp/frontend/src/tools/loreEditor/ReviewActions.tsx`
- Modify: `webapp/frontend/src/components/SharedReferences.tsx`
- Modify: `webapp/frontend/src/components/OpenFileActions.tsx`
- Modify: affected existing tests beside each component.

**Interfaces:**
- Consumes: `reportParsec` event families and `setActiveRoute`.
- Produces: typed, contextual feedback for existing meaningful actions while preserving all current inline state.

- [x] **Step 1: Add failing connection transition tests**

Inject or mock WebSocket/poll dependencies and assert that the first successful connection reports
`connected`, a later close reports `disconnected`, polling fallback reports `polling`, and a later success
reports `recovered`. Repeated failed polls with the same state must dedupe rather than create repeated errors.

- [x] **Step 2: Run the live test and confirm failure**

Run: `npm --prefix webapp/frontend test -- --run src/lib/live.test.ts`

Expected: FAIL because connection transitions do not report typed Parsec events.

- [x] **Step 3: Add transition-aware live reporting**

Track the last connection mode inside the live owner. Report only changes, use `dedupeKey: 'live-connection'`,
and keep `setConnected` as the durable shell-status source.

- [x] **Step 4: Add route context without moving router ownership**

In `AppShell`, use one Solid effect to call `setActiveRoute(location.pathname)` and report
`navigation.context-changed` with `replacesKey: 'navigation'`. The coordinator records context but does not
show a balloon for ordinary navigation.

- [x] **Step 5: Migrate existing action calls by semantic family**

Use these exact mappings:

- Saves, deletes, review decisions, assignments, reference changes, export prepare/apply: `mutation`.
- Catalog generation, tool runs, and content-graph scan: `job`.
- Unsafe repository/export state and rejected write conditions: `validation`.
- Open-file bridge errors and unexpected request errors: failed `fetch` or `mutation` matching the action.

Every failed event carries the caught string as `technicalDetail`. Keep existing `setMessage`, `setStatus`,
alert focus, retry buttons, and result panels. Remove a compatibility `announce*` import only after the same
component has direct typed coverage.

- [x] **Step 6: Run all affected focused tests**

Run: `npm --prefix webapp/frontend test -- --run src/lib/live.test.ts src/tools/fileManagement/ToolRunner.test.tsx src/tools/contentGraph/ContentGraphPage.test.tsx src/tools/loreEditor/LoreAuthoring.test.tsx src/components/SharedReferences.test.tsx src/components/OpenFileActions.test.tsx`

Expected: PASS.

- [x] **Step 7: Prove no feature bypasses the compatibility boundary accidentally**

Run: `rg -n "announce\(|announceSuccess|announceError" webapp/frontend/src`

Expected: only `notify.ts`, deliberate compatibility tests, and Parsec preview code remain. Any retained call must be listed with its reason in the plan's execution notes.

- [x] **Step 8: Review checkpoint**

Run: `git diff --check -- webapp/frontend/src`

Expected: no output. Leave changes uncommitted.

---

### Task 6: Add idle chatter settings and contextual scheduling

**Files:**
- Create: `webapp/frontend/src/lib/parsec/settings.ts`
- Create: `webapp/frontend/src/lib/parsec/settings.test.ts`
- Create: `webapp/frontend/src/lib/parsec/idle.ts`
- Create: `webapp/frontend/src/lib/parsec/idle.test.ts`
- Modify: `webapp/frontend/src/App.tsx`
- Modify: `webapp/frontend/src/tools/parsec/ParsecPage.tsx`
- Modify: `webapp/frontend/src/tools/parsec/ParsecPage.test.tsx`
- Modify: `webapp/frontend/src/tools/parsec/ParsecPage.module.css`

**Interfaces:**
- Consumes: `appState.activeRoute`, `selectedContext`, active runs, connection state, active feedback, `reportParsec`, and browser visibility/focus.
- Produces: `readIdleChatterPreference`, `writeIdleChatterPreference`, `nextIdleDelayMs`, `startParsecIdleScheduler(): () => void`, and the `/parsec` setting.

- [x] **Step 1: Write failing settings and idle-policy tests**

```ts
it('defaults to rare and persists every supported preference', () => {
	expect(readIdleChatterPreference()).toBe('rare');
	for (const preference of ['off', 'rare', 'occasional', 'frequent'] as const) {
		writeIdleChatterPreference(preference);
		expect(readIdleChatterPreference()).toBe(preference);
	}
});

it('suppresses chatter while hidden, typing, working, or already speaking', () => {
	const base = eligibleIdleContext({ route: '/lore-editor' });
	expect(canEmitIdle({ ...base, documentVisible: false })).toBe(false);
	expect(canEmitIdle({ ...base, editableFocused: true })).toBe(false);
	expect(canEmitIdle({ ...base, activeRunCount: 1 })).toBe(false);
	expect(canEmitIdle({ ...base, hasFeedback: true })).toBe(false);
});
```

- [x] **Step 2: Run focused tests and confirm failure**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/settings.test.ts src/lib/parsec/idle.test.ts src/tools/parsec/ParsecPage.test.tsx`

Expected: FAIL because settings and scheduler modules are absent.

- [x] **Step 3: Implement robust browser-local settings**

Use key `aphelion-parsec-idle-chatter`. Accept only the four declared values. Default invalid, missing, or
unreadable storage to `rare`. Storage write failures remain silent and do not generate feedback recursively.

- [x] **Step 4: Implement randomized intervals and context eligibility**

Use inclusive ranges: rare `480000–720000`, occasional `240000–420000`, frequent `120000–240000`
milliseconds. Inject `random`, `setTimer`, and `clearTimer` for deterministic tests. Suppress while hidden,
an editable element is focused, an active run exists, the connection needs attention, or feedback is
visible. Reset the timer on route or selected-context change.

Provide reviewed line pools for `/`, `/lore-editor`, `/content-graph`, `/file-management`, and `/parsec`.
Do not quote selected record content. Track recent line indexes so a pool cycles before repeating.

- [x] **Step 5: Start and dispose the scheduler once**

Mount the scheduler beside `connectLiveUpdates()` in `App.tsx` and dispose both through the existing app
lifecycle. Do not add page-owned idle timers.

- [x] **Step 6: Add the `/parsec` setting and previews**

Add a labeled select with Off, Rare, Occasional, and Frequent; show Rare as the default. Add event-family
preview buttons that call typed coordinator events. Keep the existing motion setting and pat/twerk previews.

- [x] **Step 7: Run focused settings, scheduler, and page tests**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/settings.test.ts src/lib/parsec/idle.test.ts src/tools/parsec/ParsecPage.test.tsx`

Expected: PASS.

- [x] **Step 8: Review checkpoint**

Run: `git diff --check -- webapp/frontend/src/lib/parsec webapp/frontend/src/App.tsx webapp/frontend/src/tools/parsec`

Expected: no output. Leave changes uncommitted.

---

### Task 7: Update history, documentation, and asset discoverability

**Files:**
- Modify: `webapp/frontend/src/tools/parsec/ParsecPage.tsx`
- Modify: `webapp/frontend/src/tools/parsec/ParsecPage.test.tsx`
- Modify: `references/maintainer-guide.md`
- Modify: `references/writer-guide.md`
- Modify: `references/parsec-asset-register.md`
- Modify: `tools/docs/check_agent_docs.py` only if the register becomes a required local-link target.

**Interfaces:**
- Consumes: extended `Announcement` fields and the canonical paths in the asset register.
- Produces: discoverable attribution, technical history, and user-facing setting guidance.

- [x] **Step 1: Add failing history tests**

Report an error with `technicalDetail`, render `/parsec`, and assert the playful line and exact detail are
both present as separate text. Assert the page links to `/references/parsec-asset-register.md`, the runtime
sprite sheet, and the OpenGameArt source.

- [x] **Step 2: Run the focused page test and confirm failure**

Run: `npm --prefix webapp/frontend test -- --run src/tools/parsec/ParsecPage.test.tsx`

Expected: FAIL because technical detail and asset-register links are not rendered.

- [x] **Step 3: Render history and asset links**

Keep the character-facing line first. Render technical detail in selectable code/metadata text only when it
differs from the spoken line. Preserve timestamp, tool, and severity. Add canonical sheet, upstream source,
license, and asset-register links to the attribution card.

- [x] **Step 4: Update maintainer and writer documentation**

Document the typed-event responsibility boundary, compatibility-wrapper migration rule, anchored balloon,
idle setting values/default, durable-diagnostic rule, and exact asset-register location. Do not describe
candidate artwork as shipped.

- [x] **Step 5: Run documentation and frontend page checks**

Run: `python tools/docs/check_agent_docs.py`

Expected: `Agent documentation is consistent.`

Run: `npm --prefix webapp/frontend test -- --run src/tools/parsec/ParsecPage.test.tsx`

Expected: PASS.

- [x] **Step 6: Review checkpoint**

Run: `git diff --check -- references webapp/frontend/src/tools/parsec tools/docs/check_agent_docs.py`

Expected: no output. Leave changes uncommitted.

---

### Task 8: Make and evaluate best-effort action animation candidates

**Files:**
- Inspect: `webapp/frontend/src/assets/parsec.png`
- Create conditionally: `webapp/frontend/src/assets/parsec-actions.png`
- Modify conditionally: `webapp/frontend/src/lib/parsecEngine.ts`
- Modify conditionally: `webapp/frontend/src/lib/parsecEngine.test.ts`
- Modify: `references/parsec-asset-register.md`

**Interfaces:**
- Consumes: the canonical `72 × 51` cell contract, existing palette/silhouette, and Task 1 animation fallbacks.
- Produces: accepted action frames with stable coordinates, or explicit `human help requested` register entries. Functional behavior does not depend on acceptance.

- [x] **Step 1: Preserve and inspect the canonical source at native and enlarged scale**

Record the existing image hash, dimensions `432 × 204`, transparency, palette, four row mappings, and source
license before editing. Do not overwrite `parsec.png` during candidate generation.

- [x] **Step 2: Generate or edit one high-priority candidate family at a time**

Use the image-generation skill for bitmap creation/editing. Start with `parsec-search-sniff`, then
`parsec-empty-confused`, `parsec-fetch-dig`, and `parsec-error-anxious`. Request transparent pixel-art frames
matching the supplied canonical sheet, with each frame constrained to `72 × 51`. Do not generate lore,
names, descriptions, audio, or unrelated decoration.

- [x] **Step 3: Normalize candidates without smoothing**

Crop/pad accepted candidates to exact cells, preserve alpha, and compose them into a separate action sheet.
Use nearest-neighbor scaling only for review renders. Do not resample the canonical sheet.

- [x] **Step 4: Review every loop against the register checklist**

At native size and enlarged nearest-neighbor scale, reject any candidate whose silhouette, outline, palette,
eye detail, proportions, transparency, or loop endpoints visibly depart from the canonical sheet. A rejected
candidate is not wired into runtime code.

- [x] **Step 5: Integrate only accepted rows**

If a family passes, record exact action-sheet coordinates and add it to `FRAME_SETS` with a fallback map for
missing states. Add tests asserting frame count, row/column spacing, source sheet, and reduced-motion frame.
If none pass, do not create `parsec-actions.png`; change the relevant register statuses to
`human help requested` and describe the observed mismatch.

- [x] **Step 6: Run frame tests and inspect both images**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsecEngine.test.ts`

Expected: PASS whether states use accepted action frames or declared core-sheet fallbacks.

- [x] **Step 7: Review checkpoint**

Run: `git diff --check -- webapp/frontend/src/lib/parsecEngine.ts webapp/frontend/src/lib/parsecEngine.test.ts references/parsec-asset-register.md`

Expected: no output. Leave changes uncommitted.

---

### Task 9: Complete repository and real-launcher verification

**Files:**
- Modify only when a gate exposes a Parsec regression.
- Inspect: all files changed by Tasks 1–8 and existing unrelated dirty work.

**Interfaces:**
- Consumes: the complete implementation.
- Produces: current evidence for focused, repository-wide, build, accessibility, browser, launcher, and diff gates.

- [x] **Step 1: Run frontend API generation and inspect drift**

Run: `npm --prefix webapp/frontend run gen:api`

Expected: exit 0; no Parsec work should create OpenAPI drift.

- [x] **Step 2: Run frontend typecheck, full tests, and production build**

Run: `npm --prefix webapp/frontend run typecheck`

Run: `npm --prefix webapp/frontend test -- --run`

Run: `npm --prefix webapp/frontend run build`

Expected: all exit 0. Record test-file/test counts and Vite module count.

- [x] **Step 3: Run repository Python and documentation gates**

Run: `python -m ruff check .`

Run: `python -m pyright`

Run: `python -m unittest discover`

Run: `python tools/docs/check_agent_docs.py`

Expected: all exit 0. Record any unrelated pre-existing failure separately rather than weakening a gate.

- [x] **Step 4: Launch the shipped entry point**

Run: `cmd.exe /d /c '"Launch Aphelion Content Tools.cmd"'`

Expected: the loopback readiness marker appears and the production SPA loads through the launcher. Keep the
process available for browser verification, then use its documented clean shutdown path.

- [x] **Step 5: Exercise the real browser flow**

Verify:

1. Lore Editor queue remains mounted while selection loading affects only the authoring pane.
2. Delayed selection loading produces one anchored Parsec fetch balloon and no full-page loading flash.
3. Global search keeps selected-context boosting, keyboard navigation, durable result status, and typed
   Parsec empty/error feedback without keystroke spam.
4. Save, validation failure, background job, disconnect/recovery, and pat previews select the intended
   voice, priority, and animation.
5. Errors retain exact inline diagnostics and history detail.
6. Rare is the default idle setting; Off suppresses; a shortened test harness proves contextual chatter
   without waiting eight minutes in the acceptance run.
7. Reduced motion freezes patrol and transitions while balloons and text remain functional.
8. Anchored balloons remain inside the sidebar at normal and narrow supported widths.

- [x] **Step 6: Run final diff and working-tree inventory**

Run: `git diff --check`

Run: `git status --short`

Expected: no diff-check output. Inventory Parsec files separately from pre-existing unrelated work. Leave all changes uncommitted.

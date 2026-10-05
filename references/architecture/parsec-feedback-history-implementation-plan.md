# Parsec Radio Log and Activity History Implementation Plan

Status: implemented and verified on 2026-08-24

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan inline, task by task. Do not dispatch subagents without Zoe's explicit approval. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace Parsec's balloons and session-only announcements with an SS13-style compact radio log backed by a durable, structured, browser-local activity journal.

**Architecture:** Preserve the existing typed `ParsecCoordinator` as the event-priority and voice boundary. Add a versioned native IndexedDB journal behind an injected interface, publish a small reactive live-log projection through the existing app store, and keep exact page-owned diagnostics unchanged.

**Tech Stack:** SolidJS 1.9, TypeScript 5.7, Vitest 3, native IndexedDB, CSS Modules, existing Parsec event/policy/voice modules.

**Spec:** [`references/architecture/parsec-companion-design.md`](parsec-companion-design.md)

## Global Constraints

- Preserve the shared `AppShell`, tool registry, typed API client, live owner, selected context, and shared app-store path.
- `ParsecCoordinator` owns character-facing feedback; feature owners retain requests and exact inline status.
- Remove balloon presentation without removing typed event priority, delay, deduplication, or reviewed voice.
- Store no complete lore document body. Redact secret-shaped values before persistence.
- Retention choices are 7, 30, 90, 365 days, or manual-clear; default is 90 days.
- Keep profile import/export separate from activity-history export.
- Add behavioral tests before behavior changes.
- Leave changes uncommitted and do not dispatch agents.

---

## File structure

### New files

- `webapp/frontend/src/lib/parsec/journalTypes.ts` — versioned activity/transcript schemas and retention types.
- `webapp/frontend/src/lib/parsec/redaction.ts` and `.test.ts` — allowlisted persistent fields and secret redaction.
- `webapp/frontend/src/lib/parsec/journal.ts` and `.test.ts` — injected journal service, retention, querying, export rows.
- `webapp/frontend/src/lib/parsec/indexedDbJournal.ts` — native IndexedDB backend and migrations.
- `webapp/frontend/src/components/ParsecRadioLog.tsx`, `.module.css`, and `.test.tsx` — compact/collapsed/expanded log.
- `webapp/frontend/src/tools/parsec/ActivityHistory.tsx`, `.module.css`, and `.test.tsx` — filtering, retention, export, and clear controls.

### Modified files

- `webapp/frontend/src/lib/parsec/types.ts` — stable event ID, route/context metadata, reaction, and journal linkage.
- `webapp/frontend/src/lib/parsec/coordinator.ts` and `.test.ts` — append accepted events to the journal sink.
- `webapp/frontend/src/store/appStore.ts` and `.test.ts` — bounded live-log projection instead of balloon-only state.
- `webapp/frontend/src/components/Parsec.tsx`, `.module.css`, and `.test.tsx` — remove balloon and mount the radio log below the action slot.
- `webapp/frontend/src/tools/parsec/ParsecPage.tsx`, `.module.css`, and `.test.tsx` — mount durable activity history.
- `references/maintainer-guide.md`, `references/writer-guide.md`, and `references/architecture/parsec-feedback-design.md` — document the migration and supersession.

### Interfaces

```ts
export type ActivityRetentionDays = 7 | 30 | 90 | 365 | 'manual';

export interface ActivityRecord {
	readonly schemaVersion: 1;
	readonly id: string;
	readonly at: number;
	readonly eventType: ParsecEvent['type'];
	readonly phase: string;
	readonly tool: string | null;
	readonly route: string | null;
	readonly contextId: string | null;
	readonly durationMs: number | null;
	readonly resultCount: number | null;
	readonly outcome: 'started' | 'completed' | 'cancelled' | 'warning' | 'failed' | 'notice';
	readonly technicalDetail: string | null;
	readonly parsecText: string | null;
	readonly reaction: ParsecAnimation | null;
}

export interface ActivityJournal {
	append(record: ActivityRecord): Promise<void>;
	query(query: ActivityQuery): Promise<readonly ActivityRecord[]>;
	prune(retention: ActivityRetentionDays, now: number): Promise<number>;
	clear(): Promise<void>;
	close(): void;
}
```

### Task 1: Define durable record, redaction, and retention policy

**Files:**
- Create: `webapp/frontend/src/lib/parsec/journalTypes.ts`
- Create: `webapp/frontend/src/lib/parsec/redaction.ts`
- Create: `webapp/frontend/src/lib/parsec/redaction.test.ts`
- Modify: `webapp/frontend/src/lib/parsec/types.ts`

**Interfaces:**
- Produces: `ActivityRecord`, `ActivityQuery`, `ActivityRetentionDays`, `recordForFeedback(event, feedback, context)`, and `redactTechnicalDetail(value)`.
- Consumes: existing `ParsecEvent`, `ParsecFeedback`, and `ParsecAnimation`.

- [x] **Step 1: Write failing redaction and projection tests**

```ts
it('redacts secret assignments without deleting useful failure context', () => {
	expect(redactTechnicalDetail('HTTP 500 token=abc123 path=C:\\repo\\file.json'))
		.toBe('HTTP 500 token=[REDACTED] path=C:\\repo\\file.json');
});

it('never copies lore bodies into a durable activity record', () => {
	const record = recordForFeedback(eventWithSummaryAndDetail, feedback, context);
	expect(JSON.stringify(record)).not.toContain('documentBody');
	expect(record.contextId).toBe('record:/obj/item/radio');
});
```

- [x] **Step 2: Run the focused tests and confirm the missing modules fail**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/redaction.test.ts`

Expected: FAIL because `redaction.ts` and `journalTypes.ts` do not exist.

- [x] **Step 3: Implement an explicit persistence allowlist**

Persist only the fields in `ActivityRecord`. Redact case-insensitive assignment forms for `token`,
`password`, `secret`, `authorization`, `api_key`, `apikey`, and `cookie`. Clamp persisted technical detail
to 8,000 characters and Parsec text to 1,000 characters. Do not serialize arbitrary event objects.

- [x] **Step 4: Run focused tests and typecheck the new contracts**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/redaction.test.ts`

Run: `npm --prefix webapp/frontend run typecheck`

Expected: PASS.

- [x] **Step 5: Review checkpoint**

Run: `git diff --check -- webapp/frontend/src/lib/parsec`

Expected: no output. Leave changes uncommitted.

### Task 2: Implement the injected IndexedDB activity journal

**Files:**
- Create: `webapp/frontend/src/lib/parsec/journal.ts`
- Create: `webapp/frontend/src/lib/parsec/journal.test.ts`
- Create: `webapp/frontend/src/lib/parsec/indexedDbJournal.ts`

**Interfaces:**
- Consumes: Task 1 `ActivityRecord`, `ActivityQuery`, and `ActivityRetentionDays`.
- Produces: `createActivityJournal(backend)`, `openIndexedDbJournal()`, `recordsToJson(records)`, and `recordsToCsv(records)`.

- [x] **Step 1: Write failing service tests against an in-memory backend**

```ts
it('returns newest matching records and prunes at the retention boundary', async () => {
	const journal = createActivityJournal(createMemoryJournalBackend());
	await journal.append(recordAt(day(1), 'search'));
	await journal.append(recordAt(day(100), 'fetch'));
	expect(await journal.prune(90, day(100))).toBe(1);
	expect((await journal.query({ limit: 50 })).map((entry) => entry.eventType)).toEqual(['fetch']);
});

it('escapes spreadsheet formulas in CSV exports', () => {
	expect(recordsToCsv([recordWithText('=HYPERLINK("bad")')])).toContain("'=HYPERLINK");
});
```

- [x] **Step 2: Run the focused journal tests**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/journal.test.ts`

Expected: FAIL because the journal service does not exist.

- [x] **Step 3: Implement schema version 1 and safe fallback behavior**

Create database `aphelion-parsec`, object store `activity` keyed by `id`, and indexes `at`, `eventType`,
`tool`, and `outcome`. Open failures return an in-memory session backend and one nonrecursive diagnostic
flag; they must not report failure through Parsec. Quarantine an unrecognized schema by closing it and
offering reset from the Parsec page rather than deleting it automatically.

- [x] **Step 4: Run the service tests**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/journal.test.ts`

Expected: PASS.

- [x] **Step 5: Run typecheck and diff hygiene**

Run: `npm --prefix webapp/frontend run typecheck`

Run: `git diff --check -- webapp/frontend/src/lib/parsec`

Expected: both pass.

### Task 3: Route accepted Parsec events into the journal and live-log projection

**Files:**
- Modify: `webapp/frontend/src/lib/parsec/coordinator.ts`
- Modify: `webapp/frontend/src/lib/parsec/coordinator.test.ts`
- Modify: `webapp/frontend/src/store/appStore.ts`
- Modify: `webapp/frontend/src/store/appStore.test.ts`

**Interfaces:**
- Consumes: Task 2 `ActivityJournal` and Task 1 `recordForFeedback`.
- Produces: `ParsecCoordinatorEnvironment.recordActivity`, `appState.parsecLog`, `appendParsecLog`, and `clearParsecLiveLog`.

- [x] **Step 1: Add failing coordinator tests for durable and coalesced recording**

```ts
it('records one durable event for accepted feedback and links the live line', async () => {
	coordinator.report(failedFetch);
	await harness.flushActivity();
	expect(harness.activities).toHaveLength(1);
	expect(harness.liveLines[0]?.activityId).toBe(harness.activities[0]?.id);
});

it('does not persist a fast fetch that was suppressed before the delay', async () => {
	coordinator.report(startedFetch);
	coordinator.report(completedFetch);
	await harness.flushActivity();
	expect(harness.activities).toEqual([]);
});
```

- [x] **Step 2: Run coordinator and store tests**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/coordinator.test.ts src/store/appStore.test.ts`

Expected: FAIL on the missing journal/live-log contract.

- [x] **Step 3: Implement the asynchronous sink without blocking presentation**

Publish the live line synchronously. Append the structured record through a serialized promise chain;
journal failure sets a diagnostic state on the Parsec settings page but never rejects `reportParsec`.
Keep the existing `announcements` projection as a compatibility alias during this plan, but stop treating
it as the durable source.

- [x] **Step 4: Run focused tests**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec/coordinator.test.ts src/store/appStore.test.ts`

Expected: PASS.

- [x] **Step 5: Review checkpoint**

Run: `git diff --check -- webapp/frontend/src/lib/parsec/coordinator.ts webapp/frontend/src/store/appStore.ts`

Expected: no output.

### Task 4: Replace the balloon with the compact radio log

**Files:**
- Create: `webapp/frontend/src/components/ParsecRadioLog.tsx`
- Create: `webapp/frontend/src/components/ParsecRadioLog.module.css`
- Create: `webapp/frontend/src/components/ParsecRadioLog.test.tsx`
- Modify: `webapp/frontend/src/components/Parsec.tsx`
- Modify: `webapp/frontend/src/components/Parsec.module.css`
- Modify: `webapp/frontend/src/components/Parsec.test.tsx`

**Interfaces:**
- Consumes: Task 3 `appState.parsecLog` and the profile's `compact | collapsed | expanded` presentation preference.
- Produces: render-only `<ParsecRadioLog />` with accessible live-region behavior.

- [x] **Step 1: Replace balloon assertions with failing radio-log tests**

```tsx
it('shows the newest three to five lines in compact SS13 radio form', () => {
	reportParsec(failedFetch);
	const log = host.querySelector('[data-parsec-radio-log]');
	expect(log?.textContent).toContain('Parsec:');
	expect(log?.textContent).not.toContain('HTTP 500 secret detail');
});

it('expands actionable errors without covering the app page', () => {
	expect(host.querySelector('[data-parsec-balloon]')).toBeNull();
	expect(host.querySelector('[data-parsec-radio-log][data-expanded="true"]')).not.toBeNull();
});
```

- [x] **Step 2: Run component tests and confirm they fail**

Run: `npm --prefix webapp/frontend test -- --run src/components/ParsecRadioLog.test.tsx src/components/Parsec.test.tsx`

Expected: FAIL because the radio-log component does not exist and the balloon still renders.

- [x] **Step 3: Implement compact, collapsed, and expanded modes**

Use semantic list markup, a visible `Parsec:` speaker label, timestamp, severity text, unread marker, and
an accessible details control for linked technical information. Ordinary new lines use `role="status"`
and `aria-live="polite"`; an actionable error uses `role="alert"` once. Never render technical detail as
character copy.

- [x] **Step 4: Run component and accessibility-focused tests**

Run: `npm --prefix webapp/frontend test -- --run src/components/ParsecRadioLog.test.tsx src/components/Parsec.test.tsx src/components/AppShell.accessibility.test.tsx`

Expected: PASS.

- [x] **Step 5: Review at desktop and narrow shell widths**

Exercise 1280px and the supported narrow fallback. Confirm the log stays inside the sidebar, expands
vertically without page overlay, preserves focus, and does not reintroduce oversized buttons.

### Task 5: Add durable history controls and documentation

**Files:**
- Create: `webapp/frontend/src/tools/parsec/ActivityHistory.tsx`
- Create: `webapp/frontend/src/tools/parsec/ActivityHistory.module.css`
- Create: `webapp/frontend/src/tools/parsec/ActivityHistory.test.tsx`
- Modify: `webapp/frontend/src/tools/parsec/ParsecPage.tsx`
- Modify: `webapp/frontend/src/tools/parsec/ParsecPage.test.tsx`
- Modify: `references/maintainer-guide.md`
- Modify: `references/writer-guide.md`
- Modify: `references/architecture/parsec-feedback-design.md`

**Interfaces:**
- Consumes: Task 2 query/prune/export/clear operations.
- Produces: retention setting, filters, JSON/CSV downloads, storage status, clear confirmation, and migration recovery.

- [x] **Step 1: Write failing settings/history tests**

```tsx
it('defaults retention to 90 days and keeps profile export separate', () => {
	expect(retentionSelect.value).toBe('90');
	expect(screen.getByRole('button', { name: 'Export companion profile' })).toBeTruthy();
	expect(screen.getByRole('button', { name: 'Export activity history' })).toBeTruthy();
});
```

- [x] **Step 2: Run focused Parsec-page tests**

Run: `npm --prefix webapp/frontend test -- --run src/tools/parsec/ActivityHistory.test.tsx src/tools/parsec/ParsecPage.test.tsx`

Expected: FAIL on missing controls.

- [x] **Step 3: Implement filters and explicit destructive confirmation**

Filter by date range, tool, event family, outcome, and free text over Parsec copy and allowed technical
detail. Export uses a Blob download. `Clear activity history` requires an explicit confirmation inside
the page and reports the number removed without erasing the companion profile.

- [x] **Step 4: Update normative documentation**

Change the maintainer guide from balloon/session history to radio log/IndexedDB journal. Mark the balloon
layout section of the older design as superseded and link this specification. Document retention,
export, clear, and local-only status in the writer guide.

- [x] **Step 5: Run the plan gates**

Run: `npm --prefix webapp/frontend test -- --run src/lib/parsec src/components/ParsecRadioLog.test.tsx src/components/Parsec.test.tsx src/tools/parsec`

Run: `npm --prefix webapp/frontend run typecheck`

Run: `npm --prefix webapp/frontend run build`

Run: `python tools/docs/check_agent_docs.py`

Run: `git diff --check`

Expected: all pass. Leave changes uncommitted.

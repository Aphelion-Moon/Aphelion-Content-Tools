# Lore Editor Restoration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Do not dispatch subagents. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore a compact two-pane Lore Editor inside the existing Solid SPA while preserving every current SPA contract and Lore workflow.

**Architecture:** `LoreEditorPage` remains the route coordinator and composes a focused filter component, the existing virtualized `ReviewList`, and the existing authoring components into independently scrolling queue and editor panes. Reviewer identity moves to the page-level workspace header and is passed into `ReviewActions`; shared shell, API, store, search, reference, notification, and live-state ownership remain unchanged.

**Tech Stack:** SolidJS, TypeScript, CSS Modules, TanStack Solid Virtual, Vitest, Testing Library DOM primitives, axe-core, FastAPI-generated TypeScript schemas.

**Spec:** `references/architecture/lore-editor-restoration-design.md`

## Global constraints

- Preserve `AppShell`, the tool registry, generated API client, shared Solid store, selected context, global search, references, notifications, and live connection.
- Keep the virtualized paged catalog; do not restore the legacy 500-row cap.
- Keep rollback-only files under `tools/lore_editor/web/` unchanged.
- Preserve every current Lore workflow: review, assignments, override create/edit/delete, validation, conflicts, icons, AutoWiki, groups, deep links, and shared references.
- Keep all Lore styles in `LoreEditor.module.css`; do not add tool-local bare element selectors.
- Do not add a layout toggle or a second Lore implementation.
- Leave all changes uncommitted unless the user separately authorizes a commit.

---

### Task 1: Pin the restored workspace contract with failing tests

**Files:**

- Modify: `webapp/frontend/src/tools/loreEditor/LoreEditorPage.test.tsx`
- Modify: `webapp/frontend/src/tools/loreEditor/ReviewList.accessibility.test.tsx`

**Interfaces:**

- Consumes: existing `LoreEditorPage`, `ReviewList`, `createReviewFeed`, and mocked authoring components.
- Produces: regression expectations for `aria-label="Lore review workspace"`, `aria-label="Lore review queue"`, `aria-label="Lore authoring surface"`, tab placement, selected target persistence, and catalog listbox behavior.

- [x] **Step 1: Add a page-structure test that selects a record and requires both panes at once**

  Render `LoreEditorPage`, wait for the mocked catalog row, select it, then assert:

  ```ts
  const workspace = host.querySelector('[aria-label="Lore review workspace"]');
  expect(workspace).not.toBeNull();
  expect(workspace!.querySelector('[aria-label="Lore review queue"]')).not.toBeNull();
  expect(workspace!.querySelector('[aria-label="Lore authoring surface"]')).not.toBeNull();
  expect(workspace!.querySelector('[data-testid="selected-name"]')?.textContent).toBe('Radio override');
  ```

- [x] **Step 2: Add a test that requires Review and Group Configuration tabs inside the authoring pane**

  Assert that the tablist is a descendant of the authoring surface, switch to Group Configuration,
  and verify the queue remains mounted while the mocked `GroupManager` appears.

- [x] **Step 3: Extend the ReviewList accessibility test**

  Assert the virtualized list retains `role="listbox"`, rows retain `role="option"`, and the selected
  row exposes `aria-selected="true"` after selection.

- [x] **Step 4: Run the focused tests and confirm the new structure fails**

  Run:

  ```powershell
  npm --prefix webapp/frontend test -- --run src/tools/loreEditor/LoreEditorPage.test.tsx src/tools/loreEditor/ReviewList.accessibility.test.tsx
  ```

  Expected: the new page-structure assertions fail because the current page stacks separate cards and
  places its tablist above both of them; existing listbox assertions remain green.

---

### Task 2: Extract queue controls without changing feed behavior

**Files:**

- Create: `webapp/frontend/src/tools/loreEditor/ReviewFilters.tsx`
- Create: `webapp/frontend/src/tools/loreEditor/ReviewFilters.test.tsx`
- Modify: `webapp/frontend/src/tools/loreEditor/LoreEditorPage.tsx`

**Interfaces:**

- Consumes: `ReturnType<typeof createReviewFeed>`, `DEFAULT_FILTERS`, `ReviewFilters`, and review metadata from `reviewFeed.ts`.
- Produces: `ReviewFilters` component with `feed: ReturnType<typeof createReviewFeed>`; all changes call `feed.setFilters()` with a complete `ReviewFilters` value.

- [x] **Step 1: Write focused filter interaction tests**

  Use a feed-shaped test double and assert that search, sort, status, group, visibility, select-all,
  clear-groups, and clear-all interactions call `setFilters` with the expected complete value. Pin the
  four sort values: `name`, `type_path`, `status`, and `reviewed_at`.

- [x] **Step 2: Run the filter test and confirm the component is absent**

  Run:

  ```powershell
  npm --prefix webapp/frontend test -- --run src/tools/loreEditor/ReviewFilters.test.tsx
  ```

  Expected: FAIL because `ReviewFilters.tsx` does not exist.

- [x] **Step 3: Implement `ReviewFilters` by moving, not duplicating, current controls**

  Export one default component:

  ```ts
  export default function ReviewFilters(props: {
    readonly feed: ReturnType<typeof createReviewFeed>;
  })
  ```

  Move the `SORTS`, `STATUSES`, complete-filter update helper, toggle helper, search, status, group,
  sort, visibility, count, and reset markup out of `LoreEditorPage`. Do not change query parameter
  names or feed semantics.

- [x] **Step 4: Replace the inline controls in `LoreEditorPage` with `<ReviewFilters feed={feed} />`**

  Keep load-error notification and focus ownership in the page coordinator. Do not move API access or
  create a second feed.

- [x] **Step 5: Run focused tests**

  Run:

  ```powershell
  npm --prefix webapp/frontend test -- --run src/tools/loreEditor/ReviewFilters.test.tsx src/tools/loreEditor/reviewFeed.test.ts
  ```

  Expected: PASS with paging, request-race, and complete query construction unchanged.

---

### Task 3: Compose the two-pane workspace inside the existing route

**Files:**

- Modify: `webapp/frontend/src/tools/loreEditor/LoreEditorPage.tsx`
- Modify: `webapp/frontend/src/tools/loreEditor/LoreEditor.module.css`
- Modify: `webapp/frontend/src/tools/loreEditor/LoreEditorPage.test.tsx`

**Interfaces:**

- Consumes: `ReviewFilters`, `ReviewList`, `EntryEditor`, `ReviewActions`, `GroupManager`, `Card`, and existing dirty/reload callbacks.
- Produces: one `section[aria-label="Lore review workspace"]` containing queue and authoring panes; the authoring pane owns the existing Review and Group Configuration tabs.

- [x] **Step 1: Add a selected-entry orientation test**

  After selecting a row, change a filter through the rendered controls and assert the selected editor
  remains mounted while the queue reloads. This pins the design rule that a temporary filter mismatch
  does not erase the writer's context.

- [x] **Step 2: Add the compact workspace header and two-pane semantic structure**

  Compose the page as:

  ```tsx
  <section class={styles.workspaceHeader} aria-label="Lore workspace status">
    <div>
      <p class={cardStyles.eyebrow}>Workspace status</p>
      <h2>Writer review desk</h2>
    </div>
    <label class={styles.reviewerField}>
      <span>Reviewer</span>
      <input value={reviewerName()} onInput={updateReviewerName} />
    </label>
  </section>
  <section class={styles.workspace} aria-label="Lore review workspace">
    <Card eyebrow="Review queue" heading="Catalog">
      <section class={styles.queuePane} aria-label="Lore review queue">
        <ReviewFilters feed={feed} />
        <ReviewList feed={feed} selectedId={selected()?.id ?? null} onSelect={selectEntry} />
      </section>
    </Card>
    <Card eyebrow="Selected target" heading={selectedTitle()}>
      <section class={styles.authoringPane} aria-label="Lore authoring surface">
        <div class={styles.tabs} role="tablist" aria-label="Lore editor sections">
          <button type="button" role="tab" aria-selected={activeSection() === 'review'}>Review</button>
          <button type="button" role="tab" aria-selected={activeSection() === 'groups'}>Group Configuration</button>
        </div>
        <div class={styles.authoringScroll}>{authoringSection()}</div>
      </section>
    </Card>
  </section>
  ```

  `selectedTitle()` returns the selected entry's display name or `Entry editor`; `authoringSection()`
  is a local JSX helper that returns the existing `EntryEditor` plus `ReviewActions`, the empty
  selection prompt, or `GroupManager` according to current selection and tab state.

  The queue always remains mounted. The authoring pane shows a useful empty selection message on the
  Review tab and keeps Group Configuration in the same pane. Preserve `selectEntry`, `reloadTarget`,
  `setSelectedContext`, error announcement, and dirty-navigation logic.

- [x] **Step 3: Implement desktop grid and independent pane scrolling**

  Add scoped classes with these responsibilities:

  ```css
  .workspace { display: grid; grid-template-columns: minmax(18rem, 0.34fr) minmax(0, 1fr); }
  .queuePane, .authoringPane { min-height: 0; }
  .queuePane { display: flex; flex-direction: column; }
  .authoringScroll { min-height: 0; overflow-y: auto; }
  ```

  Use a viewport-relative bounded workspace height that leaves room for `AppShell` and the compact
  header. Change `.scroller` from a page-sized `60vh` block to a flexing queue child with a practical
  minimum height. Keep the virtualizer's actual scroll element and `overflow-y: auto` intact.

- [x] **Step 4: Add responsive stacking without a second DOM implementation**

  At the existing narrow breakpoint, switch `.workspace` to one column, give both panes practical
  bounded heights, and retain queue-before-editor DOM order. Do not conditionally render a separate
  mobile tree.

- [x] **Step 5: Make Lore-local buttons content-sized at named action surfaces**

  Apply `width: auto` only through existing scoped classes such as `.tabs`, `.actions`,
  `.filterButtons`, `.footer`, and new named header actions. Do not add a bare `button` rule or change
  `app.css`. Preserve full-width inputs, selects, textareas, and intentional form-width actions.

- [x] **Step 6: Run the page, authoring, and accessibility tests**

  Run:

  ```powershell
  npm --prefix webapp/frontend test -- --run src/tools/loreEditor/LoreEditorPage.test.tsx src/tools/loreEditor/LoreAuthoring.test.tsx src/tools/loreEditor/ReviewList.accessibility.test.tsx
  ```

  Expected: PASS; both panes coexist, the authoring tabs are inside the right pane, and all existing
  authoring contracts remain green.

---

### Task 4: Restore persistent reviewer identity without weakening review records

**Files:**

- Create: `webapp/frontend/src/tools/loreEditor/reviewerIdentity.ts`
- Create: `webapp/frontend/src/tools/loreEditor/reviewerIdentity.test.ts`
- Modify: `webapp/frontend/src/tools/loreEditor/LoreEditorPage.tsx`
- Modify: `webapp/frontend/src/tools/loreEditor/ReviewActions.tsx`
- Modify: `webapp/frontend/src/tools/loreEditor/LoreAuthoring.test.tsx`
- Modify: `webapp/frontend/src/tools/loreEditor/LoreEditorPage.test.tsx`

**Interfaces:**

- Consumes: browser `localStorage`, selected entry review metadata, and existing `ReviewActions` write flow.
- Produces: `readReviewerIdentity(): string` and `writeReviewerIdentity(value: string): void`; `ReviewActions` receives `reviewerName: string` and continues to submit that value as `reviewed_by`.

- [x] **Step 1: Write storage helper tests**

  Pin the storage key `aphelion-lore-reviewer`, trimming behavior on write, empty fallback, and graceful
  behavior when storage access throws.

- [x] **Step 2: Write a page test for identity persistence across record changes**

  Enter `Zoe` in the workspace-header Reviewer field, select and reload a target, and assert the field
  still contains `Zoe`. Assert `localStorage.getItem('aphelion-lore-reviewer') === 'Zoe'`.

- [x] **Step 3: Run the new tests and confirm failure**

  Run:

  ```powershell
  npm --prefix webapp/frontend test -- --run src/tools/loreEditor/reviewerIdentity.test.ts src/tools/loreEditor/LoreEditorPage.test.tsx
  ```

  Expected: FAIL because the helper and header control do not exist.

- [x] **Step 4: Implement the guarded storage helper and page-owned signal**

  Use:

  ```ts
  const REVIEWER_IDENTITY_KEY = 'aphelion-lore-reviewer';

  export function readReviewerIdentity(): string {
    try {
      return window.localStorage.getItem(REVIEWER_IDENTITY_KEY)?.trim() ?? '';
    } catch {
      return '';
    }
  }

  export function writeReviewerIdentity(value: string): void {
    try {
      const reviewer = value.trim();
      if (reviewer) window.localStorage.setItem(REVIEWER_IDENTITY_KEY, reviewer);
      else window.localStorage.removeItem(REVIEWER_IDENTITY_KEY);
    } catch {
      // Browser privacy settings may disable storage; the in-memory identity remains usable.
    }
  }
  ```

  Initialize one `reviewerName` signal in `LoreEditorPage`, render its labeled input in the compact
  workspace header, and persist changes through the helper.

- [x] **Step 5: Make `ReviewActions` consume page-owned reviewer identity**

  Replace its entry-derived reviewer signal with a required `reviewerName` prop. Keep notes derived
  from the selected review record. Show previous review attribution as read-only metadata when present.
  `saveReview` must still reject reviewed or needs-attention decisions when the trimmed identity is
  empty and must send `reviewed_by: props.reviewerName.trim()`.

- [x] **Step 6: Update direct component tests and verify the write payload**

  Pass `reviewerName="Zoe"` to direct `ReviewActions` renders and assert the conflict/write tests still
  exercise the expected hash and proposed record. Add one empty-identity validation assertion.

- [x] **Step 7: Run focused Lore tests**

  Run:

  ```powershell
  npm --prefix webapp/frontend test -- --run src/tools/loreEditor
  ```

  Expected: all Lore Editor tests pass.

---

### Task 5: Reconcile documentation and run static policy gates

**Files:**

- Modify: `references/architecture/codebase-audit-and-recovery-plan.md`
- Modify: `references/writer-guide.md`
- Modify: `references/maintainer-guide.md`
- Modify only if required by documented policy: `tools/docs/check_agent_docs.py`

**Interfaces:**

- Consumes: implemented UI and verified behavior from Tasks 1-4.
- Produces: current writer instructions and architecture status that no longer describe the Lore page as stacked or incomplete in already-delivered areas.

- [x] **Step 1: Update the recovery plan's Lore task and remaining acceptance notes**

  Record the restored two-pane SPA composition, preserved shared architecture, and exact automated
  evidence. Do not mark browser acceptance complete before Task 6.

- [x] **Step 2: Update writer and maintainer guidance**

  Describe the left review queue, right authoring surface, page-level reviewer identity, independent
  scrolling, and Group Configuration tab. Preserve warnings that legacy pages are rollback-only.

- [x] **Step 3: Run documentation, formatting, and type gates**

  Run:

  ```powershell
  python tools/docs/check_agent_docs.py
  python -m ruff check .
  python -m pyright
  npm --prefix webapp/frontend run gen:api
  npm --prefix webapp/frontend run typecheck
  git diff --check
  ```

  Expected: all commands pass and API generation reports no schema drift because this phase does not
  change HTTP models.

---

### Task 6: Run complete automated and writer-facing acceptance

**Files:**

- Modify only for defects found by acceptance: the smallest owning Lore component, test, or scoped stylesheet.
- Regenerate: `webapp/frontend/dist/` through the normal production build.

**Interfaces:**

- Consumes: the completed restored route and existing launcher/server entry points.
- Produces: current automated, production-build, launcher, desktop, narrow-width, keyboard, and workflow evidence.

- [x] **Step 1: Run the complete frontend gate**

  Run:

  ```powershell
  npm --prefix webapp/frontend test -- --run
  npm --prefix webapp/frontend run typecheck
  npm --prefix webapp/frontend run build
  ```

  Expected: all Vitest files pass, TypeScript is clean, and the tracked production SPA builds.

- [x] **Step 2: Run the complete Python gate**

  Run:

  ```powershell
  python -m unittest discover
  python -m ruff check .
  python -m pyright
  ```

  Expected: all Python tests pass with zero Ruff or Pyright findings.

- [x] **Step 3: Launch through the real Windows entry point**

  Run `Launch Aphelion Content Tools.cmd` from `cmd.exe`, confirm the production FastAPI-served SPA
  opens, and record the selected game repository and health state. Do not substitute the Vite dev
  server for this acceptance gate.

- [x] **Step 4: Perform desktop Lore acceptance**

  Confirm in a real visible browser:

  - queue and editor remain simultaneously visible at a normal desktop width;
  - both panes scroll independently;
  - search, every sort, status/group filters, and both visibility toggles work;
  - a catalog row remains selected while its editor is used;
  - shared global search and shared references navigate to the correct target;
  - reviewer identity survives selection and reload;
  - review, assignment, override edit/create, icon preview, AutoWiki, validation, and conflict surfaces remain reachable;
  - compact actions no longer expand into oversized buttons.

- [x] **Step 5: Perform narrow-width and keyboard acceptance**

  Confirm the single DOM tree stacks queue then editor, tab and form focus order is logical, listbox
  selection remains visible, load and error status are announced, and no horizontal page overflow
  hides controls.

- [ ] **Step 6: Exercise destructive endpoints only in disposable data**

  Use a disposable checkout or fixture for override and group deletion. Browser confirmation clicks
  require the user's action-time approval; if unavailable, record the browser confirmation as pending
  while separately reporting the already-tested API behavior.

- [x] **Step 7: Inventory the final working tree**

  Run:

  ```powershell
  git diff --check
  git status --short
  ```

  Report changed files, exact gates, artifacts, browser behaviors, and anything not exercised. Leave
  the working tree uncommitted.

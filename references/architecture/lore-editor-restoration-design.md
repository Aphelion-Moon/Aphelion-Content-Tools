# Lore Editor Restoration Design

## Status

Approved design direction, pending review of this written specification.

## Objective

Make the Solid SPA Lore Editor usable as the first writer-facing acceptance target by restoring the
compact, persistent two-pane workflow of the legacy editor while retaining the architecture and
capabilities introduced by the SPA rewrite.

This is not a legacy rollback. The shipped FastAPI and Solid application remains authoritative.

## Architectural invariants

The restoration must preserve:

- `AppShell` as the only application shell and sidebar owner;
- the tool registry as the route, navigation, accent, and search-entry authority;
- generated OpenAPI TypeScript contracts and the shared typed API client;
- the shared Solid application store, selected context, references, and global search;
- the single live-connection owner and shared notification behavior;
- the virtualized, unbounded catalog browsing model;
- the current canonical-record, optimistic-write, conflict, and reload behavior;
- component-scoped styling and the ban on tool-local bare element selectors;
- all current Lore Editor features unless a feature is deliberately superseded by an equivalent or
  more capable interaction.

The rollback-only files under `tools/lore_editor/web/` remain unchanged as workflow, organization,
and visual references. They do not regain product authority or receive new features.

## Desktop layout

The Lore Editor route has three layers within the existing application shell:

1. A compact workspace header showing catalog status and reviewer identity.
2. The shared selected-context presentation supplied by the application shell.
3. A two-pane Lore workspace that occupies the useful remaining viewport.

The left pane is the persistent review queue. It contains:

- Lore-local search;
- group and review-status filters;
- directional and redundant-entry visibility controls;
- the complete sort selector;
- current result and suppression counts;
- the virtualized catalog list.

The right pane is the persistent authoring surface. Its Review tab contains:

- selected-target identity and status;
- shared open-file and reference actions;
- review notes and review-state actions;
- override creation, editing, validation, conflict resolution, deletion, and reload;
- supported text, special-description, icon, and AutoWiki fields;
- base-versus-override comparison and advanced metadata where applicable.

Its Group Configuration tab contains group listing, creation, editing, and deletion without replacing
the selected catalog context. Switching tabs continues to protect unsaved editor or review changes.

Each pane scrolls independently. Selecting a catalog target must not move the editor below the fold,
and editing a long record must not move the active catalog row out of its pane.

## Responsive behavior

Desktop authoring is the primary workflow. At widths that cannot support both panes without damaging
field readability, the workspace stacks the queue above the editor. The DOM order remains queue then
editor, controls remain keyboard reachable, and selection moves focus to a useful editor heading or
status target without causing unexpected page movement.

Responsive behavior must not introduce a second implementation or an alternate legacy mode.

## Component approach

`LoreEditorPage` remains the route-level coordinator. It owns selected-entry state, section selection,
dirty-state navigation guards, shared-context synchronization, and reload orchestration.

Existing focused components remain the starting point:

- `ReviewList` owns virtualization and catalog-row interaction;
- `EntryEditor` owns override authoring and conflict behavior;
- `ReviewActions` owns review-state editing;
- `GroupManager` owns writer-maintained taxonomy;
- `reviewFeed` owns paging, filtering, sorting, and load state.

The restoration may extract focused filter, workspace-header, or pane components where that reduces
`LoreEditorPage` responsibility. It must not duplicate API access, shared state, notifications,
formatting, references, or open-file infrastructure.

The implementation may replace the current Lore-specific CSS and rearrange component composition.
It must not replace the shared shell or add global CSS to compensate for local layout problems.

## Interaction and data flow

Filter changes continue through `reviewFeed`; the result set and virtualizer update without discarding
the selected record merely because it is temporarily outside the filtered queue. If a deliberate
selection-clearing rule is needed, it must be visible and tested rather than occurring as a side effect
of paging.

Selecting a row updates both local selection and the shared selected context. Global search or a shared
reference may navigate to a Lore type path; the feed resolves that target, loads additional data when
required, selects it, and exposes it in the right pane.

Successful review, override, deletion, and group mutations reload only the affected data while keeping
the writer oriented on the same target when it still exists. Expected-hash conflicts preserve the
current conflict-resolution flow and never silently overwrite another writer's record.

## Control sizing and visual hierarchy

Buttons are content-sized by default. Full-width buttons are reserved for actions that intentionally
span a form or narrow mobile pane. Filter helpers, tabs, review actions, open-file actions, and group
actions remain compact and visually subordinate to the primary save action.

Spacing follows a small, repeated scale within the Lore module. Filter controls are grouped by task;
they must not form a wrapping row of equally prominent oversized blocks. Destructive actions remain
visually and semantically distinct without dominating the editor.

Any shared sizing primitive introduced for this work must solve a demonstrated cross-page need and
must preserve existing consumers. Broad application-wide restyling is deferred to the later page audit.

## Loading, empty, and error states

The two panes distinguish initial loading, incremental loading, no matches, load failure, stale data,
save conflict, validation failure, and successful mutation. Failures continue through the shared
notification surface and have an inline, focusable explanation near the affected control.

An unavailable catalog or game repository must not render as an empty result set. Failed mutations
leave the writer's draft intact and identify what remained unchanged.

## Compatibility and non-goals

Compatibility means retaining the current SPA shell, contracts, state boundaries, integrations, and
features. It does not mean retaining the current stacked Lore page geometry.

This phase does not:

- restore the legacy server or browser pages;
- add a layout-mode toggle;
- remove or bypass shared search or selected context;
- redesign File Management, Home, Parsec, or Content Graph;
- solve the deferred misleading override-group selector beyond keeping its behavior documented;
- begin Tauri integration or the precomputed catalog-distribution work.

## Verification and acceptance

Behavioral tests are added or updated before layout and interaction changes. Focused coverage includes:

- two-pane desktop structure and responsive stacking semantics;
- preservation of virtualization, filtering, sorting, and all visibility controls;
- selection and shared-context synchronization;
- deep-link and shared-reference selection;
- dirty-state protection across row changes, tabs, and navigation;
- review, override, conflict, deletion, icon, AutoWiki, and group workflows;
- loading, empty, and error focus behavior;
- compact control classes without tool-local bare element selectors.

Repository gates remain API generation, frontend tests, typecheck, production build, Python suites,
Ruff, Pyright, and `git diff --check` as applicable.

Writer acceptance uses the production FastAPI-served SPA through the real Windows launcher. The
desktop pass must confirm that the catalog and editor stay simultaneously usable, long panes scroll
independently, sorting matches the legacy choices, shared search/context still navigate correctly, and
no previously available Lore operation disappears. Narrow-width keyboard behavior is checked
separately.

The Lore Editor is accepted before the broader page-by-page spacing, button, and structural audit
continues.

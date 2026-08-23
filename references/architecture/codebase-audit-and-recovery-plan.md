# Aphelion Content Tools: Codebase Audit and Recovery Plan

**Date:** 2026-08-22  
**Status:** Approved for implementation; product decisions recorded 2026-08-22  
**Scope:** Current `main` through `6b523c4`, the SPA rewrite handoff, the standalone migration design and plan, the maintainer and writer guides, and the current working tree

## Executive assessment

The rewrite has a sound shell and a useful test base, but it is not ready for cutover. The largest problem is not missing UI polish: the current persistence model makes writer changes invisible to Git. LanceDB is the only persistent source for authoring data, its directory is ignored, and it is shared across branch changes in a checkout. A saved record therefore cannot be reviewed in a pull request, recovered from a fresh clone, or reliably associated with the Git commit recorded in an export manifest.

LanceDB should remain in the product. It is a good local search and materialized-view layer for the roughly 21,000 catalog and graph records currently observed. It should not be the Git merge format or the sole authority for collaboratively authored records.

The recommended recovery is:

1. Fix the confirmed data-loss and concurrency defects before adding features.
2. Restore deterministic, one-record-per-file Git data as the collaboration authority.
3. Rebuild or incrementally synchronize a worktree-scoped LanceDB projection from those records.
4. Finish API typing and SPA feature parity before retiring the legacy UI.
5. Prototype packaging with the real native dependencies before committing to the Tauri release architecture.

This preserves the writer-facing branch and pull-request workflow from the approved standalone design while keeping LanceDB for fast filtering, full-text search, semantic search, and graph projections.

## Evidence snapshot

The following checks were run against the current working tree:

- Solid frontend tests: 40 passed.
- Solid frontend production build: passed after rerunning outside the restricted sandbox because `esbuild` could not execute there.
- Lore Editor Python suite: 133 passed.
- Content Graph Python suite: 43 passed.
- Web application Python suite: 138 passed, but took about 225 seconds because unit tests repeatedly perform real embedding work.
- `git diff --check`: passed.
- Ruff: failed with 18 findings. These include unused variables and simplification findings in production and test code, not merely historical legacy formatting.
- Pyright: not run because the declared development dependency is not installed in the active environment.
- CI: no checked-in GitHub Actions or equivalent continuous-integration configuration was found.
- Working tree: clean; local `main` is eight commits ahead of `origin/main`.

Passing tests do not cover the critical persistence, concurrency, branch-isolation, and browser-parity failure modes identified below.

## Findings

### P0: data integrity and collaboration blockers

#### Writer data is outside Git

`tools/lore_editor/workspace.py` and `tools/lore_editor/source.py` make LanceDB the actual home of targets, overrides, groups, reviews, and assignments. `.gitignore` excludes `webapp/store/data`. Git status and commit operations only see filesystem paths.

Consequences:

- Saving authoring data can leave the repository clean.
- Switching branches in one checkout continues to use the same database.
- A fresh clone creates empty tables rather than reconstructing the committed state.
- A pull request cannot show or merge the records that produced an exported DM artifact.
- Export provenance records a Git `HEAD` that does not contain the authored data.
- There is no canonical backup, restore, import, or materialization command.

The current local store contains catalog and graph projections but no overrides, groups, reviews, assignments, or manifests. Commit `8f65061` removed the previous committed catalog, eight group records, one review record, and the JSON migration path. Those records remain recoverable from Git history but are not present in the current database.

#### Predicate construction permits destructive record IDs

Record identifiers are interpolated into LanceDB filter expressions. Runtime validation does not enforce the schema's safe identifier pattern. A temporary-store reproduction confirmed that a crafted entry ID can cause a delete operation to match unrelated overrides.

This is a data-loss vulnerability even though the application is local-only. Every database predicate must be built through a single escaping or typed-filter boundary, and identifier constraints must be enforced by Pydantic at the HTTP boundary and again in the domain layer.

#### Snapshot refresh can silently retain stale fields

`sync_snapshot()` uses a hash of search text to decide whether an entire row changed. Fields omitted from search text—such as field profiles, editable roots, parent types, and icon metadata—can change without causing the row to be updated. A temporary-store reproduction confirmed this behavior.

The store needs two independent hashes:

- `record_hash`: canonical serialization of the complete logical record and promoted columns.
- `embedding_hash`: normalized search text plus embedding model and vector-schema version.

#### No optimistic concurrency or atomic authoring boundary

Save and delete requests do not include an expected revision or content hash. The backend reads, validates, mutates LanceDB, regenerates DM, and manually rolls back without a shared transaction or lock. Concurrent requests are last-writer-wins, and a failed request can restore an older row over a successful concurrent write.

The background worker serializes worker jobs only. It does not serialize FastAPI mutations.

#### Review and assignment keys can collide

The current slug function maps distinct valid type paths such as `/obj/a_b` and `/obj/a/b` to the same key. Reviews and assignments use that lossy slug as their merge key, so saving one can overwrite the other. Use the canonical type path as the logical key and a reversible or collision-resistant filename encoding for Git records.

### P1: stale reads, search correctness, and unsafe repository operations

#### Cross-process freshness is knowingly incomplete

The in-process generation counter cannot observe worker writes, but Lore Editor caches use it as their only version. A catalog refresh in the worker can leave the review feed stale until an unrelated API-process write or restart.

LanceDB connections are cached and opened with the default read-consistency behavior. LanceDB documents that cross-process freshness requires an explicit consistency interval or refresh policy. The app needs one process owning mutations, or a durable revision visible to every process, plus explicit table refresh semantics.

References:

- <https://docs.lancedb.com/tables/consistency>
- <https://docs.lancedb.com/tables/schema>

#### Search does not enforce a global result limit

Search performs full-text and vector fusion separately for every table, takes `limit` from each table, and concatenates the results. `/api/search?limit=6` can therefore return many more than six results, ordered by table rather than global relevance. Query embeddings are also recomputed once per table.

Compute the query vector once, collect candidates, normalize or rank-fuse across all requested tables, globally sort, and apply one final limit. Report semantic-search degradation instead of silently substituting zero vectors for the lifetime of the process.

#### Dirty-game-checkout protection can be bypassed

The export API and SPA expose a client-controlled `force` flag that permits applying generated output to a dirty Meridian-Rift checkout. This contradicts the earlier hard-stop safety requirement and can mix unrelated game changes into a lore export.

Remove the force path. Require a clean target checkout and give the writer explicit recovery instructions through GitHub Desktop.

#### Repository commit scope is too broad and can be incomplete

The SPA commits every path returned by repository status. Writers cannot select files, distinguish tool-owned content from unrelated changes, or preview the exact staged set. Status is capped, so a very large change set may be only partially committed without a sufficiently strong warning.

Commit operations should accept only validated, selected paths under owned content roots. The UI must show the exact files and record summaries before committing.

### P1: SPA feature parity and contract gaps

#### Lore Editor is a catalog browser, not a port

The new page provides filters, paging, selection, and record details. It does not yet provide the legacy application's authoring capabilities:

- create and edit overrides;
- validate, save, and delete entries;
- review state and notes;
- create and edit groups;
- manual group assignment;
- icon file/state editing and preview;
- opening the corresponding definition.

The legacy launcher still starts the legacy application. Cutover must wait for explicit parity acceptance, not just component presence.

#### Content Graph is not integrated

The graph engine foundation is present in an unimported commit state, but the page remains a placeholder and the planned rendering dependencies are absent. The implementation needs a measured renderer decision rather than automatically adding D3, Graphology, and Sigma together.

Recommended split:

- Graphology only if its algorithms or data model replace meaningful custom code.
- D3 utilities only for scales, layouts, or geometry actually used.
- Sigma only after a realistic-node-count WebGL spike proves it works in the target WebView2 environment.

Avoid overlapping libraries that each own the graph model or layout lifecycle.

#### HTTP typing is partial

The backend still exposes raw dictionaries and `object` responses for important Lore, Graph, Search, live-status, and manifest routes. The frontend manually duplicates review models and casts JSON to generic types without runtime validation. The frontend `ApiError` also discards the backend's stable error code.

Finish Pydantic request and response models first. Generate and check in the TypeScript contract, verify regeneration in CI, and preserve structured error codes in the client. Add runtime validation only at untrusted or version-sensitive boundaries; do not duplicate every Pydantic model in handwritten TypeScript.

#### The review feed can deadlock during a filter change

If filters change while a request is in flight, the new fetch returns because `loading()` is true. The old generation then refuses to clear loading, leaving the feed permanently stuck. Use an `AbortController` or generation-owned pending state and add a deferred-request regression test.

The visible filter values are also inconsistent with the backend. The SPA sends `approved` and `needs_work`; the backend recognizes `reviewed` and `needs-attention`. Contract generation alone will not catch this while the field remains an unconstrained string. Define the states as one backend enum and consume its generated type.

#### Unknown API paths are served as successful HTML

FastAPI's SPA catch-all currently serves `index.html` for unmatched `/api/...` paths. The frontend client treats a successful non-JSON response as an empty object. A misspelled or removed endpoint can therefore appear to succeed with empty data.

Exclude `/api` and `/ws` from the SPA fallback, return a real JSON 404, and make the HTTP client reject unexpected response content types.

#### Search navigation loses record context

Global Search routes to the owning tool but does not carry the selected record. Add typed deep links or shared selection intents so a search result opens the exact Lore or Graph entity.

#### Browser testing is too narrow

There are unit tests but no end-to-end coverage of the shipped browser path. Add Playwright coverage for critical SPA flows and a visible WebView2 or headed-browser smoke test for WebGL behavior. Hidden-browser `requestAnimationFrame` behavior must not be treated as evidence that the graph renderer works for users.

#### Content Graph's foundation already has correctness defects

With both grouping axes disabled, the engine creates one cluster and divides by a near-zero `sin(pi)` term, producing an extreme anchor radius. The engine also claims deterministic placement but uses unseeded `Math.random()`. There are no tests for the graph engine.

Special-case zero/one cluster, inject a seeded random source, and cover layout, filtering, force membership, cancellation, and cleanup before wiring the renderer. Decide explicitly whether filtering changes layout physics or renderer visibility; the legacy implementation accidentally leaves hidden nodes exerting forces.

#### Some legacy capabilities are missing from the cutover inventory

Shared References and Modular Debug do not have replacement or retirement decisions in the current handoff. Parsec's announcement surface is disconnected from application announcements, and its legacy motion settings are not exposed. These must appear in the parity matrix so deleting legacy assets cannot silently delete functionality.

#### Active jobs cannot reattach after navigation

`ToolRunner` keeps run ID, output, polling, and stop state inside the routed component. Navigating away disposes that state; returning cannot reattach to the shared active run. Use a server-state cache keyed by repository and run ID, with WebSocket invalidation and explicit reattachment. TanStack Solid Query is justified here; Solid stores should continue to hold UI preferences and cross-component intent rather than remote-resource lifecycles.

### P1: runtime, packaging, and security

#### Two servers and two application architectures remain live

`webapp/server.py` remains a large legacy router while the FastAPI application exists alongside it. `Launch Lore Tools.cmd` still launches the legacy entry point. This duplicates behavior and makes parity claims difficult to verify.

Keep the legacy entry point only as a temporary comparison gate. New behavior belongs behind typed FastAPI routes. Delete the legacy server and shims only after a recorded parity matrix passes through the real launcher.

#### Worker ownership is not repository-safe

Tool-run lookup and cancellation use a mutable global default repository root. Multiple application roots or tests can query the wrong worker. Worker output is discarded on startup failures, and cancellation is cooperative only when output is emitted.

Make every run operation explicitly repository-scoped. Prefer a single API-owned job manager unless isolation is demonstrated to be necessary. If the worker remains, use a repo-scoped durable protocol, surface startup logs, and make cancellation independent of output writes.

#### Local API trust is implicit

The loopback API has no per-launch authentication token or strict Origin/Host policy. WebSocket connections expose live state without origin validation. This becomes more important when a desktop sidecar is installed and predictable local ports or endpoints exist.

Use a random per-launch token passed to the SPA, validate Host and Origin, and apply the same authentication to HTTP and WebSocket connections.

#### Tauri process guarantees are not yet proven

Killing a Python sidecar does not by itself guarantee that a Python-spawned worker process exits on Windows. Before claiming orphan-free shutdown, either remove the grandchild worker or demonstrate process-tree ownership through a Windows Job Object or equivalent tested mechanism.

#### Dependency and release setup is not reproducible

- Python requirements are split across `pyproject.toml` and the legacy launcher requirements file.
- The launcher checks for Python and Pillow but can select an interpreter missing LanceDB, FastEmbed, FastAPI, Uvicorn, or Pydantic.
- There is no Python lock with hashes.
- A fresh frontend checkout lacks the ignored generated API types required by the build.
- The new SPA distribution is ignored and the user-facing launcher still serves the legacy UI.
- There is no CI or release workflow.
- Tauri signing and updater-key management are not designed. Tauri updater signatures are mandatory, and Windows code signing is needed for a credible release experience.

The current Python package configuration is also incomplete: it explicitly includes only the top-level `webapp` and `tools` packages, omitting their subpackages and runtime resources. Source-tree and editable installs mask this. An installed wheel smoke test must run outside the repository before PyInstaller work.

The desktop transport is undecided. Relative HTTP and WebSocket URLs work when the SPA is served by FastAPI, but not automatically when Tauri loads assets from its custom protocol. Prefer navigating the desktop window to the authenticated loopback FastAPI origin unless a narrowly scoped Tauri-command architecture provides a concrete security or packaging advantage.

References:

- <https://v2.tauri.app/plugin/updater/>
- <https://v2.tauri.app/distribute/sign/windows/>
- <https://v2.tauri.app/distribute/pipelines/github/>
- <https://pyinstaller.org/en/stable/>

### P2: performance, accessibility, and documentation

- Webapp unit tests repeatedly load or execute real embeddings. Inject a deterministic fake for unit tests and retain a small, separately marked native integration suite.
- Store-health polling walks the database directory every two seconds while clients are connected. Replace it with durable revision state or coalesced event publication.
- Tool output still polls every 750 ms even though WebSocket infrastructure exists. Publish run deltas or make polling intentionally coarse and documented.
- Global Search needs combobox/listbox semantics, keyboard traversal, focus management, and announced result state.
- Production source maps should be an explicit release decision.
- The README, maintainer guide, writer guide, tool definitions, and handoff contradict the current persistence and launcher behavior. Documentation must describe verified behavior and label transitional behavior plainly.

## LanceDB multi-writer branch and pull-request workflow

### Approved authority model

Use deterministic Git files as the collaboration authority and LanceDB as a rebuildable, worktree-scoped materialized view.

```text
Git branch/worktree
  tools/lore_editor/catalog/manifest.json
  tools/lore_editor/catalog/targets.json              generated or seeded
  tools/lore_editor/content/overrides/<id>.json       authored
  tools/lore_editor/content/groups/<id>.json          authored
  tools/lore_editor/content/reviews/<key>.json        authored/shared if approved
  tools/lore_editor/content/assignments/<key>.json    authored/shared if approved
            |
            | deterministic reconcile by record_hash
            v
Local cache outside Git or under ignored runtime data
  LanceDB tables + schema version + embedding version
            |
            +--> search, paging, graph projection, semantic ranking
            +--> generated DM and AutoWiki artifacts
```

LanceDB remains central to the runtime workflow, but corruption or branch changes are recoverable because the authoritative inputs are reviewable text.

### Writer workflow

1. The application verifies that the tool repository is on a named branch and records its `HEAD`, worktree identity, and content revision.
2. Pull or branch switching is performed in GitHub Desktop. The application detects the changed `HEAD` and content tree, pauses writes, and reconciles LanceDB before resuming.
3. Loading a record returns `record_hash` and the current Git-relative source path.
4. Saving sends `expected_record_hash` plus the proposed record.
5. The backend acquires a repository-scoped write lock, rereads the authoritative file, and returns HTTP 409 with base/current/proposed data if the hash changed.
6. The backend validates the full candidate collection, atomically replaces the one JSON file, and regenerates the deterministic artifact.
7. LanceDB is updated after the durable file write. An indexing failure marks the projection stale but does not discard the authored change; rebuilding restores it.
8. File Management shows only tool-owned changed records by default, with explicit selection and summaries.
9. The writer commits locally and opens the branch in GitHub Desktop to push and create the pull request.
10. CI validates schemas, uniqueness, cross-record ownership, deterministic generation, and that the generated artifact matches the committed records.
11. Git resolves changes to different record files normally. Same-record text conflicts are resolved through Git or a future three-way record merge UI; the application never silently picks one side.

### File and key rules

- One logical authored record per canonical JSON file.
- UTF-8, LF, stable key ordering, two-space indentation, and exactly one trailing newline.
- Filenames are reversible encodings or collision-resistant digests of canonical IDs; they are not lossy slugs.
- The ID inside the file remains authoritative and is checked against its path.
- Deletes use Git deletion, not hidden database tombstones, unless reviews/assignments are intentionally moved to an event ledger later.
- Catalog and graph snapshots carry schema version, generator version, source-game commit, complete-record hash, and embedding-version metadata.
- LanceDB cache paths include worktree identity, content revision/schema version, and embedding version. Cache reuse is allowed only after validation.

### Conflict policy

The first implementation should reject any same-record hash mismatch. It is easy to explain, deterministic, and safe. The 409 response should contain enough data for a side-by-side diff and retry after reload.

Field-level auto-merge can be added later only if real writer conflict frequency justifies it. Automatic merging before the record schema is fully typed would create more risk than value.

### Approved operating decisions

- Reviews and assignments are shared, Git-tracked pull-request content.
- Catalog data is distributed as a versioned, hash-verified release seed. A local rebuild is the fallback. Catalog snapshots do not appear in ordinary writer pull requests.
- Multi-writer collaboration uses separate branches and worktrees. Exactly one backend may mutate a selected workspace at a time; multiple browser tabs attach to that backend rather than opening competing writers.
- The eight groups removed in `8f65061` are restored after validation. The removed review is not restored.
- The dirty-game-checkout force path is removed. A dirty game checkout is always a hard stop.
- Hybrid full-text and semantic search remains a cornerstone. Model unavailability produces visible, non-destructive keyword-only mode; it never replaces valid vectors with zeros.
- Selected context boosts related search results but never silently removes global matches. Explicit scope controls may filter when the writer asks them to.
- All legacy capabilities receive an explicit keep or replace implementation. No capability is removed implicitly during cutover.
- The application may create strictly scoped local commits. GitHub Desktop continues to own authentication, pull, push, pull requests, and complex merges.

### Alternatives considered

#### Append-only Git event ledger

Every mutation becomes an immutable event file and LanceDB reduces the events into current state. This improves audit history and reduces direct file conflicts, but requires deterministic event ordering, tombstones, compaction, and a conflict-aware reducer. It is a valid later evolution, not the shortest safe recovery.

#### LanceDB-authoritative with a transactional Git outbox

Every database mutation would also create a deterministic Git export, and branch changes would import those exports into a branch-specific database. This retains database authority but creates dual-state recovery and requires an application-level journal because the current tables do not provide one transaction across the authoring and Git projections. Choose this only if database authority is a firm requirement.

#### Tracking LanceDB fragments in Git or Git LFS

Rejected. Lance fragments and version metadata are not useful human diffs, do not merge at record granularity, and create database-file conflicts between otherwise independent writer changes.

## Implementation plan

Each task starts with a failing focused test, implements the smallest behavior needed to pass, runs the focused gate, and then runs the phase gate. No source implementation should begin until the authority model and shared/private review decisions are answered.

### Phase 0: preserve and establish a baseline

#### Task 0.1: Preserve recoverable content

**Files:** Git history around `8f65061`; `tools/lore_editor/content/`; `tools/lore_editor/catalog/`; new recovery fixture under `tools/lore_editor/tests/fixtures/`.

- Export the current LanceDB authoring tables to a timestamped read-only recovery bundle, even if empty.
- Recover the eight deleted groups from the parent of `8f65061` into a reviewable staging directory. Do not restore the deleted review.
- Compare recovered data with any other known writer copy before placing it on `main`.
- Record row counts and hashes. Do not overwrite current data during recovery.

**Gate:** recovery export/import round-trip test and human review of the recovered records.

#### Task 0.2: Freeze the verified baseline

**Files:** `pyproject.toml`; `webapp/frontend/package.json`; new `.github/workflows/ci.yml`; test configuration files.

- Add Windows CI for Python tests, Ruff, Pyright, frontend tests, frontend build, OpenAPI regeneration drift, and `git diff --check`.
- Split fast unit tests from native embedding and packaging integration tests.
- Add deterministic test embeddings.
- Resolve the existing Ruff findings and make the declared Pyright command runnable.

**Gate:** a clean checkout passes the same commands locally and in Windows CI.

### Phase 1: eliminate immediate data-loss paths

#### Task 1.1: Centralize identifiers and safe filters

**Files:** `webapp/api/models.py`; `tools/lore_editor/validation.py`; `webapp/store/db.py`; `tools/lore_editor/api.py`; `tools/lore_editor/taxonomy.py`; corresponding tests.

- Define typed canonical IDs and type paths in Pydantic/domain models.
- Remove raw caller-supplied predicate interpolation.
- Replace lossy review and assignment keys with canonical or collision-resistant keys.
- Add regression tests for quotes, predicate operators, slash/underscore collisions, and unrelated-row preservation.

**Gate:** destructive-ID and key-collision reproductions fail before the change and pass afterward.

#### Task 1.2: Correct snapshot hashing and schema metadata

**Files:** `webapp/store/schema.py`; `webapp/store/db.py`; `webapp/store/embeddings.py`; `tools/lore_editor/catalog.py`; `tools/content_graph/scanner.py`; store tests.

- Add `record_hash`, `embedding_hash`, store-schema version, and embedding-model version.
- Update rows whenever complete logical content changes, even if search text does not.
- Re-embed only when the embedding hash changes.
- Detect incompatible tables and rebuild or migrate explicitly.
- Make degraded semantic search observable through health/status APIs.

**Gate:** unchanged-text/changed-record regression, model-version migration, and unavailable-embedding tests pass.

#### Task 1.3: Correct API fallback and Lore filter contracts

**Files:** `webapp/api/app.py`; `webapp/api/models.py`; `webapp/frontend/src/lib/api.ts`; `webapp/frontend/src/tools/loreEditor/LoreEditorPage.tsx`; tests.

- Return JSON 404 for unmatched API and WebSocket routes.
- Reject successful responses with unexpected content types.
- Define review states as a backend enum and use generated values in the SPA.
- Add regression tests for unknown endpoints and every visible filter.

**Gate:** no unknown API call can resolve as an empty success; every filter has backend coverage.

#### Task 1.4: Remove unsafe export override

**Files:** `tools/lore_editor/export.py`; `webapp/api/models.py`; `webapp/api/routes/export.py`; `webapp/frontend/src/tools/fileManagement/ExportPanel.tsx`; tests and guides.

- Remove the client-controlled dirty-checkout bypass.
- Return a typed 409 conflict with recovery instructions.
- Preserve the three-step prepare/inspect/apply sequence.

**Gate:** dirty checkouts cannot be mutated through any public entry point.

### Phase 2: restore Git-canonical collaboration

#### Task 2.1: Define canonical record models and serialization

**Files:** new `tools/lore_editor/models.py`; new `tools/lore_editor/serialization.py`; `webapp/api/models.py`; JSON schemas if external validation remains useful; tests.

- Model overrides, groups, reviews, assignments, catalog manifests, and source references explicitly.
- Define canonical JSON serialization and record hashes.
- Validate IDs, paths, owned fields, icon references, AutoWiki fields, and cross-record uniqueness.
- Keep LanceDB row encoding as a projection adapter, not the domain model.

**Gate:** canonical serialization is byte-stable and rejects unknown or unsafe data at the boundary.

#### Task 2.2: Implement materialization and reconciliation

**Files:** new `tools/lore_editor/reconcile.py`; new `webapp/store/migrations.py`; `webapp/store/db.py`; `webapp/store/schema.py`; CLI commands in `webapp/store/cli.py`; tests.

- Import canonical Git records into LanceDB by complete-record hash.
- Export a recovery snapshot from LanceDB without claiming it is canonical.
- Detect additions, changes, deletions, schema drift, branch/HEAD changes, and cache corruption.
- Build into a new database generation and atomically switch the active projection instead of deleting rows before a partial rebuild.
- Scope runtime databases by worktree identity and validated content/schema/model revision.
- Provide `status`, `reconcile`, `rebuild`, `backup`, and `restore` commands.

**Gate:** fresh clone, branch switch, interrupted rebuild, backup/restore, and corrupt-cache recovery tests pass.

#### Task 2.3: Add optimistic writes and one mutation owner

**Files:** `tools/lore_editor/api.py`; `webapp/api/models.py`; `webapp/api/routes/lore.py`; new repository write coordinator; `webapp/tooling.py` or its replacement; tests.

- Require `expected_record_hash` for update and delete operations.
- Use a repository-scoped write coordinator and atomic file replacement.
- Validate the candidate collection before publishing the file.
- Regenerate deterministic artifacts from canonical records.
- Update LanceDB after durability; mark it stale and schedule rebuild if projection fails.
- Return typed 409 base/current/proposed conflict data.

**Gate:** two-client same-record tests prove no silent overwrite; different-record concurrent writes remain safe.

#### Task 2.4: Make Git operations record-aware

**Files:** `webapp/git_adapter.py`; relevant FastAPI routes/models; `webapp/frontend/src/tools/fileManagement/RepositoryPanel.tsx`; tests.

- Restrict app commits to selected files under owned content/generated roots.
- Show exact record summaries and generated artifacts before commit.
- Detect branch/HEAD changes and block writes until reconciliation completes.
- Include the canonical content revision and source-game commit in export provenance.
- Continue handing authentication, push, pull, merge, and PR creation to GitHub Desktop.

**Gate:** every authoring mutation appears in Git status and a fresh clone at the commit reproduces identical generated output.

### Phase 3: make the FastAPI and Solid stack internally consistent

#### Task 3.1: Complete the API contract

**Files:** `webapp/api/models.py`; all `webapp/api/routes/*.py`; `webapp/frontend/src/lib/api.ts`; generated `webapp/frontend/src/lib/api-schema.d.ts`; tests.

- Replace public raw dictionaries and `object` responses with Pydantic models.
- Normalize 400/404/409/422/500 mappings and stable error codes.
- Preserve error codes in the frontend.
- Check in generated TypeScript API types and fail CI on regeneration drift.
- Remove manual frontend copies of API response shapes.

**Gate:** OpenAPI schema tests cover every public route and the frontend builds from a fresh checkout.

#### Task 3.2: Correct shared search and live state

**Files:** `webapp/store/search.py`; `webapp/store/embeddings.py`; search API models/routes; `GlobalSearch.tsx`; `webapp/api/live.py`; tool-run components; tests.

- Embed a query once.
- Fuse candidates across tables and enforce one global result limit.
- Expose degraded semantic search.
- Add typed record deep links and selection intents.
- Publish useful job deltas over WebSocket or deliberately reduce and document polling.
- Replace directory-walk freshness checks with durable projection revision events.

**Gate:** global ranking/limit, degraded mode, deep-link, and reconnect tests pass.

#### Task 3.3: Consolidate job ownership

**Files:** `webapp/tooling.py`; `webapp/store_worker.py`; `webapp/api/routes/tools.py`; `webapp/api/context.py`; tests.

- Remove the mutable default repository root.
- Pass repository identity to every start/get/stop operation.
- Decide from measured memory/failure behavior whether jobs remain out of process.
- Surface startup diagnostics and make cancellation independent of output writes.
- If the worker remains, configure explicit LanceDB consistency and durable revisions.

**Gate:** two-repository isolation, cancellation, crash recovery, and stale-read tests pass.

**Implemented 2026-08-22:** The worker remains out of process because the measured model cold-load and
failure-isolation costs justify it. RPCs now carry and validate the resolved repository path; run state and
startup diagnostics are durable; silent Python execution is cancellable; interrupted runs recover as
failed rather than disappearing; LanceDB reads use strong cross-process consistency; and Lore Editor
caches include the durable projection generation. Focused two-repository, cancellation, worker-crash,
external-write, and cache-invalidation tests cover the gate. Native calls remain cancellable only after
they return to Python; forced process-tree ownership is still part of the desktop packaging spike in Task
5.1.

### Phase 4: finish SPA parity

#### Task 4.1: Fix paging races and accessibility foundations

**Files:** `webapp/frontend/src/tools/loreEditor/reviewFeed.ts`; its tests; `GlobalSearch.tsx`; shared controls/styles.

- Abort or supersede in-flight feed requests safely.
- Add the filter-change-during-request regression test.
- Implement combobox/listbox keyboard and focus behavior.
- Add accessible status announcements and error focus handling.

**Gate:** unit tests plus automated accessibility checks for shell, search, and feed.

#### Task 4.2: Port complete Lore Editor authoring

**Files:** `webapp/frontend/src/tools/loreEditor/`; typed Lore routes/models; component tests; E2E tests.

- Create/edit/delete overrides with expected-hash conflict handling.
- Add validation issue presentation and unsaved-change guards.
- Port review notes/status, group CRUD, and manual assignment.
- Port icon file/state selection, preview, and definition navigation.
- Add side-by-side conflict presentation before considering auto-merge.

**Gate:** an explicit legacy/new parity matrix passes through the real writer workflow.

**Implemented in the SPA 2026-08-22:** Override create/edit/delete, validation, reviews, manual
assignments, group CRUD, icon and AutoWiki fields, exact source navigation, Shared References,
multi-select filters, unsaved-change protection, and side-by-side optimistic-conflict handling are
implemented and component/API verified. The explicit inventory is
`references/architecture/lore-editor-spa-parity-matrix.md`. The real-browser and launcher rows remain
open and are intentionally deferred to Task 4.4 rather than claimed as a passed writer-workflow gate.

#### Task 4.3: Implement Content Graph deliberately

**Files:** `tools/content_graph/`; `webapp/api/routes/graph.py`; `webapp/frontend/src/tools/contentGraph/`; dependency manifests; unit/component/E2E tests.

- Import and test the existing engine foundation.
- Fix zero/one-cluster placement and replace unseeded randomness with an injected deterministic source.
- Decide and test whether filters alter force membership or visibility only.
- Define graph API models and incremental query boundaries.
- Benchmark SVG/canvas/WebGL candidates with realistic node and edge counts in visible WebView2.
- Add only the libraries selected by the benchmark.
- Implement graph navigation, filtering, selection, record deep links, and accessible tabular fallback.

**Gate:** pure engine tests, performance budget, visible renderer smoke test, and cross-tool deep links pass.

**Implemented and measured 2026-08-23:** Sigma 3 + Graphology 0.26 + d3-force 3 now provide the
renderer and bounded simulation. Pure layout/filter/scope/simulation/renderer regressions pass. The
authoritative 30,331-node / 31,375-edge graph and a 41,703-node fallback worst case rendered visibly in
WebView2 with no console errors; full-scope activation measured about 2.45 s and 3.67 s respectively.
The compact self-contained snapshot plus null exclusion and gzip reduced `/api/graph` from 24.49 MB /
3.4 s to 10.16 MB / 0.37 s uncompressed or 0.80 MB / 0.45 s compressed. Exact graph deep links now
restore shared selected context and visibly drive related-result boosts. Full evidence and retained
manual playtest items are in `references/architecture/content-graph-renderer-decision.md`.

#### Task 4.4: Cut over the shipped browser entry point

**Files:** `Launch Lore Tools.cmd`; `webapp/serve.py`; `webapp/serve_api.py`; `webapp/api/app.py`; frontend build/release scripts; guides.

- Build the SPA deterministically as part of development and release gates.
- Point the real launcher at FastAPI plus the built SPA.
- Run writer E2E scenarios through `Launch Lore Tools.cmd`.
- Keep a short rollback window, then delete `webapp/server.py`, legacy web assets, and dual import shims.

**Gate:** all accepted parity scenarios pass through the launcher on a clean Windows checkout.

**Cut over 2026-08-23:** The shipped `.cmd` now starts `webapp/serve_api.py`. The minified SPA is a
tracked deterministic artifact, CI rebuilds and checks it for drift, and the launcher fails clearly if
the artifact is missing. The real `.cmd -> PowerShell -> FastAPI -> SPA` path loaded the authoritative
graph revision, selected-node context/search, the 17,500-target Lore catalog, restored groups, and
authoring controls; stopping the launcher closed its listening port. Legacy assets remain during the
rollback window and have not been deleted.

#### Task 4.5: Resolve remaining legacy surfaces

**Files:** shared shell components; Parsec components/store; Content Graph or replacement modules; parity matrix and E2E tests.

- Keep, replace, or explicitly retire Shared References and Modular Debug.
- Connect application announcements to Parsec's visible feedback surface.
- Restore or intentionally retire Parsec motion/settings controls.
- Persist and reattach active tool runs across route navigation through repository/run-keyed server state.

**Gate:** every legacy route and control has an accepted keep, replace, or retire result, with no undocumented loss at deletion time.

**Implemented 2026-08-23:** Shared References remains in the persistent shell; Modular Debug is
integrated into Content Graph; application announcements now drive Parsec's visible bubble; Parsec's
three-way motion preference is exposed and persisted; and File Management reattaches to repository
active runs after route navigation. Each behavior has component coverage.

### Phase 5: packaging and release

#### Task 5.1: Run a packaging spike before product integration

**Files:** isolated packaging configuration under `packaging/`; dependency lock files; spike report under `references/architecture/`.

- Build a PyInstaller `onedir` FastAPI sidecar with LanceDB, PyArrow, FastEmbed/ONNX, NumPy, and Pillow.
- Test first start without network, model availability, store rebuild, DMI preview, catalog refresh, and clean shutdown.
- Measure installed size, cold start, memory, and rebuild time.
- Prove that no child or grandchild process survives forced and normal shutdown.

**Gate:** a documented go/no-go decision with measurements. Reconsider embedding or worker architecture if the bundle is not viable.

#### Task 5.2: Add Tauri only after the spike passes

**Files:** new Tauri application; sidecar bootstrap/authentication; Windows installer configuration; E2E smoke tests.

- Add folder pickers, native notifications, logging, and explicit recovery screens.
- Use a per-launch API token and strict Host/Origin validation.
- Own the entire process tree.
- Preserve GitHub Desktop handoff for credentials and PR operations.

**Gate:** installed-app smoke test on a clean supported Windows machine.

#### Task 5.3: Build the release pipeline

**Files:** release workflow; signing/updater configuration; release runbook.

- Choose MSI or NSIS based on the measured deployment environment.
- Configure Windows code signing.
- Create and securely back up the Tauri updater signing key; store only the public key in the app.
- Produce signed artifacts, checksums, update metadata, and rollback instructions.
- Test upgrade and failed-update recovery.

**Gate:** signed test release installs, updates, rolls back, and leaves no orphan process.

### Phase 6: documentation and final acceptance

#### Task 6.1: Reconcile every guide with verified behavior

**Files:** `README.md`; `references/maintainer-guide.md`; `references/writer-guide.md`; architecture handoffs; `.agents/` where this repository needs its own guidance.

- State which data is authoritative and which is derived.
- Document branch switching, conflicts, backup/restore, GitHub Desktop handoff, and clean game-export requirements.
- Remove obsolete source paths and launcher claims.
- Add contributor setup, test, schema-generation, packaging, and recovery commands.

**Gate:** a new writer and a new maintainer can complete their respective quick-start checklists from clean machines.

#### Task 6.2: Final acceptance

- Run all Python and frontend tests, lint, type checks, schema drift, deterministic generation, browser E2E, launcher E2E, and installed-app smoke tests.
- Exercise two branches editing different records and the same record.
- Verify fresh-clone reconstruction, backup/restore, branch switching, dirty-checkout refusal, and an updater rollback.
- Record measured timings and distinguish focused gates from the complete release gate.

## Resolved questions

The product decisions above resolve the authority, shared-state, catalog-distribution, concurrency, recovery, export-safety, semantic-search, selected-context, and parity questions. Implementation may proceed.

Release signing ownership, exact supported toolchain versions, and the Content Graph filter-physics choice remain phase-specific decisions. They do not block the data-integrity and collaboration foundation.

## Ready state

The audit and recovery plan are approved. Phase 0 through Phase 2 may proceed. No source files were changed as part of the audit itself.

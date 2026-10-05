# Platform repair and expansion implementation plan

Date: 2026-08-27

Source audit:
[Platform life-cycle audit](../../../references/architecture/2026-08-27-platform-lifecycle-audit.md).

Status: proposed implementation sequence. No product implementation in this plan is complete merely
because the plan exists.

## Objective

Turn Aphelion Content Tools into a revision-correct integration platform before adding multiple
Meridian-Rift editors. The implementation retains FastAPI, Solid, Pydantic, the out-of-process worker,
Git-canonical lore records, and LanceDB. It replaces the incomplete projection revision, shared-context,
game-mutation, integration-auth, and tool-registration contracts.

The first usable product milestone is read-only DreamMaker semantics search on a provably current
workspace snapshot. The first write-capable new tool is the custom outfit editor through a staged
game-change service. Job, general outfit, icon/GAGS, type-budget, digitigrade, and PR-pipeline work then
reuse those foundations.

## Working rules

- Preserve unrelated working-tree changes. Do not reset, commit, push, or rewrite existing generated
  artifacts unless the active task explicitly requires it.
- Start each behavior change with a failing behavioral test.
- Use Meridian-MCP for DreamMaker source analysis and PowerShell for BYOND builds/tests.
- Regenerate OpenAPI TypeScript after Pydantic changes and reject drift in CI.
- Every derived dataset is immutable while active and carries source identity, revision, schema,
  extractor/indexer/model versions, content hash, counts, and build receipt.
- Every Meridian-Rift write is staged, previewed, base-hash checked, clean-checkout checked, locked,
  applied atomically, validated, and receipted.
- Keep changes reviewable by semantic dependency, with roughly 300–500 changed lines as a target rather
  than a mechanical split rule.
- Run focused gates for each batch and the repository-wide gates at each milestone. Run downstream
  DreamMaker gates only when generated or source DM changes.

## Delivery map

| Milestone | Outcome | Depends on |
|---|---|---|
| M0 | Reproducible audit baseline and policy guards | None |
| M1 | Revision-correct immutable workspace datasets | M0 |
| M2 | Parser-backed DreamMaker symbol corpus | M1 |
| M3 | Versioned context, references, and federated search | M2 |
| M4 | Staged game mutations and hardened local session | M1 |
| M5 | Standard tool/capability and SPA primitives | M1, M4 |
| M6 | Custom outfit editor vertical slice | M2–M5 |
| M7 | Job and general outfit editors | M6 |
| M8 | Type-budget/override assessment | M2, M3 |
| M9 | DMI/GAGS editor and digitigrade triage | M2–M5 |
| M10 | Local PR/change pipeline and optional remote PR adapter | M4–M7 |
| M11 | Release, supply-chain, observability, and legacy closure | M1–M10 as applicable |

M2/M3 and M4 may proceed in parallel only after M1 interfaces are accepted. M8 can proceed alongside
editor work. M9 should begin with read-only diagnostics before the pixel editor.

## M0 — Freeze the baseline and install policy guards

### Task 0.1: Add current-workspace diagnostic fixtures

Files:

- add `webapp/tests/fixtures/workspace_snapshots/` with small synthetic content-tools and game repos;
- add `webapp/tests/test_workspace_status.py`;
- update `references/development/verification.md`.

Steps:

1. Create fixture A where lore and game revisions both match the manifest.
2. Create fixture B where lore matches but the game HEAD changes after catalog/graph creation.
3. Create fixture C where one dataset build fails before activation.
4. Assert the current implementation incorrectly treats fixture B as aggregate-current; mark the test
   as the red test for M1 rather than weakening the assertion.
5. Record current row counts, search probes, cold/warm latency, graph payload size, launcher behavior,
   and store command output in a machine-readable audit fixture without local absolute paths.

Verification:

```powershell
python -m unittest webapp.tests.test_workspace_status
python tools/docs/check_agent_docs.py
git diff --check
```

### Task 0.2: Make architecture invariants executable documentation

Files:

- update `AGENTS.md`;
- add `references/development/platform-lifecycle-and-integrations.md`;
- update `references/development/README.md`;
- update `references/maintainer-guide.md`;
- update `tools/docs/check_agent_docs.py` and its tests if present.

Required policy text:

- all derived datasets have full source and build provenance;
- multi-table datasets activate atomically;
- selected context is typed and revision-bound;
- exact, structural, full-text, and semantic search are distinct capabilities;
- tool registration declares datasets, jobs, mutations, integrations, and availability;
- browser and remote credentials never substitute for each other;
- all game writes use a staged mutation service.

Verification:

```powershell
python tools/docs/check_agent_docs.py
python -m unittest webapp.tests.test_agent_docs
```

### Task 0.3: Replace unsafe monolithic Python discovery with bounded gates

Implementation status: completed 2026-08-27. Eight non-overlapping suites, an owned process-tree
wrapper, capped logs, timeouts, peak-memory reporting, `ResourceWarning` failure, PowerShell
orchestration, CI wiring, and synthetic runner tests are present under `tools/testing/`.

The full `python -m unittest discover` command has destabilized/crashed the Codex host twice. Do not
reproduce it as one process while implementing this task.

Files:

- add a machine-readable Python test-suite manifest under `tools/testing/`;
- add a PowerShell runner with one process and timeout per named suite;
- update CI and `references/development/verification.md`;
- add runner tests using synthetic pass, fail, timeout, child-process, and excessive-output fixtures.

Required named groups:

- fast domain/schema/API unit tests;
- canonical lore and generation tests;
- store/catalog/graph tests;
- embedding/model tests;
- worker/process/cancellation tests;
- launcher/bootstrap/packaging tests;
- integration tests that require repository or network-like fixtures.

The runner records command, duration, peak working set where available, exit code, bounded log path,
timeout, and remaining child processes. It terminates only the verified process tree it started and
never broad-matches Python processes. Each group gets an explicit resource/parallelism policy. CI may
run independent groups in separate jobs; local runs default to the fast groups and opt into heavy
groups by name.

Acceptance:

- every existing test is assigned to exactly one named group;
- each group finishes or times out without destabilizing the host;
- worker/model resources and sockets are closed, with `ResourceWarning` promoted to a reviewed failure
  in the relevant group;
- the aggregate report can prove all named gates passed without one monolithic discovery process.

## M1 — Replace projection currentness with workspace snapshots

### Task 1.1: Define domain models and compatibility rules

Files:

- add `webapp/store/snapshots.py`;
- add `webapp/store/datasets.py`;
- update `webapp/store/schema.py`;
- add `webapp/tests/test_workspace_snapshots.py`.

Add immutable models:

- `RepositoryIdentity`: resolved root identity without personal paths, remote identity when available,
  and revision;
- `DatasetSource`: repository identity/revision, relevant file-set hash, canonical revision if any;
- `DatasetBuild`: kind, schema version, extractor/indexer/model versions, content hash, counts,
  diagnostics summary, created time, and artifact/table references;
- `WorkspaceSnapshot`: snapshot ID, required/optional dataset map, status, compatibility decision, and
  activation receipt;
- `DatasetRequirement`: required kind plus accepted schema/capabilities.

Tests cover deterministic IDs/hashes, missing datasets, mismatched game revision, mismatched schema,
optional dataset failure, and serialization round trips.

### Task 1.2: Add a snapshot registry and atomic pointer

Files:

- add `webapp/store/snapshot_registry.py`;
- update `webapp/store/projection.py`;
- update `webapp/store/cli.py`;
- update `webapp/tests/test_store.py`.

Behavior:

1. Build datasets under an inactive content-addressed directory/generation.
2. Write and fsync the manifest and build receipt.
3. Open every referenced table/artifact and verify schema, counts, hashes, and source compatibility.
4. Replace one active-snapshot pointer atomically.
5. Never copy a stale catalog or graph into a lore-only reconcile and call it current.
6. Retain the previous active snapshot until the new pointer is verified.
7. Make backup/restore operate on snapshot manifests and explicitly mark restored source revisions.

CLI changes:

```text
status        aggregate plus every dataset source/build/currentness
build         build selected datasets without activation
verify        verify an inactive or active snapshot
activate      activate only a verified compatible snapshot
reconcile     reconcile canonical lore and leave aggregate stale until required datasets match
rebuild       build all required datasets, verify, then activate
```

### Task 1.3: Make catalog and Content Graph immutable datasets

Files:

- update `webapp/store/catalog.py`;
- update `tools/content_graph/` scanner/cache modules;
- update `webapp/api/routes/graph.py`;
- update `webapp/tests/test_store.py` and Content Graph tests.

Behavior:

- catalog and graph builders write only into inactive dataset generations;
- graph nodes, edges, unresolved markers, and delivery artifact share one build receipt;
- remove the full graph JSON from the generic manifests table;
- use normalized graph tables as source and generate a content-addressed compact artifact for delivery;
- prove injected failure after nodes or edges leaves the active graph unchanged;
- include scanner version and APHELION/NOVA parser coverage in diagnostics.

### Task 1.4: Expose typed dataset health and activation live events

Files:

- split dataset/snapshot models out of `webapp/api/models.py` into `webapp/api/schemas/`;
- update `webapp/api/routes/health.py` or the current health route;
- update `webapp/api/live.py`;
- update `webapp/frontend/src/store/appStore.ts`;
- regenerate `webapp/frontend/src/lib/api-schema.d.ts`;
- add backend/frontend health tests.

UI requirements:

- never collapse “lore current, game stale” into a green current indicator;
- show source revision, build revision, age, required/optional status, last failure, and rebuild action;
- disable only actions whose required datasets are unavailable;
- retain read-only access to a stale dataset with a visible label when safe.

M1 acceptance:

- fixture B is stale with a precise reason;
- graph failure injection cannot change active search or graph responses;
- status and UI expose both game revisions;
- backup/restore/activation tests pass;
- existing canonical lore conflict and export tests remain green.

## M2 — Build the DreamMaker semantic corpus

### Task 2.1: Select and prove a parser export boundary

Create a short spike and decision record before production code.

Candidates:

1. extend Meridian-MCP with a bulk, versioned symbol export;
2. invoke a stable SpacemanDMM export/SDK boundary;
3. share the underlying parser library through a small standalone exporter.

Do not choose a new regex or Tree-sitter grammar for convenience.

Spike corpus:

- inheritance and implicit parents;
- proc definitions/overrides and multiline signatures;
- macros and conditional includes;
- `PROC_REF`, signals, components, elements, and `AddComponent`/`AddElement` patterns;
- APHELION/NOVA modular markers and master files;
- jobs, outfits, loadouts, GAGS/body-shape icon configuration;
- intentionally invalid/incomplete fixtures.

Measure parse time, peak memory, output size, stable IDs, locations, relation recall, incremental rebuild
cost, and parity with current Meridian-MCP queries. Save the decision under `references/architecture/`.

### Task 2.2: Define corpus schemas and stable identifiers

Files:

- add `webapp/store/dm_symbols.py`;
- add `webapp/store/dm_relations.py`;
- add `webapp/store/dm_chunks.py`;
- add `webapp/store/dm_diagnostics.py`;
- add schema fixtures/tests.

Stable IDs must derive from repository identity plus logical symbol identity, not line number. Locations
are mutable attributes. Relations use typed source/target IDs and evidence spans. Chunks identify their
symbol/file parent and source hash. Result records must distinguish type, proc, var, macro, file,
component, element, signal, job, outfit, loadout item, and icon relationship.

### Task 2.3: Implement full and incremental dataset builds

Files:

- add `webapp/store/build_dm_corpus.py`;
- update `webapp/store_worker.py` and worker protocol;
- update snapshot dataset registry;
- add failure, cancellation, and incremental tests.

Behavior:

- a full build parses the pinned Meridian-Rift revision and emits an inactive dataset;
- incremental builds use include graph and file hashes, then prove their output hash equals a clean full
  build for the test corpus;
- cancellation cannot activate partial tables;
- parser errors are data with coverage status, not silently skipped rows;
- source chunks exclude generated/vendor/binary content according to an explicit policy;
- embeddings run only after exact fields and relations are complete.

### Task 2.4: Add corpus quality gates

Fixtures assert that:

- `/datum/component`, `/datum/element`, `/datum/job`, `/datum/outfit`, `Initialize`, and `typecacheof`
  resolve to their definitions;
- selected proc bodies and documentation are retrievable;
- overrides, children, job→outfit, loadout→job restrictions, component/element attachment, and icon
  relations exist;
- declared coverage and unresolved relation counts stay within reviewed thresholds;
- no local absolute paths enter stored rows, logs, or published fixtures.

M2 acceptance:

- current Meridian-Rift builds one verified corpus with source revision matching HEAD;
- a clean rebuild is deterministic;
- fixture relation recall meets its asserted baseline;
- failure/cancellation leaves the active corpus untouched.

## M3 — Replace global search, selected context, and references

### Task 3.1: Define discriminated search result models

Files:

- add `webapp/api/schemas/search.py`;
- update `webapp/store/search.py`;
- update search API route and generated frontend types;
- add backend contract tests.

Replace `dict[str, object]` records with a discriminated union. Common fields:

- provider/kind, stable ID, label/summary;
- snapshot/dataset generation and source revision;
- route/source span;
- exact, full-text, vector, relation, and context score components;
- matched fields and degradation reason.

Providers declare supported modes and receive a candidate budget. The federator applies one global
limit and deterministic RRF. Add exact-path priority, symbol prefix search, quoted exact terms, filters,
and explicit semantic opt-out/degradation.

### Task 3.2: Implement `ContextEnvelope` resolution

Files:

- add `webapp/api/schemas/context.py`;
- add `webapp/context.py`;
- update `webapp/frontend/src/store/appStore.ts`;
- update Lore Editor, Content Graph, Parsec, search, and reference adapters;
- add backend/frontend resolution tests.

Behavior:

- context carries kind, key, snapshot, source revision, route/span, relation hints, and resolution state;
- the backend resolves it against the active snapshot;
- live workspace/snapshot changes trigger re-resolution;
- stale/missing contexts cannot authorize writes;
- boosts use declared typed relations and return an explanation;
- deep links serialize only a safe versioned locator, then resolve server-side.

### Task 3.3: Give references an explicit storage contract

Recommended implementation:

- browser-local, workspace-namespaced bookmarks with schema/version migration;
- import/export JSON through Pydantic validation;
- optional later canonical “research set” records as a separate feature;
- remove bookmark persistence from rebuildable LanceDB tables after migration.

Add tests for migration, stale resolution, missing symbols, workspace separation, and malformed import.

### Task 3.4: Build the source semantics explorer

Files:

- add a typed backend tool capability and route;
- add `webapp/frontend/src/tools/sourceExplorer/`;
- reuse global search, virtualized results, context, references, and open-file actions.

Views:

- definition/source/documentation;
- inheritance and override chain;
- references/callers/callees;
- components/elements/signals;
- file/module ownership and diagnostics;
- related jobs/outfits/loadouts/icons;
- exact query, structural filters, semantic query, and relation traversal.

M3 acceptance:

- the audit probe set returns defining symbols and useful relations;
- result types require no frontend casts from arbitrary dictionaries;
- switching Meridian-Rift revisions visibly resolves or invalidates selected context and bookmarks;
- global and dedicated search share one tested provider implementation;
- WAI-ARIA combobox and keyboard tests pass.

## M4 — Add one safe game-mutation service and local session boundary

### Task 4.1: Define `GameChangeSet`

Files:

- add `webapp/game_changes/models.py`;
- add `webapp/game_changes/service.py`;
- add `webapp/game_changes/patches.py`;
- add `webapp/game_changes/validation.py`;
- add comprehensive temporary-repository tests.

State machine:

```text
draft -> prepared -> validated -> approved -> applying -> applied
                      |                         |
                      +-> rejected/expired      +-> rolled_back/failed
```

Receipt fields include repository identity/base revision, clean/conflict state, allowed paths, base and
result hashes, patch/artifact hashes, generator/tool versions, required commands, exact results,
approval identity suitable for a local single-user app, apply time, and rollback evidence.

Rules:

- resolved parent containment and symlink/reparse-point safety;
- one process/interprocess write lease per game checkout;
- no dirty-checkout force path;
- optimistic base checks immediately before apply;
- atomic replacements or complete rollback across every file;
- generated files identify their generator and are never edited as source;
- write APIs return typed conflict/expired/validation errors.

### Task 4.2: Migrate existing game writes

- move lore export apply behind `GameChangeSet` while retaining its narrower allowlist;
- move Content Graph marker edit to a prepared one-line changeset;
- add regression tests proving dirty checkout, line drift, revision drift, lock contention, validation
  failure, and rollback behavior;
- remove direct route-level file writes.

### Task 4.3: Add per-launch local session protection

Files:

- update launcher/bootstrap server startup;
- add FastAPI middleware/dependencies under `webapp/api/security.py`;
- update `webapp/frontend/src/lib/api.ts` and `live.ts`;
- add hostile Host/Origin/token/WebSocket tests.

Requirements:

- random high-entropy session credential generated per launch and delivered without placing it in
  durable logs, URLs, or repository files;
- exact loopback Host allowlist and same-origin checks for browser requests;
- custom header/token on mutations, authenticated WebSocket handshake, size limits, and origin allowlist;
- read-only health/bootstrap endpoint exposes no sensitive path, credential, or integration secret;
- test malicious-origin and missing-token requests against real ASGI/WebSocket paths.

### Task 4.4: Redesign collaboration as capabilities

- do not mount the prototype globally until configured;
- represent version, join, checkpoint, hosting, and presence as separate server-advertised capabilities;
- bind checkpoint authorization to an actual user/session grant rather than a discarded browser token or
  broad service credential;
- retain response-size, timeout, URL-origin, and secret-redaction guards;
- add explicit remote idempotency keys and action receipts.

M4 acceptance:

- every game write found by `rg` routes through the service or has a documented read-only exemption;
- direct untrusted browser requests cannot mutate through loopback endpoints;
- failed multi-file apply restores exact base hashes;
- collaboration checkpoint tests prove user/session authorization.

## M5 — Standardize tool registration and SPA composition

### Task 5.1: Add a backend capability catalog

Files:

- add `webapp/tool_manifest.py` or extend `webapp/tooling.py` with typed domain models;
- add a capability API response;
- add generated frontend types;
- update `webapp/frontend/src/tools/registry.ts` and registry tests.

Each tool declares:

- ID, label, route, category, availability/degradation reason;
- required/optional datasets and schema capabilities;
- background jobs;
- search providers/scopes/result kinds;
- read/write/change-set capabilities;
- remote integrations and permissions;
- documentation and acceptance links.

The frontend keeps lazy component factories. A test fails if frontend and backend IDs diverge or if a
tool advertises an unregistered dataset/job/mutation.

### Task 5.2: Establish shared application primitives

Add focused primitives only as real pages consume them:

- async/loading/empty/error boundary;
- status and dataset freshness badge;
- field row, validation summary, and destructive/staged action confirmation;
- accessible virtualized combobox/item navigator;
- split pane, inspector panel, preview canvas shell, and change-set diff panel;
- workspace-namespaced preference store with schema and migrations.

Add keyboard, axe, resize, empty/error/loading, and high-contrast tests. Add a local component harness or
story route excluded from production navigation for deterministic visual review.

### Task 5.3: Decompose existing monoliths at stable boundaries

- split Content Graph controller/job/scope/context state from renderer/table/inspector views;
- split API schemas by domain while preserving generated OpenAPI names intentionally;
- split lore domain operations by records/reviews/groups/catalog/export behind the existing public
  service facade;
- fix successful non-JSON API responses to raise a typed protocol error;
- centralize cancellable/debounced request resources and clean up timers on disposal.

Do not perform broad renames or styling churn. Each extraction must preserve behavior with tests before
and after.

M5 acceptance:

- a fixture tool can declare datasets/jobs/search/mutation and fail registration tests when incomplete;
- new pages use shared error/loading/selector/change preview behavior;
- Content Graph behavior and performance fixtures remain equal or improve;
- API schema and frontend generated types are drift-free.

## M6 — Deliver the custom outfit editor vertical slice

### Task 6.1: Establish the custom outfit schema and importer

Files:

- add `tools/outfit_editor/models.py`;
- add `tools/outfit_editor/importer.py`;
- add fixture JSON from synthetic type paths only;
- add compatibility tests against Meridian-Rift's `get_json_data`/`load_from` behavior.

The schema is versioned and distinguishes recognized declarative fields, preserved unknown fields,
invalid types, and non-declarative behavior warnings. Import never trusts paths or type strings without
resolving them against the active DreamMaker corpus.

### Task 6.2: Build the shared item/type navigator

Files:

- backend subtype/search/filter endpoint using the symbol corpus;
- `webapp/frontend/src/components/TypeNavigator/`;
- icon preview adapter and tests.

Capabilities:

- exact path/name search, subtype root, abstract/invalid filtering, module ownership, icon availability,
  selected-context relation, virtualized results, keyboard selection, and recent/pinned types;
- resolve every selection against the snapshot at submit time;
- never send tens of thousands of complete item records to the browser.

### Task 6.3: Build edit, preview, and export

- slot and contents editor driven by the versioned schema;
- native-size and enlarged nearest-neighbor human/body-shape preview;
- validation for invalid paths, incompatible slot types, duplicates/order/counts, and unsupported behavior;
- export through `GameChangeSet` to a staged JSON artifact/import payload;
- no direct write to a live server's mutable `data/` directory.

M6 acceptance:

- import→export round trip retains recognized and explicitly preserved unknown data;
- a staged outfit loads through game-compatible validation;
- pointer and keyboard item selection are directly exercised through the real launcher;
- invalid/stale type paths cannot apply.

## M7 — Expand to general outfits and jobs

### Task 7.1: Model effective outfit inheritance

- index every declarative `/datum/outfit` field and inheritance source;
- expose effective value, declaring type, local override, and unsupported proc behavior;
- generate minimal modular DM for supported fields through a reviewed placement policy;
- preview slots, contents, IDs/trims, backpacks, and body shapes;
- require parser, DreamChecker, unit, DreamMaker, and targeted runtime validation before apply.

### Task 7.2: Model the editable job subset

Start read-only. Inventory every `/datum/job` var/proc family and classify:

- declarative and safe to generate;
- declarative with cross-record validation;
- behavior requiring a template or dedicated editor;
- read-only/unsupported.

Then implement name/title/description, aliases, department/supervisors, access, requirements, paycheck,
outfit, loadout rules, and reviewed bonuses in increments. Always show inherited versus local values and
the source file/module that will change.

### Task 7.3: Add cross-domain validation and previews

- job→outfit existence and subtype;
- access/department/position uniqueness and ordering;
- loadout restrictions and slot conflict behavior;
- experience/species/quirk/augment/language constraints;
- job/outfit preview for standard body shapes;
- generated-source placement and modular marker policy.

M7 acceptance:

- at least one synthetic modular job and outfit round-trip through source generation, parse, unit tests,
  DreamMaker compile, and preview;
- unsupported behavior is preserved and blocks destructive rewrites rather than disappearing;
- existing non-modular and modular definitions are both inspectable without rewriting them.

## M8 — Add the type-budget and override assessment utility

### Task 8.1: Build version-aware measurements

Inputs: active DreamMaker corpus and detected/pinned BYOND version.

Metrics:

- prototype/type count, daily/revision delta, and distance from configurable warning levels;
- descendants and leaf counts per root/file/module;
- `typesof`, `subtypesof`, `typecacheof`, and static cache call sites with expansion estimates;
- proc override count/density, initial-var fingerprints, include position, modular/core ownership;
- largest contributors and changes between two snapshots.

Version policy:

- flag 516.1685 and earlier as affected by the over-64K-prototype startup defect;
- recognize that the official fix is listed in 516.1686 and included in 516.1687;
- do not describe fixed builds as having a permanent 64K hard ceiling;
- retain growth/complexity warnings because prototype count still affects startup, search, tooling, and
  maintainability.

### Task 8.2: Generate explainable recommendations

Candidate classes:

- unused/unreferenced leaf types;
- mechanically generated subtype families that could become data-driven;
- identical initial-var/proc fingerprints with distinct identity risk called out;
- scattered overrides suitable for reviewed modular colocation;
- excessive broad type-cache roots or duplicated cache construction;
- master/core edits that belong in an existing modular facility.

Every recommendation includes evidence, estimated reduction, reference/map/config checks, upstream
merge risk, proposed files, and required test plan. Default action is report/export, never auto-apply.

### Task 8.3: Add trend and CI modes

- compare current branch against a base snapshot;
- output JSON and human report;
- allow a reviewed warning budget and regression threshold;
- fail only on a confirmed affected BYOND version crossing the known risky condition or on an explicit
  repository policy, not on a guessed universal constant.

M8 acceptance:

- report accounts for all parsed types and identifies broad type-cache call sites;
- fixed/affected BYOND versions produce correct policy text;
- candidate evidence has deterministic output and false-positive fixtures;
- no source mutation exists in the first release.

## M9 — Add DMI/GAGS editing and digitigrade triage

### Task 9.1: Build and test a DMI adapter

Files:

- extend the existing icon/DMI backend or add `tools/icon_editor/dmi.py`;
- add fixture DMIs with states, directions, frames, delays, movement, alpha, GAGS palettes, and unusual
  metadata;
- add metadata-preservation and pixel round-trip tests.

The adapter emits a typed document model and recreates a byte-valid DMI while preserving unknown safe
metadata. Reject malformed dimensions/state metadata and decompression/image bombs. Do not trust file
extensions or browser MIME types.

### Task 9.2: Prototype the canvas engine behind an interface

Research spike compares:

- a small app-native Canvas/OffscreenCanvas engine;
- selective extraction from MIT Pixellate;
- selective extraction or architectural borrowing from Apache-2.0 Piskel.

Decision criteria: DMI state/direction model fit, undo memory, animation timing, nearest-neighbor
rendering, input latency, accessibility, maintenance activity, bundle size, licensing, testability, and
integration with Solid state. Do not embed an iframe or import a second application shell.

### Task 9.3: Implement editing and staged save

- pencil/eraser/fill/line/selection/eyedropper, palette, alpha, zoom/grid, frame/direction/state management;
- bounded undo/redo command log and unsaved-change recovery;
- GAGS palette/config editing and all-variant preview;
- staged artifact and diff/metadata summary through `GameChangeSet`;
- required icon/unit/DreamMaker validation before apply.

### Task 9.4: Build digitigrade diagnostics and triage first

- adapt existing clothing variation test output and indexed body-shape relations;
- classify hard missing, fallback, mask-eligible, GAGS/configuration, unused, and manual-review cases;
- store reviewed dispositions as canonical, versioned triage records in an approved location;
- show human/digitigrade composites at native size, enlarged, and animation/movement where applicable;
- deep-link to item, icon, source, test, and editor context;
- never bulk-generate placeholder pixels.

M9 acceptance:

- every DMI fixture round-trips metadata and pixels;
- direct visual review covers native, enlarged, direction, frame, animation, GAGS, and body-shape output;
- staged saves survive failure/rollback without corrupting the source DMI;
- triage agrees with game test classifications on the fixture corpus.

## M10 — Build the change/PR pipeline

### Task 10.1: Build semantic batch planning

Files:

- add `webapp/change_pipeline/models.py`;
- add `webapp/change_pipeline/planner.py`;
- add `webapp/change_pipeline/validators.py`;
- add dependency-graph and adversarial tests.

Inputs are applied or prepared `GameChangeSet` records plus content-tools changes. The planner groups
source, schema, migration, generated artifacts, tests, and docs so no required dependency is separated.
It reports target 300–500 changed-line review units but may exceed them when atomic correctness requires.

Reject:

- secrets or personal/machine paths;
- generated artifacts without their source/generator;
- source changes without behavioral tests where required;
- base-revision drift, dirty/conflicted checkout, disallowed paths, oversized binaries, or missing
  validation receipts;
- a batch whose predecessor dependency is absent.

### Task 10.2: Add preview and local handoff

- exact diff, line count, binary inventory, ownership, risk, dependencies, gates, and rollback display;
- explicit confirmation before branch or commit creation;
- non-interactive local Git operations only after confirmation;
- GitHub Desktop handoff instructions/status; no browser credential and no hidden push;
- idempotent recovery if preparation stops between batches.

### Task 10.3: Optional remote PR adapter, separately approved

Only implement after a product decision changes the current GitHub Desktop boundary.

- dedicated GitHub App or fine-grained credential with minimal repository permissions;
- credential held only by backend/OS credential storage;
- create draft PR, record idempotency key/URL/head/base, and never merge automatically;
- respect protected branches, rulesets, code owners, required checks, and review state;
- rate-limit and audit all remote mutations;
- disable the capability completely when not configured.

M10 acceptance:

- batching never separates dependency fixtures;
- hostile repositories and diffs are rejected with typed reasons;
- interruption/retry does not duplicate branches, commits, or remote PRs;
- no remote mutation is possible without explicit capability configuration and user approval.

## M11 — Productionize the integration anchor

### Task 11.1: Reproducible dependency and release inputs

- adopt and CI-verify a transitive Python lock with hashes and document the update command;
- retain `package-lock.json` and `npm ci` drift enforcement;
- add Dependabot grouping/cadence, dependency review, reviewed license policy, SBOM output, and secret
  scanning where repository settings permit;
- pin GitHub Actions by reviewed policy and minimize permissions;
- publish embedding/catalog seed with source/model/schema hashes and verify before activation.

### Task 11.2: Release and upgrade evidence

- turn the Windows sidecar spike into a signed/versioned release candidate pipeline;
- record content-tools revision, runtime, dependency lock, model, seed, frontend artifact, and SBOM hashes;
- add clean-machine offline/online install, upgrade, rollback, uninstall, and process-tree tests;
- test non-ASCII and spaced paths without publishing machine-specific paths;
- define supported BYOND version capability checks, including the 516.1685 prototype-startup defect.

### Task 11.3: Observability and performance budgets

Add structured, secret-safe events and reports for:

- dataset build/verify/activate/fail/cancel with revisions, counts, hashes, durations, and coverage;
- search provider latency, cold/warm model time, candidate/result counts, and degradation;
- context stale/re-resolve events;
- changeset prepare/validate/apply/rollback receipts;
- remote capability auth/availability failures;
- launcher/bootstrap/runtime selection without personal paths.

Set reviewed budgets for global search, source explorer, graph payload/render, item selector, initial SPA
load, worker cold start, and DMI preview. Performance failures should be reproducible fixtures, not
anecdotal thresholds.

### Task 11.4: Browser and launcher acceptance

- add Playwright or equivalent end-to-end tests through the built SPA and FastAPI server;
- add a bounded real `Launch Aphelion Content Tools.cmd` Windows smoke that proves startup, health,
  navigation, search, selected context, and clean shutdown;
- retain manual acceptance scripts for Parsec pointer feel/motion/audio and DMI native/enlarged/animated
  rendering;
- capture screenshots/traces as local evidence without tracking personal paths.

### Task 11.5: Close the legacy rollback window

After all shipped tool parity rows and launcher gates are approved:

- delete rollback-only servers/pages/tests and obsolete compatibility dependencies together;
- remove legacy documentation and fallback branches;
- prove launcher, packaging, SPA routes, export, and recovery no longer reference them;
- record the deletion and rollback alternative in an architecture decision.

M11 acceptance:

- a release candidate is reproducible from locked inputs and carries SBOM/provenance;
- clean-machine launcher and shutdown pass;
- dependency, API, generated artifact, and frontend build drift gates pass;
- legacy code is either explicitly retained with an owner/deadline or removed.

## Repository-wide verification at each milestone

Use the exact current repository and CI-pinned toolchains.

```powershell
python tools/docs/check_agent_docs.py
python -m ruff check .
python -m pyright
# Run the bounded named Python suites from Task 0.3; do not use monolithic discovery.
npm --prefix webapp/frontend run gen:api
git diff --exit-code -- webapp/frontend/src/lib/api-schema.d.ts
npm --prefix webapp/frontend test -- --run
npm --prefix webapp/frontend run typecheck
npm --prefix webapp/frontend run build
git diff --exit-code -- webapp/frontend/dist
python -m build
python packaging/smoke_wheel.py
git diff --check
git status --short
```

For DreamMaker source/generated-DM or icon changes, run the downstream Meridian-Rift commands from its
current verification guidance using PowerShell. At minimum, compile with the repository-pinned BYOND
version and inspect `$LASTEXITCODE`; add focused unit/runtime/icon gates required by the changed area.
MCP parse/analysis is supporting evidence and never replaces the compile.

For launcher, integrated UI, Parsec, or DMI work, exercise the real launcher. State explicitly when an
interactive or non-sandboxed acceptance gate was not run.

## Implementation stop points requiring maintainer decisions

Stop and request approval before:

- selecting the parser export boundary after the M2 spike;
- choosing canonical/team-shared storage for context sets or sprite dispositions;
- defining generated DM placement and editable property policy for jobs/outfits;
- importing code from Pixellate/Piskel or choosing a canvas dependency;
- changing GitHub Desktop credential/push ownership or enabling remote PR creation;
- enabling collaboration checkpoint/hosting actions;
- deleting legacy rollback code;
- applying any automated type compression or bulk sprite generation.

The snapshot, source-corpus schemas, read-only semantics search, context invalidation, local session
hardening, and staged mutation service can be developed before those decisions if their interfaces stay
implementation-neutral at the listed boundaries.

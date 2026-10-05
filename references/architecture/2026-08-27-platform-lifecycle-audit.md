# Platform life-cycle audit

Date: 2026-08-27

Status: current-state audit and architecture decision record. This report precedes the implementation
plan and does not claim that the recommended repairs are implemented.

Companion plan:
[2026-08-27 platform repair and expansion plan](../../docs/superpowers/plans/2026-08-27-platform-repair-and-expansion.md).

## Executive verdict

Aphelion Content Tools has a credible application foundation: FastAPI, a typed Solid SPA, Git-owned
canonical lore records, an out-of-process worker, generated HTTP types, staged lore export, and a
hybrid LanceDB search path. Those choices should remain.

The weak pillar is the workspace life cycle around derived data. The active projection can be marked
`current` while its Meridian-Rift catalog and Content Graph were built from an older game revision.
The selected-context and reference systems then carry objects from that stale snapshot without a
revision contract or invalidation path. Search is semantically useful for authored catalog prose, but
it does not index DreamMaker proc bodies, datum semantics, component or element relationships, or
symbol references. It must not be represented as a general Meridian-Rift semantic index.

The next architectural unit is therefore not another isolated page. It is a revision-bound workspace
snapshot and DreamMaker symbol corpus shared by search, context, editors, diagnostics, previews, and
future integrations. The type-budget inspector, source semantics search, job editor, outfit editors,
and digitigrade-sprite triage all depend on that unit. Building each tool with its own parser and cache
would repeat the repository's current provenance problem.

The application is not public, so the recommended migration deliberately favors replacing weak
contracts over preserving projection or browser-state compatibility. Canonical lore records and
explicitly staged user work remain protected; derived databases, local references, preferences, and
prototype API shapes may be rebuilt or migrated.

## Scope and evidence

This audit covered:

- repository guidance, architecture records, user workflow documentation, CI, launcher, packaging,
  Python and TypeScript manifests, backend routes, domain services, worker protocol, store tables,
  frontend shell, tool registry, global search, shared context, references, Content Graph, Lore
  Editor, File Management, Parsec, and the untracked collaboration prototype;
- current store status and dataset manifests;
- direct global-search probes for names, procs, type paths, type-cache helpers, and outfits;
- parser-backed Meridian-MCP inspection of the current Meridian-Rift environment, jobs, outfits,
  type caches, custom outfits, loadout rules, and digitigrade validation;
- primary-source research on BYOND limits and DMI behavior, source parsing, LanceDB consistency and
  versioning, web pixel editors, local-web security, accessible selectors, dependency reproducibility,
  and GitHub pull-request automation.

The working tree already contained extensive uncommitted product work. This audit did not reset,
reformat, commit, push, or rewrite those changes. Findings about untracked collaboration and Parsec
work describe the observed state and are not ownership claims.

### Reproducible current-state evidence

At the audit point:

- Content Tools reported active generation `b57b8105df57-afceb7b9a6a2`, canonical content revision
  `b57b8105df57639239b4fba9c30d9961100647bc0984040b510aacc9e5b2e2a1`, schema version `1`, embedding
  model `BAAI/bge-small-en-v1.5`, and `current: true`.
- Both the catalog and Content Graph manifests were built from Meridian-Rift revision
  `c34175cab324ce34c768e698a0c7c6c488691f89`.
- The selected Meridian-Rift checkout was at
  `1623a76079a6617598498eaf7f5778f8564ed314`, dated 2026-08-25. The derived game datasets were stale.
- The active store contained 20,881 catalog targets, 30,331 graph nodes, 31,375 graph edges, 2,027
  unresolved markers, 8 groups, no overrides, no reviews, no assignments, and no saved references.
- Meridian-MCP parsed the current DreamMaker environment successfully with 450,081 indexed symbols
  and 64,843 types.

Reproduce the first and third facts with:

```powershell
python -m webapp.store.cli status --repo-root .
git -C ../Meridian-Rift rev-parse HEAD
```

Dataset source revisions need a first-class status command; extracting them from internal manifests
is itself evidence that the current operator surface is incomplete.

## Current feature inventory

| Area | Available capability | Life-cycle assessment |
|---|---|---|
| Launcher | Windows bootstrap, private Python fallback, catalog bootstrap, loopback API, tracked SPA artifact | Strong user path; release seed and packaged-sidecar publication remain incomplete |
| Home | Repository and store status, tool navigation, current integration status | Useful, but “current” does not cover all game-derived datasets |
| File Management | Local branch/commit operations, tool execution, staged lore export, repository status | Appropriate local boundary; game-repository edits do not yet share one mutation policy |
| Lore Editor | Structured records, groups, review and assignment workflows, icon preview, definition lookup | Canonical data model is the strongest part of the application |
| Content Graph | NOVA/APHELION scan, graph/table views, scopes, marker diagnostics, targeted marker edit, references | Valuable but its graph snapshot and searchable graph tables do not activate atomically |
| Global search | One-query-vector hybrid retrieval, RRF merge, global result limit, scopes, selected-context boost | Good catalog search; inadequate and misleading as source-code semantic search |
| Shared context | One selected object shared between Lore Editor, Content Graph, search, references, and Parsec | Useful prototype; unversioned, partially typed, and not invalidated on workspace change |
| References | Pin selected objects for later navigation | Stored only in the derived local projection; provenance and persistence contract are undefined |
| Store operations | Status, reconcile, rebuild, backup, restore, optimize, persistent worker, live updates | Solid recovery base; revision model covers canonical lore but not every source dataset |
| Parsec | Feedback surface, history/preferences, animated companion and asset work | Broad implementation in progress; direct pointer-feel and visual acceptance remains mandatory |
| Collaboration | AphelionDMM version/join/checkpoint proxy prototype | Not yet a complete authorization or capability design; currently mounted as shell-wide status |
| Packaging | Measured Windows sidecar spike | Not a release pipeline; model/catalog seed publication remains blocking infrastructure |
| Legacy UI | Rollback-only server and pages | No longer a product surface; should be removed after an explicit launcher parity gate |

## Life-cycle model: current and required

The current effective model is:

```text
canonical lore revision + embedding model + schema
                    |
                    v
             active generation
                    |
        +-----------+-----------+
        |                       |
 copied catalog/graph      reconciled lore rows
 even if game changed
```

The required model is:

```text
WorkspaceSnapshot
  content_tools_revision
  canonical_lore_revision
  game_repository_identity + game_revision
  schema_bundle_version
  datasets[]
    kind
    source identity/revision/hash
    extractor/indexer/model versions
    table versions or immutable generation
    row counts + diagnostics
    built/verified timestamps
    status: building | ready | active | stale | failed
```

Every API response and shared context that depends on derived data must identify its snapshot. A
workspace activates a complete compatible snapshot, or an explicit set of immutable dataset
generations, in one pointer update. A failed build never mutates the active search corpus.

LanceDB should remain the projection engine. Its official documentation provides table versioning,
checkout/restore, and configurable cross-process freshness; the application must add the missing
cross-table transaction boundary and source manifest rather than replace the database merely to obtain
those concepts. See [LanceDB consistency](https://docs.lancedb.com/tables/consistency) and
[versioning and reproducibility](https://docs.lancedb.com/tables/versioning).

## Findings

### P1 — Store “current” is not workspace current

`ProjectionRevision` describes the canonical lore revision, embedding model, schema version, and
state. It omits Meridian-Rift identity/revision, catalog extractor version, Content Graph scanner
version, and per-dataset hashes. `reconcile` can copy a generation containing stale game-derived data,
update lore-owned tables, and call the new generation current.

Impact:

- authors can search or inspect a previous game checkout while the UI reports healthy/current;
- selected context and saved references can silently point to deleted or changed definitions;
- future job, outfit, icon, and code-analysis editors would inherit the same false-current state;
- tests of canonical reconciliation cannot establish whole-workspace correctness.

Decision: replace the single projection revision with the workspace snapshot manifest described above.
Health must report each required dataset and the aggregate may be current only when all required
datasets match the active workspace.

### P1 — Content Graph scan is not an atomic projection activation

Catalog activation creates a new generation and changes the active pointer. Content Graph scan writes
nodes, then edges, then unresolved markers, then a manifest into the active generation. A failure can
leave mixed versions. The graph API also reads a large self-contained graph embedded in a manifest
while global search reads the separate tables, so two views can disagree.

Decision: build graph tables and its compact delivery artifact outside the active generation, verify
counts/hashes/references, then activate them as one immutable dataset. Do not store the full graph JSON
inside a generic manifest row. Store metadata in the manifest and a content-addressed graph artifact
or normalized tables with an explicit export cache.

### P1 — “Semantic search” does not cover DreamMaker semantics

Direct probes showed that `/datum/component`, `Initialize`, `typecacheof`, and `custom outfit` returned
catalog prose, paths, filenames, or unresolved marker text rather than the defining procs and datums.
The graph corpus indexes path/name/module fields, not proc bodies, documentation, definitions,
inheritance, overrides, calls, signals, component attachment, or element attachment.

The existing hybrid method is sound for its corpus: one query embedding, vector and keyword retrieval,
and reciprocal-rank fusion. LanceDB officially supports hybrid full-text/vector retrieval and RRF
reranking. The defect is corpus and result typing, not RRF. See the
[LanceDB Python query API](https://lancedb.github.io/lancedb/python/python/).

Decision: add an immutable DreamMaker symbol dataset with at least:

- `dm_files`: file hash, module ownership, include order, repository revision;
- `dm_symbols`: stable symbol ID, kind, full path, declaration location, documentation, signature,
  effective parent, source span, flags;
- `dm_relations`: inheritance, override, call/reference, signal registration/handler, component and
  element attachment, job/outfit/loadout and icon relationships;
- `dm_chunks`: source/documentation chunks with exact-search fields and embeddings;
- `dm_diagnostics`: parser errors, unresolved references, type-budget metrics, and extractor coverage.

Use Meridian-MCP/SpacemanDMM-derived parser data where possible. SpacemanDMM already supplies a DM
language server, definitions, documentation generation, and static analysis; this is stronger evidence
than starting a second regex parser. See the
[SpacemanDMM repository](https://github.com/SpaceManiac/SpacemanDMM). Tree-sitter is a reasonable
incremental parsing framework in general, but a new DM grammar would become another semantic authority
and must not be adopted until corpus tests prove parity; see the
[Tree-sitter introduction](https://tree-sitter.github.io/tree-sitter/index.html).

### P1 — Shared context has no revision or resolution contract

The application store carries a selected ID, label, kind, type path, module, and tool. Context boosts
use only a subset of those fields, and `record_kind` is not scored. Graph references do not fully
reconstruct module context. Backend live messages include a workspace revision, but the frontend
currently ignores it.

Decision: replace the loose object with a versioned `ContextEnvelope`:

```text
schema_version
context_id
kind
primary_key
display
source_repository
source_revision
dataset_generation
relations / related keys
route and source span
resolution: current | stale | missing | ambiguous
```

On workspace or dataset activation, re-resolve the envelope. Clear unsafe action state when it cannot
be resolved. Preserve a visible stale tombstone when that helps the user understand what changed.
Selected context may influence ranking through declared relations, but boosts must be explainable in
the result payload.

References need an explicit product decision. Recommended default: browser-local workspace bookmarks
that store the complete context envelope and migrate with a schema version. Team-shared research sets
should be separate canonical records, not rows hidden in a rebuildable LanceDB projection.

### P1 — Local application and collaboration authorization are incomplete

Loopback binding is necessary but is not an authorization model. The HTTP API and WebSocket currently
have no per-launch credential; WebSocket origin is not restricted. The collaboration prototype obtains
a join token in the browser, discards its value after setting a Boolean, and performs checkpoint calls
through the backend service credential. The checkpoint action is therefore not bound to the browser's
join authorization.

Decision:

- issue a random per-launch local session credential and require it on mutating HTTP requests;
- validate exact `Host`, `Origin`, and WebSocket origin values;
- authenticate the WebSocket handshake and validate message size/type;
- model remote integration capabilities and user grants server-side;
- never substitute a broad service credential for a user-authorized remote action;
- mount integrations through the capability/tool registry and show unconfigured services only where
  they are actionable.

OWASP explicitly recommends origin validation and token-based authentication for WebSockets, and
notes that CORS alone is not access control. See the
[WebSocket Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html)
and [CSRF prevention guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

### P1 — Game-repository mutation policies are fragmented

Lore export has a strong prepare/apply protocol. Content Graph marker edit instead writes one validated
line directly after an optimistic line check. It does not share the clean-checkout rule, a game-repo
write lease, a staged artifact, or typed conflict responses. New job, outfit, icon, and PR tooling would
multiply this inconsistency.

Decision: introduce one `GameChangeSet` service. Every proposed game change records repository
identity/revision, allowed paths, base hashes, generated patches/artifacts, ownership reason, validation
commands, status, and apply receipt. Applying requires a compatible clean checkout, a workspace write
lease, current base hashes, containment, complete rollback, and an audit record. Tools may use narrower
policies, but they may not bypass the service.

### P2 — Tool registration is only partially declarative

The frontend registry centralizes route, label, color, component, and search metadata, but backend
routes, Pydantic schemas, background jobs, dataset requirements, permissions, documentation, and result
kinds remain separately wired. “Adding a tool is a one-file change” is no longer true.

Decision: define a backend-owned typed capability catalog containing tool ID, route, required datasets,
jobs, search scopes, mutation capabilities, integration requirements, and availability. Generate its
frontend type. The frontend registry retains the lazy component import but is validated against the
catalog in tests. A new tool becomes one declared capability plus its implementation, not one oversized
manifest or many invisible registrations.

### P2 — SPA composition is consistent at the shell level but uneven inside tools

Positive findings:

- there is one request wrapper, one live connection, one application store, one shell, and one frontend
  registry;
- tool styles are scoped and no top-level bare-element leakage was found;
- global search implements useful combobox roles, keyboard behavior, request-staleness guards, and
  a degraded-semantic notice;
- API types are generated from OpenAPI.

Debt:

- `ContentGraphPage.tsx` owns route loading, scan jobs, scope state, graph physics/rendering, selection,
  reference actions, and table fallback; it needs controller/view decomposition;
- backend HTTP schemas and lore API operations are concentrated in large monoliths;
- shared async, error, empty, status, field, selector, and staged-change patterns are not standardized;
- preferences in browser storage do not share a schema/migration/workspace namespace;
- `requestJson` accepts a successful non-JSON response as `{}`, hiding protocol failures;
- frontend live state ignores workspace-revision changes;
- global-search timer cleanup and cancellation should use a common request-resource primitive.

Decision: create small accessible application primitives and controller hooks, not a wholesale UI
framework replacement. The global search and item navigator should conform to the current
[WAI-ARIA combobox pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/). Add a component harness
for error/loading/empty/keyboard states and visual regression of high-value surfaces.

### P2 — Dependency and release provenance is incomplete

Node has a lockfile and CI uses a clean install path. Python runtime dependencies are pinned in
manifests but there is no standardized transitive lock with artifact hashes. The repository does not
yet enforce dependency/license review, publish an SBOM, or attest a release artifact. The packaging
spike is measured but not a release pipeline.

Decision:

- adopt a Python lock format/tool that records transitive artifacts and hashes; `pylock.toml` is now a
  standard interchange format for reproducible Python installs;
- retain `package-lock.json` and `npm ci` in CI;
- add dependency review, Dependabot policy, license policy, secret scanning where available, SBOM
  generation, and release provenance;
- publish and verify the model/catalog seed independently from the application binary;
- establish upgrade cadence and rollback evidence for embeddings, LanceDB, Python, Node, and BYOND.

Primary references: [Python `pylock.toml` specification](https://packaging.python.org/en/latest/specifications/pylock-toml/),
[`npm ci`](https://docs.npmjs.com/cli/commands/npm-ci/), and
[GitHub supply-chain guidance](https://docs.github.com/en/code-security/tutorials/implement-supply-chain-best-practices/securing-code).

### P2 — Observability and acceptance gates do not yet match an integration anchor

The job log and worker-startup log are useful. Missing platform-level evidence includes:

- dataset build duration, source revision, row counts, coverage, hash, and activation receipt;
- search latency/recall fixtures by corpus and cold/warm state;
- context invalidation and resolution events;
- staged mutation previews, apply receipts, and rollback results;
- integration capability/auth failures without secret leakage;
- real-launcher end-to-end smoke in CI or a documented Windows acceptance run;
- performance budgets for graph payload, initial SPA load, embedding cold load, and item selectors;
- visual regression and direct pointer/motion review for Parsec and sprite tools.

### P1 — Monolithic Python discovery is unsafe on the development host

`python -m unittest discover` destabilized or crashed the Codex host twice. During the audited attempt,
the suite ran for several minutes through repeated store/embedding/graph fixtures, emitted a socket
`ResourceWarning`, never produced a unittest completion summary, and its process disappeared after the
host/tool interruption. This evidence does not isolate a failing test or prove whether memory pressure,
child-process cleanup, model/runtime resources, output volume, or their interaction caused the crash.
It does establish that rerunning monolithic discovery is unsafe and cannot be used as a completion gate
in the current environment.

Decision: make Python verification a manifest of bounded suites with per-suite timeout, isolated
temporary workspace/model policy, captured logs, explicit child-process cleanup, and peak-resource
telemetry. Run cheap unit/schema/domain suites first; run store/embedding/worker/packaging/launcher
integration suites as separate named gates. Until that exists, report each named suite that actually
ran and mark aggregate Python verification unverified rather than retrying discovery.

## Requested tool assessments

### Type-budget and override colocation inspector

Priority: foundation-adjacent, after the DreamMaker symbol corpus and snapshot manifest.

The current parsed environment contains 64,843 types. The test user confirmed that the incident was
present through BYOND 516.1685 and fixed for them in 516.1687. BYOND's official 516 notes list the
relevant Dream Daemon fix under build 516.1686: worlds with more than 64K prototypes could sometimes
crash or hang during startup. Build 516.1687 includes that fix. This establishes the failure class
without establishing a permanent 65,535-type ceiling in fixed builds. See the
[BYOND 516 release notes](https://www.byond.com/docs/notes/516.html).

Build a read-only analyzer first:

- total types and change over time;
- direct and transitive descendants by root, file, and module;
- `typesof`, `subtypesof`, `typecacheof`, and related call sites with estimated expansion size;
- duplicate leaf families, near-identical initial vars, proc-override density, and file/module ownership;
- master-file/core/modular placement and APHELION/NOVA marker relationships;
- explainable compression or colocation candidates with estimated type reduction and merge risk;
- a configurable warning budget and trend gate, with a BYOND-version capability check rather than a
  permanent hard limit for fixed builds.

Do not automatically merge types or colocate overrides. Type identity can be gameplay data, and a
superficially duplicate subtype can be referenced through paths, maps, serialization, configuration,
or external tooling. Each recommendation needs reference evidence and a compile/test plan.

### Proc, datum, component, and element context/semantics search

Priority: first new platform capability.

Expose the DreamMaker corpus through global search and a dedicated explorer. Search modes should be
explicit:

- exact symbol/path and prefix search;
- structural filters for kind, parent, module, file, override depth, component/element attachment,
  signal, and diagnostics;
- full-text search over documentation and source;
- semantic retrieval over bounded documentation/source chunks;
- relationship traversal for callers, callees, definitions, references, children, overrides, and
  attached components/elements.

Results must be discriminated Pydantic models, not arbitrary dictionaries. Each result carries a
snapshot revision, exact source span, score components, matched fields, and a typed context envelope.
Global search should federate result providers under one global limit while preserving provider
budgets and explainability.

### GAGS and DMI icon editor

Priority: after snapshot, changeset, and symbol/icon relationship infrastructure.

[Pixellate](https://github.com/RainboeStrykr/Pixellate) is an MIT-licensed HTML Canvas PWA with basic
pixel drawing, import, frames, PNG, and GIF export. It is a useful interaction reference or small-code
donor after a license/source review, but it is not a DMI or GAGS editor and its visible project scale is
small. [Piskel](https://github.com/piskelapp/piskel) is a substantially larger Apache-2.0 web sprite
editor with animation support, but adopting an entire editor would bring a second application shell
and legacy assumptions.

Recommend an app-native editor core with selectively reused ideas or libraries, not an iframe:

- backend DMI adapter preserves PNG metadata and maps icon states, directions, frames, delays, movement,
  and tile size;
- frontend canvas owns zoom, grid, tools, palette, selection, frames/directions, undo/redo, and keyboard
  controls;
- GAGS mode edits palette/color configuration and previews all configured variants;
- save produces a staged DMI artifact through `GameChangeSet`, never an immediate source overwrite;
- acceptance previews native-size, enlarged nearest-neighbor, animation, all directions, body shapes,
  overlays, and in-game-relevant composite states.

BYOND documents that DMI is PNG with metadata/comments that must be preserved, and that a file can hold
states, directions, and animation frames. A generic PNG editor is therefore insufficient. See the
[BYOND icon reference](https://secure.byond.com/docs/ref/info.html) and
[BYOND 4.0 icon format notes](https://secure.byond.com/docs/notes/400.html).

### PR creator and change pipeline

Priority: build the local pipeline after `GameChangeSet`; remote PR creation is later and separately
authorized.

Do not split diffs mechanically every 300–500 lines. A line cap can divide a schema from its migration,
a generated artifact from its source, or a behavior from its test. Treat 300–500 changed lines as a
reviewability target for semantic batches.

The local pipeline should:

1. collect one or more validated change sets;
2. build a dependency graph of source, generated artifacts, tests, and documentation;
3. propose semantic batches with ownership, risk, and expected line counts;
4. preview exact diffs and reject disallowed paths, secrets, generated-source edits, dirty-base drift,
   or unresolved dependencies;
5. run focused and required gates per batch and record evidence;
6. prepare local branches/commits only after explicit user confirmation;
7. hand off authentication, push, and complex merge work to GitHub Desktop under current policy.

If remote PR creation is later approved, prefer a dedicated GitHub App or fine-grained credential with
repository-scoped permissions, create draft PRs, and rely on protected branches/rulesets and required
checks. GitHub documents a dedicated pull-request write permission for PR creation, draft PRs, and
protected-branch checks. See the
[pull-request REST API](https://docs.github.com/en/rest/pulls/pulls) and
[protected branch guidance](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches).

### Job editor

Priority: after symbol search and `GameChangeSet`.

`/datum/job` is an inheritance-based model with many children and behavior beyond display name: title,
description, faction, skills, playtime/config/map checks, outfit selection, spawn behavior, bans,
requirements, and downstream loadout rules. The editor should not expose arbitrary datum vars as a
flat form.

Build a versioned editable job schema that maps a reviewed subset of properties and relationships to
source definitions. Show effective inherited values and local overrides separately. Include job title
aliases, departments, supervisors, access, experience requirements, paycheck, outfit, loadout
restrictions, spawn behavior, and policy/validation coverage as the source corpus confirms them. Stage
minimal modular source changes and run parser, lint, unit, compile, and relevant runtime gates.

### Outfit editor

Priority: first major consumer of the shared item navigator.

`/datum/outfit` already defines named slots, backpack/belt contents, JSON serialization, copying,
loading, saving, preview-related subclasses, and job relationships. Build one virtualized item/type
navigator backed by exact symbol search, subtype filters, icon previews, compatibility diagnostics, and
selected context. Reuse it for jobs, outfits, loadouts, and later sprite triage.

The editor must show effective inherited slots versus local overrides, contents ordering/counts,
post-equip behavior that cannot be expressed declaratively, and a rendered human/body-shape preview.
Non-declarative procs make an outfit partially editable rather than silently discarded.

### Custom outfit editor

Priority: recommended first editor vertical slice.

Meridian-Rift already serializes outfits as JSON and loads server custom outfits from
`data/custom_outfits.json`. That makes offline structured editing lower risk than general job-source
editing. Define a versioned Pydantic schema, import existing JSON through the game-compatible parser,
edit with the shared item navigator, preview, validate, and export a staged file or DM-supported import
payload. Do not make the application's canonical data model depend on an active server's mutable
`data/` directory.

### Missing digitigrade sprite checker

Priority: can start as a diagnostics adapter after icon relationships are indexed; full editing waits
for the DMI editor.

The game already has a clothing-variation unit test and body-shape masking logic. Missing digitigrade
assets are not one class of defect: uniforms may use a human fallback; suits or shoes can be hard
failures; some sprites can be generated from masks; GAGS/body-shape configurations alter the expected
states; and some garments are intentionally unsuitable.

The tool should import machine findings, classify them as hard failure, fallback, mask-eligible,
configuration issue, unused asset, or manual review, and persist a maintainer disposition with evidence.
Show native-size and enlarged side-by-side human/digitigrade composites, animated states where present,
the defining type and icon source, related unit-test output, and deep links to search/context. The tool
must never bulk-create placeholder sprites or mark every absent state as a defect.

## Infrastructure inventory

### Keep and strengthen

- FastAPI application factory and Pydantic HTTP ownership.
- Solid SPA, one shell, generated API types, scoped styles, and one live connection.
- Git-canonical lore records with hashes and coordinated writes.
- persistent out-of-process model/index worker and workspace lease.
- LanceDB hybrid search, provided dataset manifests and atomic activation are added above it.
- prepare/apply export pattern and GitHub Desktop credential boundary.
- PowerShell ownership of BYOND build/test execution and Meridian-MCP ownership of source analysis.

### Add

- workspace snapshot/dataset manifest and atomic multi-dataset activation;
- parser-backed DreamMaker symbol, relation, source-chunk, and diagnostic datasets;
- versioned context envelope, reference persistence contract, and workspace-change invalidation;
- backend capability catalog and validated frontend tool registration;
- one staged `GameChangeSet` mutation service and receipt/audit log;
- shared item/type navigator, icon preview service, and body-shape preview fixtures;
- per-launch local session protection and integration capability authorization;
- background-job dependency DAG, dataset build receipts, cancellation and activation phases;
- search relevance, latency, parser coverage, context invalidation, and stale-dataset tests;
- accessible component primitives, visual regression, real launcher smoke, and performance budgets;
- Python transitive lock, dependency/license review, SBOM, and release provenance.

### Remove or replace

- aggregate health based only on the canonical lore revision;
- in-place Content Graph writes into the active generation;
- full graph JSON stored as a generic manifest row;
- untyped heterogeneous search result dictionaries;
- local LanceDB rows as the unexplained persistence layer for user bookmarks;
- claims that one frontend registry file completely registers a tool;
- direct game-repository writes outside the staged mutation service;
- unconditional shell mounting of unconfigured integrations;
- legacy pages and server after launcher parity/rollback closure;
- duplicate or ad hoc browser-storage formats without schema and migration.

## Decisions and sequencing constraints

1. Repair dataset provenance and activation before adding editors that write Meridian-Rift.
2. Build the DreamMaker corpus once and make it the shared source for type budget, source search, item
   navigation, jobs, outfits, loadouts, icons, and sprite diagnostics.
3. Replace shared context at the same time as the new result union so stale identifiers cannot leak into
   new tools.
4. Introduce `GameChangeSet` before any job, outfit, icon, or PR pipeline can apply changes.
5. Treat custom outfits as the first editor vertical slice and semantic search as the first read-only
   platform capability.
6. Close the local security boundary before enabling remote integration actions.
7. Standardize SPA primitives through real new-tool consumers, not an isolated design-system rewrite.
8. Keep type compression and sprite remediation recommendation-only until direct game tests confirm each
   proposed change.

## Unknowns requiring explicit evidence

- The original failing startup log and dependency symptoms are not retained in this repository. The
  upstream failure class and affected/fixed release line are now identified, so this evidence is useful
  for incident reconstruction but no longer blocks the analyzer design.
- Whether Meridian-MCP should expose a stable bulk symbol export, SpacemanDMM should be invoked directly,
  or a shared library/API should own the corpus. Decide with a parity/performance spike.
- The intended persistence and sharing policy for references and future context sets.
- The allowed declarative property subset and generated-source placement for jobs/outfits.
- Whether remote PR creation is wanted after the local pipeline proves safe; current guidance keeps
  authentication and push in GitHub Desktop.
- The canonical home for sprite-review dispositions and whether they belong in Content Tools or a game
  module.
- The completion and authorization model for the AphelionDMM collaboration prototype.
- The exact test or resource interaction behind the repeatable Codex-host crash during monolithic
  Python unittest discovery. Do not reproduce it through another full-discovery run; isolate bounded
  suites with telemetry.

These are implementation decisions, not reasons to defer the snapshot, source corpus, context, and
changeset foundations.

## Verification performed for this audit

Passed on the observed working tree:

- agent-documentation consistency checker;
- `ruff`;
- Pyright with zero errors/warnings;
- frontend Vitest: 66 files and 326 tests;
- frontend TypeScript typecheck;
- Vite production build to an isolated temporary output directory;
- whitespace/error checks for the audit and guidance files.

Not completed:

- aggregate Python unittest discovery: unsafe host crash/interruption described above, no final result;
- OpenAPI regeneration and tracked `dist` drift checks: intentionally not written over the unrelated
  dirty generated artifacts during a documentation-only audit;
- wheel/package build, real launcher acceptance, and downstream DreamMaker compile/runtime: not needed
  to validate documentation edits and not claimed.

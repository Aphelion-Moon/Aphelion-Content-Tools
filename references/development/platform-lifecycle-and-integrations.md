# Platform life cycle and integrations

Read this guide for derived datasets, workspace health, shared context, search, new tools, game writes,
or external integrations. The maintainer guide remains normative.

## Workspace currentness

`current` is an aggregate compatibility claim, not a synonym for “canonical lore rows match.” A
workspace snapshot identifies every required dataset and its source:

- source repository identity and revision;
- relevant source/canonical content hash;
- dataset schema version;
- extractor, scanner, indexer, and embedding model versions as applicable;
- artifact/table content hash, row counts, diagnostics, and build receipt;
- state: `building`, `ready`, `active`, `stale`, or `failed`.

A required catalog, graph, DreamMaker symbol, icon, job, or outfit dataset built from another game
revision makes the aggregate workspace stale even when canonical lore is current. Optional dataset
failure degrades only the capabilities that declare it.

## Immutable build and activation

Never update a multi-table dataset in place while it is active.

1. Resolve and pin every source revision.
2. Build under an inactive, content-addressed generation.
3. Write manifest and artifacts completely.
4. Reopen and verify schemas, hashes, counts, relations, and compatibility.
5. Atomically replace one active-snapshot pointer.
6. Retain the prior snapshot until the new pointer and reads are verified.

Cancellation or failure leaves the active snapshot byte-for-byte and table-version unchanged. LanceDB
table versioning and read consistency support this design but do not provide the cross-table activation
boundary by themselves.

Backups and restores operate on complete snapshot manifests. A restored snapshot remains explicitly
stale when its source revisions do not match the selected repositories.

## Search capabilities

Name search modes precisely:

- **Exact** — stable ID, full type path, exact name, prefix, or quoted term.
- **Structural** — symbol kind, parent, module, file, override, relation, diagnostic, or other typed
  filters.
- **Full-text** — lexical retrieval over indexed documentation/source fields.
- **Semantic** — embedding retrieval over declared bounded chunks.
- **Relational** — graph traversal such as parent/child, definition/reference, caller/callee,
  override, signal, component, element, job/outfit, loadout, or icon relationships.

Do not describe filename/path search as source semantics. Semantic search quality is a property of its
corpus, not only its embedding model. Every result is a discriminated Pydantic type with provider,
kind, source snapshot/revision, route or source span, matched fields, score components, and degradation
reason. The frontend does not cast arbitrary record dictionaries.

Federated search uses provider candidate budgets, one deterministic merge, and one global result limit.
Selected-context boosts are typed, relation-aware, capped, and explainable.

## Shared context and references

Cross-tool selected context uses a versioned envelope containing:

- context schema version, kind, stable primary key, and display summary;
- source repository and revision plus dataset generation;
- route/source span and typed relation hints;
- resolution state: `current`, `stale`, `missing`, or `ambiguous`.

The backend resolves context against the active snapshot. A workspace/snapshot live event triggers
re-resolution. Stale or unresolved context may remain visible as a tombstone, but it cannot authorize a
write or be submitted as though it were current.

References/bookmarks need an explicit persistence policy. Browser-local bookmarks are workspace
namespaced, schema-versioned, and validated on import. Team-shared context sets are canonical records
with their own review/export policy. Rebuildable LanceDB rows are not an implicit user-data store.

## Tool and capability registration

The backend capability catalog owns tool identity and declares:

- route, label/category, documentation, and availability/degradation reason;
- required and optional dataset capabilities;
- background jobs and their state model;
- search providers, scopes, and result kinds;
- read and staged-mutation capabilities;
- remote integrations and authorization requirements.

The Solid registry owns lazy component factories and presentation metadata that cannot be generated.
Tests verify that backend and frontend tool IDs and declared capabilities agree. Adding a tool is a
declarative registration plus implementation, schemas, tests, and documentation; it is not assumed to
be a one-file change.

## Game-repository changes

All Meridian-Rift writes pass through one staged change-set service. A change set records:

- repository identity, base revision, clean/conflict state, and write lease;
- allowed paths with resolved parent containment;
- base/result/patch/artifact hashes and generator versions;
- exact preview, validation commands/results, and dependencies;
- approval, apply, rollback, and final receipt state.

Apply rechecks the checkout and hashes immediately before writing. Multi-file application uses atomic
replacement or complete rollback. There is no dirty-checkout force path. Generated DreamMaker and DMI
artifacts are edited through their source/generator model, never patched as unexplained output.

Routes remain thin and do not open game files for writing. A one-line marker edit is still a change set,
not an exception.

## Local and remote security boundary

Loopback binding is required but insufficient for mutations.

- Generate a high-entropy per-launch local session credential.
- Require it on mutating HTTP requests and authenticate WebSocket establishment.
- Validate exact loopback Host and same-origin values; use allowlists, never substring matching.
- Limit body/message sizes and validate every Pydantic/message schema.
- Keep credentials out of URLs, logs, browser persistence, generated artifacts, and error bodies.
- Treat remote version, join, checkpoint, hosting, and presence as separate capabilities.
- Bind a remote action to the user/session grant that authorized it. Do not perform it with a broader
  service credential merely because the browser once obtained a join token.
- Make unconfigured integrations unavailable rather than mounting a failing shell-wide widget.

The current AphelionDMM adapter exposes local capability status and anonymous version diagnostics.
Session reads, joins, and checkpoints remain unavailable until a remote user-grant flow is implemented;
the configured service credential is never forwarded. Protocol compatibility alone does not enable
those actions. Checkpoint schemas use an idempotency key and the upstream pending/accepted/rejected
states; a pending request is not a verified checkpoint.

GitHub Desktop continues to own authentication, pushes, pull requests, and complex merges unless an
approved design explicitly replaces that policy. A future GitHub adapter uses least-privilege,
repository-scoped authorization, draft PRs, protected branches/rulesets, explicit confirmation,
idempotency, and receipts. It never merges automatically by implication.

## SPA standardization

Preserve one shell, typed API client, live owner, shared store path, and scoped-style policy. Build
shared primitives only for repeated application behavior:

- async/loading/empty/error states;
- dataset freshness and capability status;
- accessible virtualized combobox/type navigator;
- validation summary and staged-change preview;
- inspector/preview panels and workspace-scoped preference migrations.

Large pages separate resource/controller state from renderer and inspector views. Browser timers,
requests, workers, object URLs, observers, and canvas resources are disposed on unmount. Successful
non-JSON responses from JSON endpoints are protocol errors, not empty objects.

Interactive selectors follow current WAI-ARIA patterns and receive keyboard and accessibility tests.
Pixel/motion tools additionally require direct native-size, enlarged, animated/in-motion, and pointer
interaction review.

## Verification additions

Alongside the repository-wide gates, changes in this area test:

- stale game revision while canonical lore matches;
- failure/cancellation between dataset table writes;
- inactive snapshot verification and atomic activation;
- context re-resolution after branch/snapshot change;
- exact/structural/full-text/semantic/relational search fixtures;
- hostile Host/Origin, absent/invalid token, and WebSocket handshake/message cases;
- dirty/conflicted/drifted repository, lock contention, partial apply, and rollback;
- tool registry/capability drift;
- search cold/warm latency and graph/item-selector payload budgets;
- absence of credentials, personal identifiers, and machine paths in stored/published artifacts.

DreamMaker analysis uses Meridian-MCP after `dm_parse_environment`. PowerShell owns compile and runtime
gates. A parser green is not a DreamMaker compile green.

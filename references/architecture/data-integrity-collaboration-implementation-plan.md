# Data Integrity and Git Collaboration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Zoe requires inline execution and prohibits subagent dispatch unless she separately approves it.

**Goal:** Make writer-authored Aphelion content safe, Git-reviewable, branch-isolated, conflict-aware, and searchable through a rebuildable LanceDB projection.

**Architecture:** Deterministic per-record JSON in the selected content-tools workspace is authoritative. LanceDB is an ignored, worktree-scoped projection used for paging, hybrid search, and graph queries. One backend owns mutations for a workspace, writes use expected record hashes, and any projection failure leaves the canonical Git record durable and marks the cache stale.

**Tech Stack:** Python 3.11+, Pydantic/FastAPI, LanceDB/PyArrow, FastEmbed, Git/GitHub Desktop, Solid/TypeScript for the contextual search client.

**Spec:** `references/architecture/codebase-audit-and-recovery-plan.md`

**Implementation status (2026-08-23):** Tasks 1-11 are implemented in the current working tree and
passed the final foundation gate recorded below. The unchecked boxes in the task bodies preserve the
original red-green execution recipe; they are not the current status tracker.

## Global constraints

- Work inline in the current checkout; do not dispatch subagents.
- Leave changes uncommitted. Commit steps are intentionally omitted despite the generic execution skill.
- Use test-driven development for every production behavior change: focused failing test, observed expected failure, minimal implementation, focused pass, then phase regression gate.
- Preserve unrelated working-tree changes.
- Git-tracked records are authoritative; LanceDB must always be rebuildable.
- Reviews and assignments are shared pull-request content.
- Separate branches/worktrees are the multi-writer boundary; only one backend mutates one workspace at a time.
- Selected context boosts related search results but never hides global matches unless the writer applies an explicit scope filter.
- A dirty Meridian-Rift checkout is always a hard stop for export apply.
- GitHub Desktop owns authentication, pull, push, pull requests, and complex merges.
- Use Meridian-MCP for DreamMaker and Meridian-Rift inspection or verification when those gates become relevant.

---

## File and interface map

### Store safety

- `webapp/store/db.py`: LanceDB connection and typed key operations. Produces `record_hash_for`, `get_row_by_key`, `delete_row_by_key`, and corrected snapshot synchronization.
- `webapp/store/schema.py`: projection columns, store format metadata, and record/embedding hash fields.
- `webapp/store/embeddings.py`: model identity and explicit unavailable/degraded behavior.
- `webapp/tests/test_store.py`: store-level regression coverage.

### Canonical writer records

- `tools/lore_editor/records.py` (new): record kinds, canonical paths, serialization, hashes, and atomic file replacement.
- `tools/lore_editor/reconcile.py` (new): Git-record-to-LanceDB projection and recovery export.
- `tools/lore_editor/source.py`: loads canonical records rather than treating source paths as virtual.
- `tools/lore_editor/workspace.py`: authoritative and derived workspace layout.
- `tools/lore_editor/taxonomy.py`: group/review/assignment domain operations over canonical records.
- `tools/lore_editor/api.py`: optimistic write coordinator and deterministic artifact regeneration.
- `tools/lore_editor/tests/test_records.py` (new): canonical formatting, hashing, filenames, and atomicity.
- `tools/lore_editor/tests/test_reconcile.py` (new): fresh-clone, branch-change, deletion, and rebuild coverage.

### API and workspace ownership

- `webapp/api/models.py`: expected-hash requests, conflict responses, projection health, and contextual-search models.
- `webapp/api/errors.py`: stable 409 conflict mapping.
- `webapp/api/context.py`: selected workspace identity and single-writer lease.
- `webapp/api/routes/lore.py`: typed optimistic authoring endpoints.
- `webapp/api/routes/search.py`: global hybrid ranking plus selected-context boost.
- `webapp/workspace_lock.py` (new): process-held workspace mutation lease.
- `webapp/git_adapter.py`: branch/HEAD/content-revision observation and owned-path commit scope.

### Frontend contract

- `webapp/frontend/src/lib/api-schema.d.ts`: checked-in generated contract.
- `webapp/frontend/src/store/appStore.ts`: shared selected entity/context.
- `webapp/frontend/src/components/GlobalSearch.tsx`: contextual boost disclosure and exact-record navigation.

---

### Task 1: Block destructive identifiers and key collisions

**Files:**

- Modify: `webapp/store/db.py`
- Modify: `tools/lore_editor/validation.py`
- Modify: `tools/lore_editor/api.py`
- Modify: `tools/lore_editor/taxonomy.py`
- Modify: `webapp/tests/test_store.py`
- Modify: `tools/lore_editor/tests/test_api_write.py`
- Modify: `tools/lore_editor/tests/test_taxonomy.py`

**Interfaces:**

- Produces: `get_row_by_key(table, key_field: str, key: str) -> dict[str, object] | None`
- Produces: `delete_row_by_key(table, key_field: str, key: str) -> None`
- Produces: `validate_entry_id(value: object) -> str`
- Replaces review/assignment LanceDB logical IDs with the canonical type path.

- [ ] Add `test_delete_row_by_key_treats_predicate_text_as_data` to seed two overrides, delete `missing' OR true OR id = 'x`, and assert both seeded rows remain.
- [ ] Run `python -m unittest webapp.tests.test_store.StoreTests.test_delete_row_by_key_treats_predicate_text_as_data -v`; verify RED because `delete_row_by_key` does not exist.
- [ ] Add store-private SQL literal escaping and trusted key-field validation, then implement `get_row_by_key` and `delete_row_by_key` in `webapp/store/db.py`.
- [ ] Replace every authoring-path `get_row(...f"...")` and `delete_rows(...f"...")` call with the key API.
- [ ] Run the focused store test; verify PASS.
- [ ] Add validation tests for `items.radio`, `items-radio_2`, an empty ID, a leading punctuation mark, whitespace, a quote, and predicate operators. The accepted grammar is the existing schema rule `^[A-Za-z0-9][A-Za-z0-9._-]*$`.
- [ ] Run the focused validation tests; verify RED because runtime validation currently accepts unsafe non-empty strings.
- [ ] Implement `validate_entry_id` once and call it from shape validation, create, update, and delete domain entry points.
- [ ] Run focused validation and API-write tests; verify PASS.
- [ ] Add a taxonomy regression proving reviews for `/obj/a_b` and `/obj/a/b` coexist and deleting either preserves the other.
- [ ] Run the focused taxonomy test; verify RED because `_target_slug` collides.
- [ ] Use canonical type paths as LanceDB review/assignment IDs and the safe key API for deletion. Remove `_target_slug` when no caller remains.
- [ ] Run `python -m unittest webapp.tests.test_store tools.lore_editor.tests.test_validation tools.lore_editor.tests.test_api_write tools.lore_editor.tests.test_taxonomy -v`; verify PASS.

### Task 2: Separate complete-record and embedding hashes

**Files:**

- Modify: `webapp/store/db.py`
- Modify: `webapp/store/schema.py`
- Modify: `webapp/store/embeddings.py`
- Modify: `webapp/tests/test_store.py`

**Interfaces:**

- Produces: `record_hash_for(row: Mapping[str, object]) -> str`, excluding only derived `vector`, `record_hash`, and `embedding_hash` fields.
- Produces: `embedding_hash_for(text: str, model_id: str) -> str`.
- Stores `record_hash` and `embedding_hash` separately in every projected row.

- [ ] Add a store test that synchronizes a catalog row, changes only `raw_json.field_profile`, keeps `text` identical, and asserts the stored field changes without another embedding call.
- [ ] Run the focused test; verify RED because the text hash causes the row to be skipped.
- [ ] Define canonical hash serialization using UTF-8 JSON with sorted keys and compact separators.
- [ ] Rename the current `content_hash` column to `record_hash` in the expected schemas and add `embedding_hash`.
- [ ] Update snapshot comparison so complete-record changes write the row while unchanged embedding hashes reuse the existing vector.
- [ ] Add a test that changing only text or the embedding model ID invokes embedding and updates both hashes.
- [ ] Add a test that an unchanged complete record performs no write and no embedding.
- [ ] Run `python -m unittest webapp.tests.test_store -v`; verify PASS.

### Task 3: Make embedding degradation explicit and non-destructive

**Files:**

- Modify: `webapp/store/embeddings.py`
- Modify: `webapp/store/cli.py`
- Modify: `webapp/store/health.py`
- Modify: `webapp/api/models.py`
- Modify: `webapp/tests/test_store.py`
- Modify: `webapp/tests/test_store_health.py`

**Interfaces:**

- Produces: `EmbeddingUnavailableError`.
- Produces: `embedding_status() -> EmbeddingStatus` with `available`, `model_id`, and optional `reason`.
- A rebuild never writes zero vectors when the model is unavailable.

- [ ] Add a test that a model-load failure makes `rebuild_embeddings` fail while preserving previously stored vectors.
- [ ] Run the focused test; verify RED because zero vectors are currently treated as success.
- [ ] Introduce explicit embedding status and make write/rebuild callers choose between keyword-only projection and semantic-vector mutation.
- [ ] Preserve existing vectors when semantic generation is unavailable.
- [ ] Surface keyword-only degradation through store health without exposing exception traces.
- [ ] Run focused store and health tests; verify PASS.

### Task 4: Restore canonical group records and deterministic record primitives

**Files:**

- Create: `tools/lore_editor/records.py`
- Create: `tools/lore_editor/tests/test_records.py`
- Restore: `tools/lore_editor/content/groups/celestial-bodies.json`
- Restore: `tools/lore_editor/content/groups/groups-of-interest.json`
- Restore: `tools/lore_editor/content/groups/interdyne.json`
- Restore: `tools/lore_editor/content/groups/languages.json`
- Restore: `tools/lore_editor/content/groups/manufacturing-companies.json`
- Restore: `tools/lore_editor/content/groups/nanotrasen.json`
- Restore: `tools/lore_editor/content/groups/nova-sector.json`
- Restore: `tools/lore_editor/content/groups/races.json`
- Do not restore: `tools/lore_editor/content/reviews/review.datum-language-buzzwords.json`

**Interfaces:**

- Produces: `RecordKind = Literal["override", "group", "review", "assignment"]`.
- Produces: `canonical_record_bytes(payload: Mapping[str, object]) -> bytes`.
- Produces: `canonical_record_hash(payload: Mapping[str, object]) -> str`.
- Produces: `record_path(repo_root: Path, kind: RecordKind, record_id: str) -> Path`.
- Produces: `atomic_write_record(path: Path, payload: Mapping[str, object]) -> None`.

- [ ] Add tests for UTF-8, sorted keys, two-space indentation, LF endings, one trailing newline, stable hashes, path containment, and collision-free type-path filenames.
- [ ] Run `python -m unittest tools.lore_editor.tests.test_records -v`; verify RED because the module does not exist.
- [ ] Implement the minimal canonical serialization, record-path, and atomic replacement functions.
- [ ] Run the focused tests; verify PASS.
- [ ] Recover the eight group files byte-for-byte from `8f65061^`, then normalize only if the canonical serializer test requires it.
- [ ] Add a test that discovers exactly those eight group IDs and no restored review.
- [ ] Validate every restored group through the domain group parser.
- [ ] Run `python -m unittest tools.lore_editor.tests.test_records tools.lore_editor.tests.test_taxonomy -v`; verify PASS.

### Task 5: Reconcile Git records into a versioned LanceDB projection

**Files:**

- Create: `tools/lore_editor/reconcile.py`
- Create: `tools/lore_editor/tests/test_reconcile.py`
- Create: `webapp/store/metadata.py`
- Modify: `webapp/store/schema.py`
- Modify: `webapp/store/db.py`
- Modify: `webapp/store/cli.py`
- Modify: `tools/lore_editor/source.py`
- Modify: `tools/lore_editor/workspace.py`

**Interfaces:**

- Produces: `ProjectionRevision(schema_version, content_revision, embedding_model_id, state)`.
- Produces: `scan_canonical_records(repo_root: Path) -> CanonicalSnapshot`.
- Produces: `reconcile_projection(repo_root: Path, *, rebuild: bool = False, on_progress=None) -> ReconcileResult`.
- Produces CLI commands `status`, `reconcile`, `rebuild`, `backup`, and `restore`.

- [ ] Add a fresh-clone test with Git group/override/review/assignment fixtures and no database; assert reconciliation creates the expected rows.
- [ ] Run the test; verify RED because no reconciler exists.
- [ ] Implement deterministic filesystem scanning and whole-snapshot validation before any projection mutation.
- [ ] Build a new versioned projection directory and atomically switch a small active-generation metadata file only after success.
- [ ] Add interrupted-build and corrupt-active-generation tests; verify the previous projection remains readable.
- [ ] Add addition, update, and Git-deletion tests using complete-record hashes.
- [ ] Add backup/export and restore tests. Recovery exports are labeled snapshots and never become an implicit authority change.
- [ ] Add a test that changing branch content revision forces reconciliation before reads are considered current.
- [ ] Run `python -m unittest tools.lore_editor.tests.test_reconcile webapp.tests.test_store -v`; verify PASS.

### Task 6: Make all authoring writes Git-durable and optimistic

**Files:**

- Create: `tools/lore_editor/write_coordinator.py`
- Modify: `tools/lore_editor/api.py`
- Modify: `tools/lore_editor/taxonomy.py`
- Modify: `tools/lore_editor/source.py`
- Modify: `webapp/api/models.py`
- Modify: `webapp/api/errors.py`
- Modify: `webapp/api/routes/lore.py`
- Modify: `tools/lore_editor/tests/test_api_write.py`
- Modify: `tools/lore_editor/tests/test_review_api.py`
- Modify: `webapp/tests/test_api.py`

**Interfaces:**

- Produces: `RecordConflict(record_id, expected_hash, current_hash, base, current, proposed)` mapped to HTTP 409.
- Update/delete requests require `expected_record_hash`; create requires absence.
- Every successful mutation atomically changes one canonical file, regenerates deterministic output, and then updates or invalidates LanceDB.

- [ ] Add a same-record two-client test: both load hash A, client one saves B, client two attempts C with hash A, and receives a conflict while B remains canonical.
- [ ] Run the test; verify RED because requests have no expected hash.
- [ ] Implement a repository-scoped write coordinator and compare-and-swap over canonical files.
- [ ] Move override, group, review, and assignment writes to canonical record files.
- [ ] If generation fails, restore the canonical file atomically; do not restore an old LanceDB row over another writer.
- [ ] If LanceDB projection update fails after durability, return the successful canonical result with projection state `stale` and queue/require reconciliation.
- [ ] Add create/create, update/delete, and different-record concurrency tests.
- [ ] Add FastAPI 409 response-model tests with base/current/proposed payloads.
- [ ] Run Lore Editor and FastAPI focused suites; verify PASS.

### Task 7: Enforce one mutation owner per workspace and branch-aware state

**Files:**

- Create: `webapp/workspace_lock.py`
- Create: `webapp/tests/test_workspace_lock.py`
- Modify: `webapp/api/context.py`
- Modify: `webapp/api/app.py`
- Modify: `webapp/git_adapter.py`
- Modify: `webapp/api/live.py`
- Modify: relevant API models/routes and tests.

**Interfaces:**

- Produces: `WorkspaceLease.acquire(workspace: Path)`, `release()`, and read-only owner metadata.
- Produces: `WorkspaceRevision(worktree_id, branch, head, content_revision, projection_revision)`.
- Mutations return 409 while Git content and projection revisions disagree.

- [ ] Add a process-level test proving a second backend cannot acquire a mutation lease for the same resolved workspace.
- [ ] Run it; verify RED because no lease exists.
- [ ] Implement a lock file containing PID, process start identity, workspace path, and random session ID; reclaim only demonstrably stale locks.
- [ ] Acquire/release through FastAPI lifespan, including startup-failure cleanup.
- [ ] Add tests proving separate worktrees acquire independent leases.
- [ ] Observe Git branch, `HEAD`, and owned-content hashes; publish revision changes over WebSocket.
- [ ] Block mutation until reconciliation catches up after branch or owned-content change.
- [ ] Run workspace, Git adapter, live-state, and API tests; verify PASS.

### Task 8: Restrict commits and provenance to canonical owned paths

**Files:**

- Modify: `webapp/git_adapter.py`
- Modify: Git API models/routes.
- Modify: `webapp/frontend/src/tools/fileManagement/RepositoryPanel.tsx`
- Modify: `tools/lore_editor/export.py`
- Modify: `webapp/api/routes/export.py`
- Modify: `webapp/api/models.py`
- Modify: corresponding Python and frontend tests.

**Interfaces:**

- Produces: owned-change records with path, kind, record ID, and summary.
- Commit requests contain an explicit selected path list validated against owned roots.
- Export provenance contains canonical `content_revision`, tool `HEAD`, and source-game commit.

- [ ] Add a Git adapter test with one canonical record, one generated artifact, and one unrelated file; assert the unrelated file cannot be staged through the app API.
- [ ] Run it; verify RED because current commit scope accepts status paths wholesale.
- [ ] Implement owned-root classification and exact selected-path staging.
- [ ] Preserve and report pre-existing index state if a bounded Git command times out or commit fails.
- [ ] Remove `force` from export API and implementation; add a dirty-checkout 409 regression.
- [ ] Update RepositoryPanel to require explicit file selection and show record summaries.
- [ ] Add provenance reconstruction test: a fresh checkout at the recorded commit plus the catalog seed reproduces the generated DM bytes.
- [ ] Run Git, export, API, and frontend focused tests; verify PASS.

### Task 9: Implement globally ranked contextual hybrid search

**Files:**

- Modify: `webapp/store/search.py`
- Modify: `webapp/api/models.py`
- Modify: search API route.
- Modify: `webapp/frontend/src/store/appStore.ts`
- Modify: `webapp/frontend/src/components/GlobalSearch.tsx`
- Modify: `webapp/frontend/src/lib/api-schema.d.ts`
- Modify: Python and frontend search tests.

**Interfaces:**

- Search request includes optional `selected_context` with tool, record kind, record ID/type path, group/module, and explicit scope filters.
- Search response includes globally ordered results, score components, context reason, semantic mode, and exact navigation target.
- Context adds a bounded ranking boost; it never excludes global matches without explicit scopes.

- [ ] Add a store test proving `limit=6` returns at most six results across all tables and that the query is embedded once.
- [ ] Run it; verify RED because current code returns up to six per table and embeds per table.
- [ ] Refactor candidate collection and apply reciprocal-rank fusion globally.
- [ ] Add tests proving related context wins close rankings while a stronger unrelated global result remains visible.
- [ ] Add deterministic tie-breaking by final score, table priority, and canonical ID.
- [ ] Add keyword-only result tests and visible semantic status.
- [ ] Extend shared selected context and exact-record navigation in the frontend.
- [ ] Run Python and frontend search suites; verify PASS.

### Task 10: Add catalog seed and clean-checkout bootstrap gates

**Files:**

- Create: catalog seed manifest model and downloader under `tools/lore_editor/catalog_seed.py`.
- Modify: launcher/bootstrap code.
- Modify: maintainer/writer guides.
- Create: catalog-seed tests and clean-checkout integration test.

**Interfaces:**

- A seed manifest identifies schema version, source-game commit, generator version, byte size, SHA-256, and download location.
- Bootstrap verifies the downloaded bytes before activation and can rebuild locally through the existing catalog scanner.

- [ ] Add tests for valid cached seed, hash mismatch, interrupted download, offline fallback, and incompatible schema.
- [ ] Run them; verify RED because seed bootstrap does not exist.
- [ ] Implement download-to-temporary, hash verification, and atomic activation.
- [ ] Never require a seed download to preserve or edit existing canonical writer records.
- [ ] Add a clean-checkout integration test that restores groups, activates a seed, reconciles LanceDB, and serves the review feed.
- [ ] Run the focused integration test; verify PASS.

### Task 11: Establish the foundation regression gate

**Files:**

- Create: `.github/workflows/ci.yml`
- Modify: `pyproject.toml`
- Modify: `webapp/frontend/package.json`
- Track: `webapp/frontend/src/lib/api-schema.d.ts`
- Modify: `.gitignore`
- Modify: `README.md`, `references/maintainer-guide.md`, and `references/writer-guide.md`.

**Interfaces:**

- A clean Windows checkout can install locked dependencies, regenerate contracts, run tests, reconcile a fixture workspace, and build the SPA.

- [ ] Fix current Ruff findings through behavior-neutral edits, running focused tests for touched modules.
- [ ] Make Pyright installation and configuration reproducible.
- [ ] Check in generated API types and add regeneration-diff verification.
- [ ] Add Windows CI jobs for Python unit/integration groups, Ruff, Pyright, `npm ci`, Vitest, typecheck, production build, and `git diff --check`.
- [ ] Add an installed-wheel smoke test outside the source tree so omitted packages/resources fail CI.
- [ ] Update documentation to state Git authority, LanceDB projection, branch/worktree rules, catalog seeds, conflicts, backup/restore, and dirty-export refusal.
- [ ] Run the full foundation gate locally and record exact counts/timings.

## Execution order and checkpoints

1. Tasks 1–3 are the immediate P0/P1 data-safety batch.
2. Task 4 restores approved records only after canonical primitives exist.
3. Tasks 5–7 establish the collaboration and concurrency boundary.
4. Tasks 8–10 connect Git, search, and fresh-checkout bootstrap.
5. Task 11 is the complete foundation gate.

After Tasks 1–3, pause for an inline review of the changed diff and focused verification evidence. Continue automatically if the review finds no product decision or environment blocker. Do not commit.

## Completion record and next queue

Tasks 1-11 passed the current-tree foundation gate on 2026-08-23:

- Python: 401 tests passed in 263.732 seconds.
- Frontend: 85 tests across 26 files passed in 7.09 seconds.
- Ruff: clean.
- Pyright: 0 errors and 0 warnings.
- TypeScript: clean.
- OpenAPI: 47 paths regenerated with no declaration drift.
- Packaging: an isolated wheel built, installed into a clean temporary target, and imported the API,
  search, catalog-seed, and graph packages from outside the source tree.
- Production SPA: two consecutive builds produced the same complete artifact-tree SHA-256,
  `2E51C416EBFE2002EE71441BBEB80F209BBEA875A381B625AA4706222A2F4B01`.
- Workflow YAML, launcher PowerShell, and `git diff --check`: clean.
- The shipped `.cmd` launcher was exercised through FastAPI and the production SPA against the real
  17,500-target catalog and authoritative Meridian-Rift graph, then shut down without leaving its port
  open.

Remaining work is deliberately outside the foundation tasks:

1. Run destructive Lore create/edit/conflict/delete acceptance against a disposable branch/worktree.
2. Complete the Content Graph keyboard-only fallback, direct canvas-drag, and disposable marker-repair
   playtests.
3. End the short rollback window and delete the retired legacy server/UI assets after those gates pass.
4. Execute the Phase 5 packaging spike and record binary size, offline first start, memory, rebuild time,
   and complete process-tree shutdown behavior.
5. Prepare the multi-writer changes as a reviewable branch/PR only when Zoe explicitly asks for Git
   staging, commits, or publication.

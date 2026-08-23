# Aphelion Content Tools Agent Standards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the misplaced game-code instructions with locally complete standards for the FastAPI/Solid application, canonical structured content, safe export, verification, and Meridian-Rift integration.

**Architecture:** A thin root `AGENTS.md` and compatibility pointer route agents to focused development references. Existing active maintainer/writer documentation is reconciled in place, while a standard-library checker validates routing, local links, required safety language, and verification commands in CI.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic 2, Ruff, Pyright, Solid, TypeScript, Vite, Vitest, npm, Markdown, Windows `.cmd`/PowerShell launcher, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-23-agent-standards-design.md`

## Global Constraints

- `references/maintainer-guide.md` is normative architecture for this application; historical preferences are supporting rationale.
- The Solid SPA is the target implementation. Legacy pages are transitional and receive no new behavior except documented migration work.
- Pydantic owns HTTP schemas; TypeScript API declarations are generated and may not be duplicated by hand.
- Structured files under `tools/lore_editor/content/` are canonical. LanceDB/catalog projections are rebuildable derived data.
- Generated DreamMaker is downstream output and is never the writer-facing canonical source.
- Export writes only `modular_aphelion/modules/lore_overhaul/code/generated_lore_overrides.dm` into a clean, compatible Meridian-Rift checkout.
- There is no dirty-checkout force path.
- The browser receives no GitHub or AutoWiki credentials. GitHub Desktop owns authentication, pushes, pull requests, and complex merges.
- The real `Launch Aphelion Content Tools.cmd` path is part of completion evidence.
- Preserve all unrelated dirty working-tree changes. Reconcile edits to `README.md`, `references/maintainer-guide.md`, and `references/writer-guide.md` rather than replacing them.
- Changes remain uncommitted for maintainer review; each task ends with a status/diff checkpoint.

---

## File map

- `AGENTS.md`: concise local repository instructions and required-reading router.
- `.agents/AGENTS.md`: compatibility pointer to root policy; no independent game-code policy.
- `references/development/README.md`: development-guide index.
- `references/development/backend-and-schema.md`: FastAPI, Pydantic, services, errors, package, Ruff, and Pyright.
- `references/development/frontend-and-state.md`: SPA boundaries, shared concerns, accessibility, and legacy transition.
- `references/development/data-and-generation.md`: canonical records, IDs, migrations, projections, generated DM, and AutoWiki fields.
- `references/development/content-graph.md`: modular-root scanning, ownership, historical marker tolerance, and operation states.
- `references/development/export-safety.md`: prepare/apply invariants, repository checks, atomicity, and GitHub Desktop handoff.
- `references/development/verification.md`: exact Python/frontend/schema/launcher/export/downstream gates.
- `references/development/meridian-integration.md`: ownership and acceptance boundary with Meridian-Rift and Meridian-MCP.
- `tools/docs/check_agent_docs.py`: required-file, local-link, safety-language, and command validator.
- `tools/docs/tests/test_agent_docs.py`: isolated fixture tests and real-repository assertion.
- `.github/workflows/ci.yml`: document validation gate.

### Task 1: Preserve active documentation changes and install local routing

**Files:**
- Create: `AGENTS.md`
- Modify: `.agents/AGENTS.md`
- Create: `references/development/README.md`
- Create: `tools/docs/__init__.py`
- Create: `tools/docs/check_agent_docs.py`
- Create: `tools/docs/tests/__init__.py`
- Create: `tools/docs/tests/test_agent_docs.py`

**Interfaces:**
- Consumes: local repository paths and Markdown links.
- Produces: `check_repository(root: Path) -> list[str]` and unambiguous agent discovery.

- [ ] **Step 1: Inventory overlapping user changes before editing**

Run:

```powershell
git diff -- README.md references/maintainer-guide.md references/writer-guide.md pyproject.toml
git status --short
```

Expected: active SPA/data-integrity edits are visible. Treat them as the baseline; do not restore older text from HEAD.

- [ ] **Step 2: Write failing checker tests**

```python
class AgentDocumentTests(unittest.TestCase):
	def test_cross_repository_game_policy_is_rejected(self) -> None:
		with temporary_repository() as root:
			(root / "AGENTS.md").write_text(
				"# Meridian Rift agent instructions\nmodular_nova/readme.md\n",
				encoding="utf-8",
			)
			errors = check_repository(root)
			self.assertIn("AGENTS.md must identify Aphelion Content Tools", errors)

	@unittest.skip("enabled in Task 5 after the complete guide set exists")
	def test_checked_in_repository_is_consistent(self) -> None:
		root = Path(__file__).resolve().parents[3]
		self.assertEqual(check_repository(root), [])
```

- [ ] **Step 3: Run the tests and confirm failure**

Run: `python -m unittest tools.docs.tests.test_agent_docs -v`

Expected: failure because the checker and root instructions do not exist.

- [ ] **Step 4: Write the root instructions**

Identify the repository as the Content Tools Python/TypeScript application. Include required reading, search-before-edit behavior, schema ownership, SPA/legacy boundary, canonical data, export safety, GitHub Desktop ownership, real-entry-point verification, hostile path/input handling, dirty-worktree preservation, and no-commit policy.

- [ ] **Step 5: Replace `.agents/AGENTS.md` with a compatibility pointer**

Keep only a short statement that policy lives at `../AGENTS.md`, with a link to `../references/maintainer-guide.md`. Remove the duplicated Meridian-Rift/Dogmos rules from this repository; do not migrate them elsewhere because Meridian-Rift receives its own guide set.

- [ ] **Step 6: Implement the documentation checker**

Use `pathlib`, `re`, and `urllib.parse` only. Validate required files, local Markdown links, root identity, links to all development guides, loopback/credential/export constraints, and exact verification commands. Ignore external HTTP links except for syntactic parsing.

- [ ] **Step 7: Run focused tests**

Run: `python -m unittest tools.docs.tests.test_agent_docs -v`

Expected: isolated pointer/identity tests pass. Keep the real-repository assertion skipped with a clear reason until Tasks 2–5 create the full guide set.

- [ ] **Step 8: Review checkpoint**

Run: `git diff --check` and `git status --short`.

Expected: existing active application changes remain present; Task 1 adds routing/checker files without modifying their content.

### Task 2: Reconcile the normative maintainer architecture

**Files:**
- Modify: `references/maintainer-guide.md`
- Modify: `README.md`
- Modify: `references/development/README.md`
- Modify: `tools/docs/tests/test_agent_docs.py`

**Interfaces:**
- Consumes: current dirty maintainer-guide/README changes as the source baseline.
- Produces: explicit normative status, target/transitional architecture, and links to focused guides.

- [ ] **Step 1: Re-read the current working-tree versions**

Run:

```powershell
Get-Content -Raw references/maintainer-guide.md
Get-Content -Raw README.md
git diff -- references/maintainer-guide.md README.md
```

Expected: the latest worker, catalog-seed, projection, commit-selection, SPA, and export decisions are visible before patching.

- [ ] **Step 2: Add architecture-status assertions**

Assert the maintainer guide explicitly contains:

```text
Normative status
Target architecture: FastAPI and the Solid SPA
Legacy pages are transitional and must not receive new product behavior
Pydantic models are the canonical HTTP schema
tools/lore_editor/content/ is canonical authored source
```

- [ ] **Step 3: Add a concise status section to the maintainer guide**

State what is normative, what remains transitional, and how the focused development guides divide responsibility. Preserve all active details about the out-of-process worker, durable runs, catalog seed, projections, typed boundary, selected commits, and staged export.

- [ ] **Step 4: Align the README entry points**

Keep writer-facing startup concise. Add links for contributors to root `AGENTS.md`, the maintainer guide, and the development index. Do not duplicate backend/frontend detail in the README.

- [ ] **Step 5: Run documentation tests and application text checks**

Run: `python -m unittest tools.docs.tests.test_agent_docs -v`

Expected: architecture-status tests pass; repository-completeness remains deferred until all guides exist.

Run: `git diff --check`

Expected: no whitespace errors.

- [ ] **Step 6: Review checkpoint**

Run: `git diff -- references/maintainer-guide.md README.md`

Expected: pre-existing additions remain intact and the new changes are limited to status/routing clarity.

### Task 3: Backend/schema and frontend/state guides

**Files:**
- Create: `references/development/backend-and-schema.md`
- Create: `references/development/frontend-and-state.md`
- Modify: `references/development/README.md`
- Modify: `tools/docs/tests/test_agent_docs.py`

**Interfaces:**
- Consumes: `pyproject.toml`, FastAPI/Pydantic modules, frontend package scripts, and current maintainer guide.
- Produces: framework boundaries and exact ownership rules for contributors.

- [ ] **Step 1: Add required-content tests**

Backend assertions require `Pydantic owns the HTTP schema`, `stable error taxonomy`, `framework-agnostic domain logic`, `pip install -e ".[dev]"`, `python -m ruff check .`, and `python -m pyright`.

Frontend assertions require `one application shell`, `one tool registry`, `one typed API client`, `one live-connection owner`, `one shared application-store path`, `npm run gen:api`, accessibility, and the no-new-legacy-behavior rule.

- [ ] **Step 2: Write the backend/schema guide**

Map current responsibilities across `webapp/api`, `webapp/store`, `webapp/tooling.py`, and `tools/*` domain packages. Define error payload stability, route/service separation, package/import rules, type-boundary honesty, generated OpenAPI contract workflow, and tests required for a schema change.

- [ ] **Step 3: Write the frontend/state guide**

Map `AppShell`, tool pages, shared components, `src/lib/api.ts`, generated `api-schema.d.ts`, and `appStore`. Require domain language, actionable errors, scoped CSS, keyboard/accessibility tests, and no parallel APIs/WebSockets/stores.

- [ ] **Step 4: Run checker tests**

Run: `python -m unittest tools.docs.tests.test_agent_docs -v`

Expected: backend/frontend ownership and command assertions pass.

- [ ] **Step 5: Verify referenced commands are real**

Run: `python -m ruff check tools/docs`

Run: `python -m pyright`

Run: `npm --prefix webapp/frontend run gen:api`

Run: `npm --prefix webapp/frontend run typecheck`

Expected: commands resolve. If existing unrelated application failures occur, record them precisely and do not weaken the documented gate.

- [ ] **Step 6: Review checkpoint**

Run: `git diff --check` and `git status --short`.

Expected: only new guides/checker work overlaps Task 3.

### Task 4: Canonical data, generation, and export-safety contracts

**Files:**
- Create: `references/development/data-and-generation.md`
- Create: `references/development/content-graph.md`
- Create: `references/development/export-safety.md`
- Modify: `references/maintainer-guide.md`
- Modify: `references/writer-guide.md`
- Modify: `references/development/README.md`
- Modify: `tools/docs/tests/test_agent_docs.py`

**Interfaces:**
- Consumes: current record, projection, catalog, manifest, generation, reconciliation, and export implementation.
- Produces: one canonical ownership chain and an exact prepare/apply refusal contract.

- [ ] **Step 1: Reconcile dirty writer/maintainer text before editing**

Run:

```powershell
git diff -- references/maintainer-guide.md references/writer-guide.md
```

Expected: current catalog-bootstrap, selected-record commit, conflict, and no-force-export language is preserved as the baseline.

- [ ] **Step 2: Add canonical-data assertions**

Require the data guide to define stable IDs, schema/manifest versions, references/taxonomy ownership, validation severities, record hashes, conflicts, reconciliation, projection generations, migrations, deterministic output, artifact hashes, and AutoWiki fields.

- [ ] **Step 3: Write the data/generation guide**

State that authored records are canonical, catalog and LanceDB are derived, generated DM is reproducible output, and schema changes update Pydantic validation, generated TypeScript, migrations/compatibility, tests, and docs together.

- [ ] **Step 4: Add export-safety assertions**

Require compatible Meridian remote/identity, `tgstation.dme`, clean/conflict-free status, stable revisions, canonical-content revision, manifest/schema versions, source/base/final hashes, allowed destination, parent containment, atomic replace, rollback, and no force override.

- [ ] **Step 5: Write the Content Graph guide**

Require scans of both `modular_nova` and `modular_aphelion`, preserved ownership metadata, tolerant read support for historical NOVA/APHELION marker forms, unresolved-marker diagnostics instead of whole-graph failure, canonical future APHELION output only, progress/cancellation where supported, bounded diagnostics, and distinct loading/empty/failed/completed states.

- [ ] **Step 6: Write the export-safety guide**

Describe prepare and apply as separate state transitions. State that tests use temporary or dedicated checkouts, the app never exports into the maintainer's dirty production checkout, and GitHub Desktop receives the post-apply review handoff.

- [ ] **Step 7: Align existing guides without duplicating the contract**

Replace long duplicated maintainer/writer explanations with concise workflow guidance and links where doing so does not remove necessary audience-specific recovery steps. Preserve all current user-authored data-integrity decisions.

- [ ] **Step 8: Run focused domain and documentation tests**

Run: `python -m unittest tools.lore_editor.tests.test_records tools.lore_editor.tests.test_reconcile tools.lore_editor.tests.test_export tools.lore_editor.tests.test_validation tools.content_graph.tests.test_marker_edit tools.content_graph.tests.test_graph -v`

Run: `python -m unittest tools.docs.tests.test_agent_docs -v`

Expected: domain invariants and documentation assertions pass.

- [ ] **Step 9: Review checkpoint**

Run: `git diff --check` and `git status --short`.

Expected: no generated DM, catalog projection, stage, or Meridian-Rift file changed.

### Task 5: Verification and cross-repository integration guides

**Files:**
- Create: `references/development/verification.md`
- Create: `references/development/meridian-integration.md`
- Modify: `AGENTS.md`
- Modify: `references/development/README.md`
- Modify: `tools/docs/tests/test_agent_docs.py`

**Interfaces:**
- Consumes: checked-in CI, launcher, Meridian-Rift build policy, and Meridian-MCP responsibility.
- Produces: exact local/full/downstream evidence matrix.

- [ ] **Step 1: Add exact-command assertions**

Require these commands verbatim:

```text
python -m ruff check .
python -m pyright
python -m unittest discover
npm --prefix webapp/frontend run gen:api
npm --prefix webapp/frontend test -- --run
npm --prefix webapp/frontend run typecheck
npm --prefix webapp/frontend run build
git diff --check
```

- [ ] **Step 2: Write the verification matrix**

Separate focused backend, full Python, schema drift, frontend unit, frontend typecheck, production build, accessibility, deterministic generation, staged export, wheel smoke, real launcher, and Meridian downstream gates. For each, state command, evidence, and when it is required.

- [ ] **Step 3: Write the Meridian integration guide**

State that Meridian-Rift owns DM placement/full build/final acceptance, Content Tools owns structured data/schema/export, and Meridian-MCP owns bounded source navigation/diagnostics. PowerShell owns Windows orchestration. AutoWiki publication remains CI-only and credentials never enter the browser.

- [ ] **Step 4: Add the evidence report template**

```text
Command or real entry point:
Scope: focused | repository-wide | integration | downstream
Result:
Observed artifact/readiness marker:
Required gates not run:
Existing unrelated failures:
```

- [ ] **Step 5: Enable the real-repository documentation assertion**

Remove the temporary skip. Validate all required files, links, architecture statements, safety invariants, and exact commands against the checkout.

- [ ] **Step 6: Run documentation and full noninteractive gates**

Run: `python -m unittest tools.docs.tests.test_agent_docs -v`

Run: `python -m ruff check .`

Run: `python -m pyright`

Run: `python -m unittest discover`

Run: `npm --prefix webapp/frontend run gen:api`

Run: `npm --prefix webapp/frontend test -- --run`

Run: `npm --prefix webapp/frontend run typecheck`

Run: `npm --prefix webapp/frontend run build`

Expected: all gates pass, or existing unrelated failures are reported without being attributed to the documentation change.

- [ ] **Step 7: Review checkpoint**

Run: `git diff --check` and `git status --short`.

Expected: no unrelated working-tree file was altered by formatting or generation without explicit review.

### Task 6: CI integration and real launcher/export validation

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `references/development/verification.md`
- Modify: `references/maintainer-guide.md`

**Interfaces:**
- Consumes: documentation checker, existing Foundation gate, production SPA, compatible clean test checkout.
- Produces: enforced documentation consistency and current real-entry-point evidence.

- [ ] **Step 1: Add document validation to CI**

After Python installation and before application tests, add:

```yaml
- name: Agent documentation
  run: python tools/docs/check_agent_docs.py
```

`python -m unittest discover` already includes `tools/docs/tests/test_agent_docs.py`; do not add a redundant second test invocation to CI.

- [ ] **Step 2: Run the complete CI command sequence locally**

Run the commands from `.github/workflows/ci.yml` in order: install editable dev package, frontend `npm ci`, API generation/drift review, Ruff, Pyright, Python tests, frontend tests/typecheck/build, wheel smoke, and `git diff --check`.

Expected: results match the documented matrix. Because this working tree is dirty, inspect generated diffs instead of using a blanket reset.

- [ ] **Step 3: Parse and exercise the real launcher**

Run:

```powershell
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
	(Resolve-Path 'tools/launcher/launch.ps1'),
	[ref]$null,
	[ref]$errors
) | Out-Null
if ($errors.Count) { $errors | Format-List; exit 1 }
cmd.exe /d /c '"Launch Aphelion Content Tools.cmd"'
```

Expected: PowerShell parses cleanly; the `.cmd` resolves its repository root, starts the FastAPI production SPA on loopback, prints `LORE_EDITOR_URL=...`, and opens the browser. Manually close the launcher after confirming Home, Lore Editor, Content Graph, and File Management load. Do not leave the server running.

- [ ] **Step 4: Validate staged export using a dedicated clean checkout**

Prepare an export from committed canonical fixture records, inspect its manifest, apply to a clean compatible Meridian-Rift test checkout, and verify that exactly `modular_aphelion/modules/lore_overhaul/code/generated_lore_overrides.dm` changes. Then dirty the checkout and confirm apply refuses without modifying it.

- [ ] **Step 5: Run downstream game acceptance when generated output changed**

If Task 4 or validation changed generated output, use Meridian-Rift's PowerShell/full-build and AutoWiki-related gates from its verification guide. If no generated output changed, record the downstream gate as not applicable rather than claiming it passed.

- [ ] **Step 6: Final working-tree review**

Run: `git diff --check`

Run: `git status --short`

Expected: authored documentation/checker/CI changes are identifiable among preserved application work, no credentials or local projection/stage data are tracked, and all changes remain uncommitted.

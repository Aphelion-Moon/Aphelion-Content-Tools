# Aphelion Content Tools agent instructions

Aphelion Content Tools is a Windows-first Python and TypeScript application for non-programmer
content and lore maintainers. It is not the Meridian-Rift game codebase. The application owns
structured authoring, catalog projections, local review workflows, and staged export; Meridian-Rift
owns DreamMaker placement, compilation, and final game acceptance.

## Required reading

Read [the maintainer guide](references/maintainer-guide.md) before meaningful changes. It is the
normative architecture. Use [the development guide index](references/development/README.md) for the
area being changed and [the writer guide](references/writer-guide.md) for user-visible workflows.

## Before editing

Research the current working tree with `rg` and inspect nearby implementations, tests, and active
documentation. This repository may contain uncommitted work from other agents or the maintainer;
preserve it and reconcile overlapping edits. Do not reset, commit, or push unless explicitly asked.

Add or update a behavioral test before changing behavior. Keep routes thin, domain logic
framework-agnostic, and changes at the smallest maintainable surface. Treat paths, repository state,
record identifiers, revisions, hashes, and browser input as hostile.

## Architecture and ownership

- FastAPI and the Solid SPA are the target architecture. Legacy pages are transitional and receive
  no new product behavior except an explicit migration step.
- Pydantic models own HTTP schemas. Regenerate `webapp/frontend/src/lib/api-schema.d.ts`; do not
  maintain duplicate request or response types.
- Use one application shell, tool registry, typed API client, live-connection owner, and shared
  application-store path. Tool pages may own local interaction state.
- Structured records under `tools/lore_editor/content/` are canonical. LanceDB, catalogs, caches,
  frontend builds, generated DreamMaker, and AutoWiki material are derived outputs.
- Every derived dataset must identify its source repository and revision, schema, extractor/indexer/model
  versions, content hash, and build state. Do not call a workspace current when a required dataset was
  built from another revision. Build multi-table datasets outside the active snapshot, verify them, and
  activate them with one atomic pointer change.
- Shared selected context, references, and search results are typed and revision-bound. Re-resolve or
  visibly invalidate them when the workspace snapshot changes. Keep exact, structural, full-text, and
  semantic search capabilities distinct in APIs and UI claims.
- A tool declaration includes its required datasets, jobs, search providers, mutation capabilities,
  integrations, and availability. Keep the frontend lazy-component registry validated against the
  backend capability catalog; do not rely on hand-synchronized metadata.
- The Content Graph reads both inherited NOVA and current APHELION forms without rewriting unrelated
  history. New Aphelion output uses the current APHELION convention.

## Repository and export safety

Bind application services to loopback and protect mutating HTTP and WebSocket paths with a per-launch
session, exact Host/Origin validation, and typed authorization. Never send GitHub, AutoWiki, remote
service, or broad integration credentials to browser code. A browser user grant must not be replaced by
a backend service credential. GitHub Desktop owns authentication, pushes, pull requests, and complex
merges unless a separately approved integration changes that boundary.

Export is a prepare/apply workflow. Apply only to a compatible, clean, conflict-free Meridian-Rift
checkout whose revision and generated-artifact hash still match the stage. Permit only
`modular_aphelion/modules/lore_overhaul/code/generated_lore_overrides.dm`, enforce resolved parent
containment, and use atomic replacement or complete rollback. There is no dirty-checkout force path.
Never hand-edit generated DM.

All other Meridian-Rift changes use the same staged change-set standard: compatible clean checkout,
repository write lease, allowed resolved paths, base revision and hashes, preview, validation, atomic
apply or complete rollback, and a receipt. Routes and tool pages do not write game files directly.

## Verification

Run focused tests while iterating, then the applicable repository-wide gates from
[the verification guide](references/development/verification.md). A focused test is not a completion
claim. Exercise the real `Launch Aphelion Content Tools.cmd` entry point for launcher or integrated UI
work. When generated DM changes, complete the downstream Meridian-Rift gates separately.

Report commands, scope, results, observed artifacts, gates not run, and unrelated existing failures.
Run `git diff --check` and inventory the final working tree before handoff. Leave changes uncommitted.

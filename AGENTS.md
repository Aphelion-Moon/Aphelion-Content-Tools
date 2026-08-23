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
- The Content Graph reads both inherited NOVA and current APHELION forms without rewriting unrelated
  history. New Aphelion output uses the current APHELION convention.

## Repository and export safety

Bind application services to loopback. Never send GitHub, AutoWiki, or other credentials to browser
code. GitHub Desktop owns authentication, pushes, pull requests, and complex merges.

Export is a prepare/apply workflow. Apply only to a compatible, clean, conflict-free Meridian-Rift
checkout whose revision and generated-artifact hash still match the stage. Permit only
`modular_aphelion/modules/lore_overhaul/code/generated_lore_overrides.dm`, enforce resolved parent
containment, and use atomic replacement or complete rollback. There is no dirty-checkout force path.
Never hand-edit generated DM.

## Verification

Run focused tests while iterating, then the applicable repository-wide gates from
[the verification guide](references/development/verification.md). A focused test is not a completion
claim. Exercise the real `Launch Aphelion Content Tools.cmd` entry point for launcher or integrated UI
work. When generated DM changes, complete the downstream Meridian-Rift gates separately.

Report commands, scope, results, observed artifacts, gates not run, and unrelated existing failures.
Run `git diff --check` and inventory the final working tree before handoff. Leave changes uncommitted.

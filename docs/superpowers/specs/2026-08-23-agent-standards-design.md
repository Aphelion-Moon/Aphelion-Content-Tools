# Aphelion Content Tools Agent Standards Design

## Status

This specification applies the maintainer-approved cross-repository decisions to Aphelion Content Tools. `references/maintainer-guide.md` is the normative architectural intent for this application. Git-history-derived preferences provide supporting rationale but do not silently override newer checked-in decisions.

Related repository specifications:

- Meridian-Rift shared governance record: `docs/superpowers/specs/2026-08-23-agent-standards-and-tooling-governance-design.md` in the Meridian-Rift repository.
- Meridian-MCP: `docs/superpowers/specs/2026-08-23-meridian-mcp-trust-and-modernization-design.md` in the Meridian-MCP repository.

## Objective

Replace the current cross-repository instruction mismatch with local, versioned standards for safely developing the Aphelion Content Tools application while preserving its writer-friendly workflow, structured canonical data, staged export, and Meridian-Rift integration.

## Repository identity

Aphelion Content Tools is a local multi-tool support application for non-programmer content and lore maintainers. It is not a second game codebase and must not inherit Meridian-Rift's DM placement rules as its primary agent instructions.

Its active application architecture is:

- Python package and FastAPI backend.
- Pydantic-owned HTTP schemas with generated TypeScript contracts.
- Solid, Vite, and strict TypeScript frontend.
- Shared application shell, tool registry, API client, state, and WebSocket ownership.
- Structured content as canonical source.
- Generated DreamMaker and future AutoWiki output as downstream artifacts.

Legacy pages are transitional compatibility surfaces. New behavior targets the SPA architecture and does not extend a legacy implementation unless a documented migration step requires it.

## Agent documentation hierarchy

A concise root `AGENTS.md` becomes the local entry point. It identifies the repository, active architecture, safety boundaries, required reading, and verification commands. Longer material remains in versioned references:

- Maintainer architecture guide.
- Writer guide.
- Backend and schema guide.
- Frontend and shared-state guide.
- Canonical content and generation contract.
- Export and repository-safety guide.
- Verification matrix.
- Meridian-Rift integration summary.

The current `.agents/AGENTS.md` content that governs Meridian-Rift is removed or replaced with an unambiguous pointer. Local instructions must not make an agent infer which repository they govern.

## Backend standards

FastAPI modules own HTTP transport and dependency wiring. Pydantic models are the canonical HTTP schema and generate the TypeScript declaration consumed by the frontend. Hand-maintained duplicate request or response types are not allowed.

Domain logic remains framework-agnostic where practical. Routes call focused services rather than embedding content reconciliation, graph, export, git, or storage logic in request handlers.

Errors use a stable taxonomy and machine-readable payload. Expected domain errors are not converted into unstructured exception strings. Filesystem, repository, revision, manifest, conflict, and validation failures remain distinguishable to the UI.

The Python project remains installable. Formatting, linting, type checking, tests, schema generation, and generated-schema validation are first-class gates.

## Frontend standards

The SPA has one implementation per shared concern:

- One application shell and navigation model.
- One tool registry.
- One typed API client boundary.
- One shared live-connection owner.
- One canonical application-store path for shared state.
- Scoped component styling unless a rule is genuinely global.

Tool pages may own local interaction state but do not create parallel APIs, WebSockets, repository state, or competing global stores. Shared behaviors become focused library or component units with stable typed interfaces.

Writer-facing interactions use domain language and actionable recovery guidance. Raw JSON, DreamMaker, git internals, hashes, and stack traces are hidden by default and exposed only in appropriate diagnostic views.

Accessibility and keyboard operation are verification requirements for shared shell, search, forms, review actions, conflicts, and export flows.

## Canonical data and generation

Structured content under the documented content root is canonical. Generated DreamMaker is a reproducible artifact, not an editing surface. Generation must be deterministic for unchanged input.

The data contract defines:

- Stable record identifiers.
- Schema and manifest versions.
- References and taxonomy ownership.
- Validation severity and blocking rules.
- Conflict and reconciliation behavior.
- Generated-file inventory and hashes.
- Migration behavior for schema changes.
- AutoWiki-facing fields and compatibility expectations.

Changing a schema requires backend validation, regenerated TypeScript contracts, migration or compatibility handling, generation tests, and documentation updates in the same reviewable change.

## Repository and export safety

The application binds to loopback and does not place credentials in browser code. GitHub Desktop owns authentication, pushes, pull requests, and complex merges. The application may inspect repository state and prepare a handoff, but it does not become a credential manager.

Staged export verifies:

- The selected target is a compatible Meridian-Rift checkout with the expected DME.
- The target revision and cleanliness meet the selected operation's requirements.
- The manifest and schema versions are accepted.
- Source and generated hashes match the staged payload.
- Every destination is on the allowed generated-file list and remains inside the target root.
- The final apply is atomic or rolls back without a mixed state.

Tests use a temporary or dedicated test checkout. They do not export into a maintainer's dirty production checkout.

## Content Graph and source inspection

Content Graph scans both `modular_nova` and `modular_aphelion`, preserving ownership information. It recognizes inherited NOVA markers and current APHELION markers. Unresolved or legacy markers produce useful diagnostics without making the entire graph unusable.

Marker parsing follows the canonical future-facing Meridian policy while retaining tolerant read support for known historical forms. Editing or generation never silently normalizes unrelated legacy markers.

Repository-scale operations expose progress, cancellation where practical, bounded diagnostics, and explicit completion evidence. An empty result is distinct from an operation that is still loading or failed.

## Verification matrix

The local agent guide defines exact current commands for:

- Python formatting and linting.
- Python type checking.
- Backend and domain tests.
- API schema generation and clean-diff validation.
- Frontend formatting, linting, type checking, unit tests, and production build.
- Accessibility tests for shared interactions.
- Content validation and deterministic generation.
- Staged export against a compatible test checkout.
- Windows launcher execution through the real `.cmd` or PowerShell entry point.
- Meridian-Rift DreamMaker/full-build and AutoWiki-related downstream gates when generated output changes.
- `git diff --check` and a final working-tree inventory.

The matrix labels focused, repository-wide, integration, and downstream gates separately. A passing unit test does not imply a successful launcher or export workflow.

## Meridian-MCP boundary

Meridian-MCP may inspect Meridian-Rift DreamMaker source, resolve definitions, search context, diagnose SpacemanDMM findings, and provide bounded map/runtime support. It does not own Content Tools schemas, application tests, export policy, or the authoritative Meridian full build.

PowerShell owns Windows build/test orchestration. The Content Tools application owns its Python and frontend workflows. The game repository owns the final acceptance gates for generated artifacts.

## Planned repository documentation

The implementation creates or revises:

- Root `AGENTS.md`.
- `.agents/AGENTS.md` as a compatibility pointer to the root instructions, containing no independent policy.
- `references/maintainer-guide.md` status, architecture, and legacy-transition language.
- Backend/schema conventions.
- Frontend/shared-state conventions.
- Data and generation contract.
- Export safety contract.
- Verification matrix.
- Meridian-Rift integration summary.
- Writer guide links where workflow behavior changes.

Documentation describes the intended SPA and clearly identifies transitional legacy paths. It does not pretend migration work is complete when both implementations remain present.

## Change discipline

Implementation is separated into reviewable repository-local changes. Existing unrelated dirty working-tree changes are preserved. Documentation work must inspect overlaps before editing currently modified files, especially the maintainer and writer guides.

Changes remain uncommitted unless the maintainer explicitly authorizes commits. Generated output and frontend build artifacts are reviewed separately from authored source.

## Acceptance criteria

- An agent starting in this repository receives Content Tools rules rather than Meridian-Rift DM placement rules.
- The SPA is the declared target and legacy surfaces are explicitly transitional.
- Backend schemas, generated TypeScript contracts, and frontend consumption have one documented ownership chain.
- Structured content is unambiguously canonical and generated DM is reproducible downstream output.
- Export cannot target an incompatible, dirty, or out-of-root destination without a documented explicitly permitted workflow.
- GitHub Desktop and the application have non-overlapping authentication responsibilities.
- Verification covers backend, frontend, schema drift, generation, export, launcher, and downstream game acceptance.
- Content Graph tolerates historical markers while writing only the canonical future form.

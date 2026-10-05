# Development guides

Start with the normative [maintainer guide](../maintainer-guide.md), then read the guide for the area
being changed:

- [Backend and schema](backend-and-schema.md) — FastAPI, Pydantic, services, errors, packaging, and
  generated API contracts.
- [Frontend and state](frontend-and-state.md) — Solid SPA boundaries, shared concerns, accessibility,
  and the legacy transition.
- [Data and generation](data-and-generation.md) — canonical records, versions, projections,
  deterministic DreamMaker output, and AutoWiki fields.
- [Content Graph](content-graph.md) — modular scanning, ownership, marker compatibility, and operation
  states.
- [Export safety](export-safety.md) — prepare/apply invariants, containment, atomicity, and GitHub
  Desktop handoff.
- [Verification](verification.md) — focused, repository-wide, integration, launcher, and downstream
  gates.
- [Meridian integration](meridian-integration.md) — ownership boundaries between this application,
  Meridian-Rift, Meridian-MCP, and AutoWiki.
- [Platform life cycle and integrations](platform-lifecycle-and-integrations.md) — workspace snapshots,
  derived-dataset provenance, search/context contracts, tool capabilities, staged game changes, and
  local/remote authorization.

The [writer guide](../writer-guide.md) remains the authority for user-facing Lore Editor workflow.

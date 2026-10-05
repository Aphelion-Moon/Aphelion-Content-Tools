# Content Graph

Content Graph scans `modular_nova` and `modular_aphelion` modules, mirrored `master_files` overrides,
and marked core edits while preserving repository and module ownership. The scanner and graph model
remain framework-agnostic; the FastAPI route imports and invokes them, and the Solid page consumes the
typed result.

Reading is intentionally tolerant. Recognize historical NOVA and APHELION marker spellings and known
START/BEGIN or single-line forms. Resolve an ownership edge only when attribution matches a real module;
otherwise retain a bounded unresolved-marker diagnostic. Do not fail the whole graph, invent ownership,
or normalize unrelated legacy source. New editing or generated output uses only the canonical future
APHELION form.

Repository-scale scans are explicit, cached, and bounded. Preserve file and module provenance, expose
progress and cancellation where supported, and cap diagnostic/output volume. UI and API state must
distinguish loading, an empty completed graph, failed, cancelled, stale-cache, and completed states.
Tests cover both modular roots, mirrored overrides, marker variants, unresolved attribution, cache
manifests, and the route-to-engine integration.

Graph scans write all tables and their manifest into an inactive projection, then publish one active
pointer. A failed scan leaves the previous generation readable. Cache reads pin their generation for
the entire operation, including the legacy table-based fallback.

Each new graph generation also publishes a compact `graph-health` manifest in the same transaction.
Health polling reads that row without decoding the delivery graph or initializing an embedding model.
An older cache remains readable, but its freshness is unavailable until a graph refresh publishes the
compact manifest and source provenance.

A scan captures module text, marker candidates (including ignored files), and mirrored core targets
once. Markers, references, and node metadata derive from those captured bytes. The source fingerprint
also includes module/readme and master-file topology, master-file sizes, and tracked path membership.
Immediately before activation, the scanner checks source topology, bytes, and game HEAD again. An
unreadable input or a changed source rejects the scan. Source directory aliases are rejected, and a
Git failure in an existing checkout does not trigger a full filesystem fallback.

Workspace polling compares a metadata observation and selected game HEAD; it does not hash all source
files or parse markers. This observation includes ignored graph inputs and also invalidates shared
context when an already-dirty checkout changes. It is a freshness hint, not a write authorization or a
substitute for the byte verification performed by explicit scans. Older graphs remain readable but
cannot be current until refreshed with this provenance.

Marker repair is a prepare/apply operation. `/api/graph/markers/edit` prepares a diff without changing
the game checkout; `/api/graph/markers/apply` accepts only the returned stage identifier. The shared
game change-set service revalidates the clean compatible checkout and complete file hashes before
applying. Labels cannot introduce new lines or comment delimiters. Existing line endings are preserved.

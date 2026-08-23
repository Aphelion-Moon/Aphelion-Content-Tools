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

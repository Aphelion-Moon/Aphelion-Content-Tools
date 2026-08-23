# Canonical data and generation

`tools/lore_editor/content/` is the canonical authored source for overrides, groups, reviews, and
assignments. Stable IDs identify records across branches and projections. Record files carry schema
and manifest versions, references and taxonomy ownership, validation results and severities, and
record hashes used for optimistic concurrency. Conflicts retain base, current, and proposed values;
reconciliation never silently chooses a winner.

Catalog snapshots, LanceDB tables, search indexes, caches, and projection generations are derived.
They must be rebuildable from canonical records plus their declared game/catalog inputs. A projection
activation is atomic, generation-tagged, and invalidates in-process views. Derived data does not enter
ordinary content pull requests unless it is an explicitly versioned release seed or manifest.

## Schema evolution

A schema change updates Pydantic validation, schema and manifest versions, generated TypeScript,
migrations or documented compatibility behavior, fixtures, generation tests, and these guides in one
reviewable change. Migrations are deterministic and idempotent. Unknown versions fail with a specific
diagnostic instead of being guessed.

References and taxonomy values are validated against their owning catalogs. Warnings remain distinct
from blocking errors. Content hashes use canonical serialization so equivalent records do not churn
across platforms.

## Generated outputs

Generated DreamMaker is deterministic for unchanged canonical inputs. Manifests identify source
revisions, projection/catalog provenance, schema versions, included stable IDs, and artifact hashes.
Generation writes a temporary artifact, validates it, and replaces only the declared output. Never
hand-edit generated DM; fix source records and regenerate.

AutoWiki-facing fields are part of the content schema and compatibility contract, but publication is
CI-only. Missing or disabled wiki fields must have explicit deterministic behavior. Browser code and
local writer sessions never receive AutoWiki credentials.

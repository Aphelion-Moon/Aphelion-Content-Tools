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

Catalog freshness distinguishes a verified release seed from local probe output. Seed bootstrap
retains the release manifest's source revision after validating its hash and canonical bytes. Local
refresh observes game source before the probe and rechecks it before reconciliation and activation;
detected source drift rejects publication. The observed HEAD is never taken only after compilation.

Explicit `catalog-reload` can replace an existing catalog using the validated release seed. When a
game checkout is selected, its HEAD must match the release and its source observation must remain
unchanged through activation. Missing or invalid releases preserve the active catalog and authored
records; this command does not fall back to the native probe. Startup bootstrap still keeps a nonempty
catalog. Seed downloads have a socket timeout and enforce the declared byte size while streaming.

A fresh probe JSON file does not prove the compiler input set of a reused BYOND binary. Local probe
catalogs therefore retain `source_provenance: unverified` and remain available for authoring, while
workspace health does not call them current. Older catalog manifests default to unverified. A native
compiler-source receipt is still an open integration requirement; neither clean Git status nor the
Content Graph's narrower input fingerprint supplies that evidence. Release-seed freshness additionally
requires matching game HEAD and a clean selected checkout.

Release packaging and export preparation verify the catalog manifest's source provenance, revision,
canonical target hash, and target count under the tool repository lock. Packaging cannot relabel a
catalog with a different game revision or promote an unverified local probe to a release seed. Export
preparation rejects missing, unverified, stale, or altered catalogs before creating a stage. This
currently limits those actions to verified release catalogs until local compiler receipts are added.

## Projection lifecycle

Use `read_projection` or `with_projection_read` around composite reads. Nested loaders use the same
generation, and connection-owned leases keep a returned native table or query alive after its caller's
scope ends. Bare paths are not reader leases. Retired or aliased generation paths must not be reopened
as empty databases. Acquire a new read scope when a fresh active generation is needed.

Activation and reader registration share a short lifecycle lock distinct from the repository writer
lock. Retirement holds the writer lease, preserves active and previous pointers plus live readers, and
renames eligible completed generations into `projections/.retired` under the lifecycle lock. Physical
deletion follows outside that lock, with at most four attempts per write and a persistent retry cursor.
Reader locks are stored in an application-specific temporary directory; abandoned lease files are
recognized by an available OS lock, not by a PID or elapsed-time guess. Restart both application
processes when updating this lifecycle code; older processes do not register these leases.

Projection schema 2 records a flat `table_owners` map. A stage declares its `changed_tables`, copies
only those tables, and reuses the direct physical owners of the rest. The first write after migration
copies all existing tables and upgrades their columns in the new stage. Published reads never create
tables or upgrade schemas; an absent table produces empty results. Use `schema.writable_table` only
inside a stage. Its write methods and pending merge builders reject use after the stage closes.
Published readers expose only schema, search and row-count operations; native version checkout alone
does not prevent every LanceDB mutation.

Reference changes use the same staged publication boundary. Partial writes and compaction preserve
the recorded embedding model; only a successful complete embedding rebuild assigns the current model
and updates row embedding hashes. A model mismatch remains visibly stale until that rebuild.

Active and previous pointers, and each logical reader lease, protect their direct table owners.
Native connections pin only the physical generation they opened. This avoids retaining an owner's
unrelated historical dependencies. A shared owner directory stays intact while any of its tables is
needed, including unused tables in an old full snapshot. Retention does not bound simultaneous readers
or incomplete recovery directories. Backups materialize every logical table into one independent
directory; restores remap those tables into a new stale generation. Interrupted copies remove only
their newly allocated destination when cleanup is possible. Restart both application processes after
updating; older versions do not understand shared table ownership.

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

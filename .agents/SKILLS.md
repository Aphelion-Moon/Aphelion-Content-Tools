# Meridian Rift skills reference

> **Scope: this file governs the Meridian-Rift game checkout, not this repository.**
>
> You are reading this inside `aphelion-content-tools`, the tool suite that targets Meridian-Rift. The
> loops and failure tables below are for working on the **game checkout** (DM, Rust/Dogmos, BYOND
> gates), which normally sits beside this repository as a sibling directory. For this repository's own
> code, see [`references/maintainer-guide.md`](../references/maintainer-guide.md).
>
> One caveat worth naming, since it is easy to misread: the "Standalone lore-tools loop" below describes
> using *this* tool suite from a game-developer's perspective — how to drive it, not how to modify it.
> It also predates the current architecture in places (it refers to `Launch Lore Tools.cmd` and an
> `aphelion-lore-tools` repository name, and cites a 500-row response cap that is a historical rendering
> limitation rather than a rule to preserve). Treat it as game-side workflow context, not as a
> specification for this repository.

This is a project-specific routing guide for recurring Dogmos work. It is not production code and
belongs in the extraction bundle. Use the repository guides and AGENTS.md as the authority when a
rule here conflicts with them.

## Marker choice

New Aphelion-owned work uses APHELION EDIT markers, including marked edits in inherited core files.
NOVA EDIT markers are retained only for inherited Nova-owned regions or when the current upstream
tooling requires their existing metadata. Do not introduce a new NOVA EDIT marker for Aphelion work.
The TGUI header THIS IS A NOVA SECTOR UI FILE is pipeline metadata, not an indication of ownership.

## Choose the skill by the failure you are solving

| Situation | Use | First evidence | Completion evidence |
|---|---|---|---|
| DM behavior or integration change | DM change loop | Existing procs, overrides, defines, and a focused in-game test | Compile, focused test, boot, full suite |
| Rust gas, graph, or formula change | Rust/Dogmos loop | Rust module tests, units, invariants, and FFI boundary | Targeted Rust tests, generated-bind drift check, vendored DLL, boot |
| Compiler or server hangs | Process-liveness diagnosis | Child PID, CPU/output, fresh artifact, captured stderr, logs | Explicit infrastructure or code result; no stale-artifact claim |
| Live atmospheric behavior is wrong | Reproduction and invariant check | Small test setup, relevant telemetry, runtime log, source path | Reproduction test, fix, focused gate, live or boot evidence |
| Merge or upstream conflict | Conflict-safe integration | Both sides, current include/type APIs, marker/whitespace diff | No unmerged paths/markers, compile, targeted tests, clean diff |
| Performance or mathematical concern | Cost-and-invariant review | Units, conservation/bounds, allocations, lock/queue behavior | Focused invariant tests plus measured or bounded cost explanation |
| UI, overlay, or goggles change | Player/admin surface review | Existing TGUI and visual lifecycle patterns | Compile, UI data path, equip/drop/toggle/delete cleanup, live check |
| Lore catalog or override work | Standalone lore-tools loop | Separate tool/game checkouts, catalog manifest, source records, export stage | Tool tests, generated-content validation, clean export apply, game compile/AutoWiki gate |
| PR cleanup or extraction | Release hygiene | Git diff, tracked/untracked files, in-game docs, extraction manifest | Production-only repo, concise docs, tests and status recorded |

## DM change loop

1. Read STYLE.md, AUTODOC.md, STANDARDS.md, modular_nova/readme.md, and any relevant
   HARDDELETES.md or VISUALS.md section.
2. Search for existing implementations and all overrides before designing a new proc or component.
3. Write one focused unit test for the observable contract and run it to establish the baseline.
4. Make the smallest modular or marked-core change.
5. Run the focused test, then test_compile_check.ps1, boot_probe.ps1, and the full run_tests.ps1 gate.

Focused tests accelerate iteration. They do not establish that unrelated tests, initialization, or the
full process lifecycle remain healthy.

## Rust/Dogmos loop

Use the dogmos branch of aphelion-dogmos and target i686-pc-windows-msvc. The build helper must:

- Build the release DLL.
- Run cargo test --target i686-pc-windows-msvc generate_binds.
- Compare generated bindings with code/__DEFINES/dogmos_bindings.dm.
- Reject drift unless the Rust bind attribute/doc comment was intentionally changed and the new
  generated file is accepted once.
- Reject a DLL older than changed Rust/Cargo inputs.
- Vendor the DLL and verify its hash.
- Run the post-build boot smoke test.

Never hand-edit generated bindings. If a bind collides with a DM-facing name, use the established
Rust __ bind plus DM wrapper pattern.

For gas or heat math, record the units and invariant in the test or nearby technical documentation:

- Gas transfer conserves each gas subject to the documented quantization boundary.
- Pressure follows the ideal-gas relationship with the mixture's temperature and volume.
- Heat moves from hot to cold and does not overshoot equilibrium.
- Infinite or empty heat-capacity cases do not produce NaN.
- Per-second work scales with seconds_per_tick.
- Parallel locks use a stable ordering and callbacks cannot act on deleted targets.

## Verification and process-liveness

Run BYOND gates from host Windows PowerShell. The restricted CodexSandboxOffline context is known
to leave DreamMaker/DreamDaemon silent or artifact-less; do not turn that into a long idle wait or a
green result.

The authoritative checks are:

1. Process exits successfully.
2. Compiler diagnostics contain zero errors.
3. The expected DMB is fresh for the invocation.
4. DreamDaemon reaches the initialization marker.
5. Logs contain no new runtime signatures.
6. Unit-test results and baseline comparisons are present and current.

Use Meridian-MCP for source-backed inspection and live diagnostics, not as a hidden build dependency.
Drain child output, keep cleanup scoped to processes started by the current run, and inspect logs when
the wrapper exit code disagrees with the generated results.

Baseline files are evidence, not a trash bin. Read the exact changed message/signature before using an
update switch. A fluctuating known hard-delete count is a baseline/tooling issue until a source
reproduction proves otherwise.

## Performance review loop

For any proposed optimization, answer these questions before changing code:

1. What repeats, at what frequency, and on which population?
2. What is the unit and conservation/bound invariant?
3. Can metadata, type resolution, or allocation move out of the hot loop?
4. Can one pass, one queue, or one callback replace duplicated work?
5. Does the change add lock contention, callback retention, timer overhead, or override chaining?
6. What focused test or telemetry will distinguish faster work from skipped work?

Prefer stable IDs, bounded batches, reusable buffers, typecaches, early validity checks, and event
driven processing. Do not optimize by removing a gameplay callback, weakening cleanup, or hiding a
runtime behind a baseline update.

## UI and visual review loop

Dogmos Kennel and goggles have separate station-safe and admin feature sets. Keep their data paths and
overlay categories explicit. For every UI control, check:

- Default state and permission boundary.
- Tooltip and user-facing explanation.
- Cost of enabling instrumentation.
- Bounded history and deletion-safe target references.
- Overlay cleanup on equip, drop, toggle, wearer change, and deletion.
- Visual behavior across adjacent turfs, walls, firelocks, and other topology boundaries.

Profiling is not the same as reaction-event recording: profiling times every Rust reaction call and
stores calls above a cost threshold, while events store meaningful reaction amount changes. Keep
profiling opt-in and document its overhead.

## Merge and extraction loop

For a merge conflict:

1. Read both sides and identify which side owns the data model now.
2. Preserve the Dogmos FFI/gas-mixture contract when upstream still references removed DM storage.
3. Adopt current upstream APIs where they are compatible, such as typepath-based techweb designs.
4. Re-add Dogmos content through the current API with an APHELION EDIT marker. Preserve NOVA EDIT
   markers only for inherited Nova-owned regions.
5. Search all conflict markers and check staged whitespace.
6. Compile before committing; run boot and relevant tests.

For extraction, keep production DM/Rust integration, in-game tests, and concise Dogmos operational
documentation in-repo. Move tooling, plans, reviews, changelogs, agent instructions, worker notes,
and verbose historical investigation to the external bundle. Do not delete the external bundle while
extracting it; preserve it for manual archival.

## Standalone lore-tools loop

Use this loop for lore catalog, writer-group, review, icon-reference, AutoWiki, or override work:

1. Open the standalone `aphelion-lore-tools` checkout with `Launch Lore Tools.cmd`; configure the
   separate Meridian-Rift checkout when prompted. Do not open the HTML with `file://`; relative API and
   asset requests require the loopback server.
2. Refresh the catalog against the game checkout and retain the catalog manifest/hash with the tool
   repository. The refresh may compile a large probe and can take minutes; distinguish a real compiler
   error from a restricted-context BYOND stall by checking process output, `$LASTEXITCODE`, fresh
   artifacts, and the tool log.
3. Maintain groups, keywords, type-path scopes, reviews, assignments, and overrides as separate source
   records. A type path without keywords is still a valid group rule. Match direct type paths, parent paths,
   labels, names, and descriptions according to the configured rule; do not add broad universal scopes such
   as all headsets unless the configuration explicitly asks for them.
4. Keep directional subtypes and redundant inherited descriptions hidden by default. Expose them only via
   their visibility toggles so a writer can opt into the noisy tail when needed. Search and group filters
   must preserve the 500-row response cap and distinguish initial loading from a genuine zero-result query.
5. Treat icon metadata as catalog data, not duplicated per-target configuration. Resolve DMI files inside
   the selected game checkout, validate the actual state name, and return a clear missing/invalid result for
   paths outside the checkout or state values that are type paths instead of icon states. Do not silently
   reuse one preview URL for unrelated entries.
6. Use the app's review state for “looked at and approved” and its override state for changed content; they
   are independent. Record attention decisions separately from overrides.
7. Prepare an export stage outside the game checkout, review its source revision, catalog hash, game
   revision, and artifact hash, then apply only to a clean compatible checkout. Let the app create a local
   branch and scoped commit when useful; use GitHub Desktop for authentication, push, pull requests, and
   conflict resolution.
8. Regenerate and validate the runtime DM artifact, then run the normal game compile and AutoWiki gate.
   AutoWiki consumes the generated runtime module; it must not import the standalone editor or make server
   startup depend on catalog generation.

### Lore-tool failure patterns

| Symptom | Check first | Correct response |
|---|---|---|
| Page is stuck on `Loading catalog` or shows zero entries | Loopback server output, `/api/health`, catalog manifest, browser console | Confirm the server is running and the catalog exists; wait for the initial large fetch before diagnosing an empty query |
| Search appears to accept text but results update slowly | Review-index cache, request duration, client render count | Measure each stage, retain indexed/cached filtering, and keep the response page bounded; do not remove matching scopes to make it appear fast |
| Icon endpoint returns 400/404 | Resolved path under the selected game checkout and actual DMI state list | Reject unsafe/out-of-root paths and invalid states with a clear UI fallback; never substitute a shared icon URL |
| `/datum/species` or a path-only group finds nothing | Rule parser and type-path normalization | Preserve absolute type paths as paths even when no keywords are supplied; test both direct and inherited type matches |
| Server startup stalls after lore work | Build target/dependency graph and catalog probe inclusion | Keep catalog extraction separate from normal DM/server targets and run it only through the tool workflow |
| Export would overwrite a contributor's game changes | Git status, manifest revision, and base artifact hash | Refuse the apply and hand the checkout to GitHub Desktop for review/commit/merge |

## Handoff format

Report these independently:

- Changed files and architectural reason.
- Compile result.
- Focused test result.
- Boot/live result.
- Rust result and generated-bind status.
- Full-suite result, including known baseline failures and wrapper exit discrepancies.
- Remaining untested behavior or follow-up work.

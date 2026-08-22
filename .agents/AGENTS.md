# Meridian Rift agent instructions

> **Scope: this file governs the Meridian-Rift game checkout, not this repository.**
>
> You are reading this inside `aphelion-content-tools`, the tool suite that targets Meridian-Rift. Every
> rule below — DM placement, edit markers, Dogmos/Rust, BYOND compile and boot gates — applies to the
> **game checkout**, normally a sibling directory beside this one. None of it describes this repository's
> own Python backend or web frontend; for those, see
> [`references/maintainer-guide.md`](../references/maintainer-guide.md).

Meridian Rift is a BYOND/Dream Maker Space Station 13 codebase derived from Nova Sector and TG.
Dogmos is its Rust-backed atmospheric integration; the Rust source lives in the sibling
aphelion-dogmos repository and the game checkout contains the vendored native library and DM
integration.

This file governs work on production code. The extraction bundle contains tooling, reviews, plans,
and agent notes; those files are not part of the game PR unless the user explicitly requests them.

## Communication

Be direct. Lead with the result or blocker. Distinguish confirmed facts, inference, and untested
assumptions. Do not claim that a compile, test, live check, or tool call succeeded without current
evidence.

## Required reading

Read the relevant versioned guide before editing code in its area:

- .github/guides/STYLE.md — repository style.
- .github/guides/AUTODOC.md — DM documentation comments.
- .github/guides/STANDARDS.md — architecture, security, optimization, and DM quirks.
- modular_nova/readme.md — modular placement and edit-marker rules.
- .github/guides/HARDDELETES.md — before touching Destroy() or retained references.
- .github/guides/VISUALS.md — before touching planes, layers, filters, or overlays.
- code/modules/atmospherics/Atmospherics.md — before changing Dogmos or atmospheric flow.

Before editing Rust, read aphelion-dogmos/README.md and the relevant crate/module tests.
Before changing a verification script, read the script's postmortem and README in the extraction
bundle.

## Before editing

Research first. Use rg to find existing types, procs, defines, signals, tests, and nearby patterns.
Search for an existing setter, helper, component, or subsystem hook before adding one. Keep the
smallest surface that satisfies the request.

Use this order:

1. Define the observable behavior and its invariant.
2. Find the existing implementation and all modular overrides.
3. Decide placement using the tree below.
4. Add or update a focused test before changing production behavior.
5. Make the smallest modular or marked-core change.
6. Run focused, compile, boot, and full-suite gates as appropriate.

Do not copy a core proc into a modular override merely to change one line. Do not leave exploratory
code, commented-out alternatives, speculative hooks, or dead compatibility scaffolding.

## Placement decision

~~~text
Is this genuinely new, self-contained fork content?
  -> modular_aphelion/modules/<module_id>/{code,icons,sound}/

Is this an override of an existing core type or proc?
  Can it be expressed as a type var, proc override, or addition at the start/end?
    -> modular_aphelion/master_files/<exact core path>
  Does it require a middle-of-proc change?
    -> marked inline edit in the core file

Does it belong to inherited Nova content?
  -> modular_nova/, preserving NOVA EDIT grammar for Nova-owned changes

Does it belong to Aphelion content or a core change owned by this fork?
  -> modular_aphelion/, or an APHELION-marked core edit
~~~

New module directories are flat by file category and need a readme.md when non-trivial. Core files
must retain upstream structure and byte parity except for intentional edits. Do not edit TG maps
directly; use the automapper.

## Edit markers and merge safety

Use APHELION EDIT markers for new Aphelion-owned modular and core changes. NOVA EDIT markers remain
on inherited Nova-owned changes and should be preserved when those regions are not being transferred
to Aphelion ownership. The APHELION convention is:

~~~dm
// APHELION EDIT ADDITION START - MODULE_ID
...
// APHELION EDIT ADDITION END

/* // APHELION EDIT REMOVAL START - MODULE_ID
...
*/ // APHELION EDIT REMOVAL END

// APHELION EDIT CHANGE - ORIGINAL: <the complete original line>
~~~

Existing NOVA EDIT markers are valid inherited history and must be preserved unless the complete
owned region is intentionally migrated to Aphelion. Do not add new NOVA EDIT markers for Aphelion
work. CHANGE is one line only; represent a multi-line change as a removal plus an addition. Never
put edit markers in a modular file.

After touching code/, inspect the diff and confirm every changed byte is intentional and marked when
required. Check trailing whitespace, final newlines, conflict markers, and generated files.

## Reuse, OOP, and modular overrides

- Condense behavior into the existing override rather than stacking another override of the same
  proc. Override chaining adds runtime overhead and hides the actual behavior.
- Prefer existing setters and helpers over direct var assignment; they carry signals, clamping,
  list semantics, logging, and HUD updates.
- Replace type-check ladders with virtual procs or data on the type. Use flags, traits, or typecaches
  instead of hand-curated path lists when membership is a property of a type.
- Use a component for a coherent reusable behavior, not as a bag of unrelated vars.
- Keep template datums stateless; put mutable state on the instance, component, or owning object.

## Signals, references, deletion, and races

- Use a proc override when both sides are controlled; use a signal when the producer and consumer are
  decoupled.
- Every registered proc uses SIGNAL_HANDLER, PROC_REF, TYPE_PROC_REF, or GLOBAL_PROC_REF.
- Unregister every signal and component hook on every teardown path.
- Never call Destroy() directly; use qdel() and QDEL_LIST.
- Never qdel an image; remove references and let BYOND collect it.
- Destroy() clears references and has no side effects. Undo exactly what Initialize() registered.
- Guard weak references and queued callbacks. Null references when they stop resolving.
- Timers must be stoppable, stored, and safe when their owner has been deleted.
- QDELETED() already covers null. Do not write redundant null-plus-deleted guards.
- Before adding sleep() or spawn(), identify the exact race and the existing synchronous callback or
  lifecycle hook that can remove it. Signal handlers cannot sleep.

## Dogmos architecture

Dogmos has one Rust gas store. Do not create a second DM-owned turf gas store or bypass the public
gas-mixture API. Rust owns repeated numerical work; DM owns gameplay contracts and player-facing
effects.

Rust owns gas mixture storage and hot gas operations, FDM environmental flow, Katmos pressure
equalization, excited-group processing, and TurfHeat conduction through blocked atmospheric paths.

DM owns the public gas-mixture contract and compatibility callers, atmospheric machinery and
pipenets, reaction gameplay consequences, hotspots, fire groups, explosions, overlays, logging,
subsystem scheduling, and Kennel history/telemetry.

Dogmos-specific rules:

- SSdogmos initializes the gas registry before turfs construct mixtures.
- dogmos_bindings.dm is generated. Change the Rust bind attribute or doc comment, regenerate, and
  compare; never hand-edit the generated file.
- Raw colliding FFI binds use the established __ prefix and are wrapped by clean DM-facing procs.
- Use stable registered gas IDs. Never parse gas strings or reconstruct metadata in a hot path.
- Keep FFI handles internal. Validate callback targets before invoking DM.
- Acquire multiple mixture locks in stable arena-slot order.
- Keep immutable source behavior explicit: immutable mixtures may be read or copied but do not mutate.
- Keep the DM compatibility boundary's quantization and temperature/heat-capacity invariants intact.
- Atmospheric work must be frame-independent; scale per-second quantities by seconds_per_tick.
- Use bounded active-turf walks, callback queues, worker channels, and reusable buffers. Do not turn a
  bounded stage into a full round-wide scan.
- Keep Rust as the authority for turf-to-turf heat conduction. Do not add a competing DM neighbor
  walk without an invariant, a focused test, and measured cost.
- Reaction profiling is opt-in because it times every Rust reaction call. Keep history bounded and
  distinguish reaction events from reaction timing.

## Performance and mathematical review

For a hot path or formula, record units, conservation/bounds, and the cost driver before editing.
Check both the normal path and failure or empty inputs.

- Parse strings and resolve typepaths outside Life() and air hot loops.
- Use typecaches for repeated type membership.
- Put the cheapest validity checks before list scans, FFI, locks, and expensive math.
- Loop once; accumulate telemetry in the same pass when possible.
- Do not create timers for work that can happen in the current stage.
- Start processing when work exists and stop when it does not.
- Avoid round-long globals when a value is consumed once in the current cycle.
- Check overflow, NaN, infinite heat capacity, zero-volume mixtures, and empty gas sources.
- For diffusion or transfer changes, assert conservation and boundedness, not only that a counter rose.
- For heat changes, assert hot-to-cold flow, no overshoot, and finite edge-capacity behavior.
- For callbacks or workers, measure queue drops, retries, contention, and stale-target paths.

## Style and comments

- Tabs, never spaces or mid-line alignment.
- Absolute typepaths beginning with /; snake_case; /datum datums.
- Descriptive names; never M, C, or H for local variables.
- Use SECONDS, units in names, and defines instead of magic numbers.
- Use static, not global; :: for static values; length() over .len.
- Use early returns, trailing commas in multiline lists, explicit return values, and named arguments
  where the meaning is not obvious.
- Never use usr, :, string typepaths, or walk*(); use SSmove_manager.
- Use item_interaction() over attackby() where applicable.
- New TGUI files retain // THIS IS A NOVA SECTOR UI FILE when required by the current TGUI tooling;
  this file header identifies the inherited UI pipeline and is not an edit-marker choice.
- New class-level vars and defines use ///. Public procs/classes use AUTODOC /** */ format.
- Keep discretionary commentary near zero. Comments explain a non-obvious invariant, a reason for
  divergence including the original value, or a surprising lifecycle/algorithm choice.
- Do not narrate obvious code or keep commented-out code in modular files.

## Player-facing work

- Give player actions feedback through the established alert, sound, visible-message, logging, and
  preference pathways.
- Anything spammable needs a cooldown or bounded rate.
- Keep long descriptions out of compact UI controls; use tooltips or documentation panels.
- Tooltips should explain disabled controls. Non-interactive information should not look clickable.
- Keep station-safe diagnostics separate from administrative-only diagnostics.
- For overlays and filters, read VISUALS.md first and validate cleanup when an item is dropped,
  toggled, deleted, or its wearer changes.

## Verification

For a DM-only change, use the extracted PowerShell tooling from a host Windows PowerShell session:

~~~powershell
$GameRepo = 'C:/path/to/Meridian-Rift'
test_compile_check.ps1 -GameRepo $GameRepo
run_tests.ps1 -GameRepo $GameRepo -Focus /datum/unit_test/affected_test
boot_probe.ps1 -GameRepo $GameRepo
run_tests.ps1 -GameRepo $GameRepo
~~~

A focused run is iteration evidence, not a completion gate. The full suite is required before calling
a change complete. A successful compile requires a fresh DMB and zero parsed compiler errors. A
successful boot requires the initialization marker, clean shutdown, and no new boot runtime
signatures. Read data/unit_tests.json, data/logs/ci/runtime.log, and the baselines; do not rely on a
lone DreamDaemon exit code.

For a Rust change, run the extraction build script or equivalent from host PowerShell. The Dogmos fork
must be on the dogmos branch, use the dogmos crate, target i686-pc-windows-msvc, pass binding drift
checks, vendor a DLL newer than the changed source, and pass the post-build boot smoke test.

PowerShell owns deterministic DreamMaker/DreamDaemon builds and tests. Meridian-MCP is for source
navigation, type/proc inspection, map queries, compiler diagnostics, and live server diagnostics.
Call dm_parse_environment before MCP diagnostics. If the restricted execution context cannot launch
BYOND reliably, fail fast and report the infrastructure limitation; do not reinterpret a stale DMB or
silent child as a code result.

Baseline updates require reading the changed failure message or runtime signature first. Never update
a baseline solely to make a run go green. Known baseline noise must remain explicitly separate from new
failures.

## Scope and handoff

Unfinished content, debug assets, changelog work, reviews, plans, worker instructions, and tooling
belong in the extraction bundle unless they are required production documentation. Production code,
in-game unit tests, and concise user-facing Dogmos documentation remain in the game repository.

### Standalone lore tools

The lore editor is maintained in the separate `aphelion-lore-tools` repository. Its catalog snapshot,
groups, reviews, assignments, and per-record overrides are the source of truth for lore work. The game
repository must retain only the runtime `modular_aphelion/modules/lore_overhaul` module and its generated
override artifact. Do not recreate the old `config/aphelion/lore_overhaul` or `tools/lore_editor` tree in
the game checkout.

Use the Windows `Launch Lore Tools.cmd` entry point from the tool repository. It starts the loopback web
server and asks for a compatible game checkout when needed. The browser must not receive GitHub or AutoWiki
credentials. Local branch creation and scoped commits may be performed by the app; pushes, pull requests,
and complex merges belong in the signed-in GitHub Desktop client.

Prepare lore exports in the tool repository first. Review the export manifest and apply it only to a clean
game checkout whose revision and generated artifact still match the manifest. A dirty checkout, changed
revision, changed generated artifact, missing module, or conflict is a stop condition, not a reason to
overwrite files. Never hand-edit the generated DM artifact; fix the source records and regenerate it.

Catalog refresh is an external-tool operation against the selected game checkout, not a game-server build
dependency. Keep catalog probes opt-in and do not make server startup depend on the editor. On Windows, run
the catalog and DreamMaker gates from host PowerShell, check `$LASTEXITCODE`, and confirm fresh artifacts;
restricted execution can leave BYOND children silent or artifact-less without proving a source failure.

Leave changes uncommitted unless the user explicitly asks for a commit. Before handoff, report:

1. Files changed and why.
2. Compile, focused-test, boot, Rust, and full-suite results separately.
3. Known baseline failures and infrastructure limitations.
4. Any live behavior not tested.

## Pre-submit checklist

1. Correct location and no copied core proc for a one-line change.
2. Existing overrides consolidated; no unnecessary override chain.
3. Core diff has correct markers and byte parity, including whitespace.
4. Existing helpers, setters, and components reused where appropriate.
5. Signals, refs, timers, callbacks, and deletion paths are safe.
6. Units, invariants, bounds, and hot-path costs are stated and tested.
7. No magic numbers, string parsing in hot paths, dead code, or debug leftovers.
8. AUTODOC is present where required and discretionary comments are concise.
9. Compile, boot, relevant focused tests, and full-suite status are current and honestly reported.
10. Extraction-only tooling and agent history are not left in the production repository.

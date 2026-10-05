# Maintainer Guide

This guide is for maintainers responsible for the catalog, the Content Graph, the game-repository
build integration, and the release/bootstrap path. Writer-facing Lore Editor workflow is covered in
the [writer guide](writer-guide.md); architecture and implementation history are in
[architecture/](architecture/).

## Normative status

This working-tree version is the normative architecture for Aphelion Content Tools. Historical design
records explain prior decisions but do not override this guide.

Shipped architecture: FastAPI and the Solid SPA.

Legacy pages are transitional and must not receive new product behavior except for a
documented migration or rollback fix. Pydantic models are the canonical HTTP schema, and
tools/lore_editor/content/ is canonical authored source. Catalogs, projections, generated TypeScript,
the production SPA, generated DreamMaker, and AutoWiki material are derived outputs.

Focused implementation rules are indexed in the [development guides](development/README.md). They
divide backend/schema, frontend/state, canonical data/generation, Content Graph, export safety,
verification, Meridian integration, and platform life-cycle responsibilities without replacing the
operational detail in this guide. The 2026-08-27
[platform audit](architecture/2026-08-27-platform-lifecycle-audit.md) records the evidence and the
[repair plan](../docs/superpowers/plans/2026-08-27-platform-repair-and-expansion.md) sequences the
replacement work.

## Repository structure

`aphelion-content-tools` is a multi-tool suite, not a single app:

- `webapp/api/` — typed FastAPI routes and the application factory; `webapp/serve_api.py` is the shipped
  server entry point.
- `webapp/frontend/` — the Solid SPA source and tracked production `dist/` artifact. Home, File
  Management, Lore Editor, Content Graph, Parsec, shared search, and shared references are routes or
  components in this one application.
- `webapp/store/`, `webapp/tooling.py`, and `webapp/store_worker.py` — the worktree-scoped LanceDB
  projection and persistent background-job process.
- `tools/lore_editor/` — canonical Lore records plus framework-independent catalog, validation,
  generation, and export domain logic.
- `tools/content_graph/` — framework-independent scanner, marker parser/editor, query, and graph logic.
- `webapp/web/` and `tools/*/web/` — rollback-only legacy assets; the shipped launcher does not serve
  them.

Each tool registers its own `ToolDefinition`s (see `tool_definitions.py` in each tool folder); the
shell combines them into one background-job registry so File Management's "Database and Git" panel and
`/api/tools` list every tool's actions together, without either tool importing the other's code.

## Architecture

The app is a Solid single-page frontend over a FastAPI backend. The launcher cut over to this stack on
2026-08-23. Legacy pages remain only for the explicit rollback window and must not receive product work.

### Frontend (`webapp/frontend/`)

Vite + Solid + TypeScript, strict `tsconfig`. Build with `npm run build`; develop with `npm run dev`,
which serves the UI on `:5173` and proxies `/api` and `/ws` to the Python server.

Four rules carry most of the design, and each exists because its absence caused a specific bug:

- **One implementation per concern, in `src/lib/`.** `api.ts` owns the only `requestJson`; `format.ts`
  owns `formatBytes` / `formatElapsed` / `escapeHtml`; `notify.ts` owns the announce surface. Before the
  rewrite `requestJson` existed in seven copies and `formatBytes` in three. Import them; never redeclare.
- **One layout, in `src/components/AppShell.tsx`.** The sidebar chrome was previously duplicated verbatim
  across five HTML files, so every nav change meant editing all five.
- **One frontend registry, in `src/tools/registry.ts`.** A tool's route, label, accent, page component,
  and frontend search entry come from a single manifest object. Backend routes, datasets, jobs,
  mutations, integrations, and availability are separate today; the required target is a backend
  capability catalog with a generated contract and a test that validates the frontend lazy-component
  registry against it. Do not claim that adding a complete tool is a one-file change.
- **Styles scoped by default.** `src/app.css` holds design tokens and app-wide element defaults; every
  other rule lives in a component-scoped `*.module.css`. A bare element selector in a per-tool stylesheet
  is a bug: `graph.css`'s `button { width: auto }` used to leak to every other tool for the rest of the
  session once Content Graph had been visited, because the SPA appended that stylesheet permanently.

Cross-tool state lives in `src/store/appStore.ts` (Solid `createStore`) and is fed by one WebSocket
connection (`src/lib/live.ts`). This replaced `window.__aphelionParsecShared`, per-widget cache
variables, and several independent 5-second polling timers.

Tests are Vitest, colocated as `*.test.ts` next to what they cover. Run with `npm test`.

### Backend (`webapp/api/`)

FastAPI, created per repository-root pair by `create_app()` so tests can run several apps against
separate temporary directories. `webapp/serve_api.py` is the ASGI entry point.

- **Pydantic models in `models.py` are the single definition of every shape crossing HTTP.** They serve
  as request validation, response schema, OpenAPI documentation, and — via `npm run gen:api` — the
  TypeScript types the frontend compiles against. A renamed field breaks the build rather than arriving
  in the UI as `undefined`. Regenerate after changing a model.
- **`errors.py` is a real taxonomy.** `BadRequest`, `NotFound`, `Conflict`, `GameRepositoryUnavailable`,
  `StoreUnavailable` each carry a status and a stable `code` the frontend can branch on. The old server
  answered every failure with the same `400`, repeated 56 times, so a missing game checkout was
  indistinguishable from malformed input. Raise the specific class; don't add another blanket handler.
- **Domain logic is untouched and framework-agnostic.** Routers import `tools/lore_editor/api.py`,
  `tools/content_graph/*`, `webapp/git_adapter.py`, `webapp/tooling.py`, and `webapp/store/*` directly.
  Those modules must stay free of HTTP concerns — they signal invalid input with `ValueError`, which the
  app maps to a 400.
- **`/ws` pushes health and active-run changes** to every connected client. Job state lives in the
  separate `store_worker.py` process behind a request/response pipe that cannot push, so the server polls
  it centrally and fans out; adding a real push channel later changes only `live.py`.

### Background-job ownership and recovery

There is one lazily started worker per resolved content-tools workspace. Every start, status, stop,
active-list, and shutdown request carries that workspace path; the worker rejects a request whose path
does not match its own. Never restore a process-global "current" repository shortcut.

The worker remains out of process deliberately. The embedding model is roughly 130 MB and its observed
cold load took about two minutes, so an API-owned thread would both lose crash isolation and make a
worker restart capable of taking down the HTTP server. The persistent process amortizes that load while
serializing its repository jobs. Run metadata is atomically persisted under `tools/logs/runs/`; after a
crash, completed runs remain inspectable and formerly queued/running runs are recovered as failed with
an explicit rerun message. Worker startup stdout/stderr is retained in
`tools/logs/store-worker-startup.log` and included in startup exceptions.

Stop requests are checked by a per-line Python trace as well as on output writes, so a silent Python
loop is cancellable. A single blocking native-library call cannot be interrupted safely inside the warm
process; cancellation is applied immediately when that call returns to Python, before the next command
or successful completion is published.

Published LanceDB tables are read through a version-bound interface. Each process caches at most eight
connections; eviction releases cache ownership without
closing a connection still held by a table or query. Composite readers borrow one projection for their
whole operation. Lore Editor's computed-view caches use that borrowed generation's ID, and a live poll
uses the same generation for its workspace revision and health. Worker activation cannot mix table
generations within those reads or tag old results with the newly active generation.

Projection schema 2 copies only tables declared changed by a writer and reuses immutable physical
owners for the others. Reference writes and schema upgrades happen inside stages. Read operations
never create tables, and staged write handles cannot mutate published data after their scope closes.
Backups materialize shared tables so they remain independent of subsequent generation cleanup.

Projection retirement preserves active, previous, and live reader generations plus their table owners. OS-locked reader leases
work across the API and worker processes and are released on process exit. A successful staged write
or restore retires eligible completed generations in bounded batches; deletion runs after releasing the
short lifecycle lock. Busy deletions are retried fairly, and failed cleanup does not undo publication.
Incomplete or unrecognized directories remain available for investigation. See
[projection lifecycle](development/data-and-generation.md#projection-lifecycle) for migration, embedding
provenance and retention boundaries.

The current projection revision is not a complete workspace revision: it can call canonical lore
current while catalog or Content Graph data came from an older Meridian-Rift checkout. Until the
workspace-snapshot repair lands, inspect every dataset manifest's game revision before relying on
aggregate health. New derived datasets must follow
[platform life-cycle and integration guidance](development/platform-lifecycle-and-integrations.md):
build inactive, verify complete provenance, then activate atomically.

The package is installable (`pip install -e ".[dev]"`), which is what lets modules use plain absolute
imports. `pyproject.toml` configures `ruff` and an initial Pyright production boundary. Legacy DMI,
dictionary-shaped graph code, and tests remain outside that type boundary; do not describe the whole
repository as strict-typed until that debt is removed.

### Legacy pages (`webapp/web/`, `tools/*/web/`) — rollback only

The original no-build-step pages are not used by the shipped launcher. They remain temporarily as a
rollback surface and use plain scripts with a guarded
`if (typeof module !== 'undefined' && module.exports)` block exporting DOM-free functions for `node --test`.
**Do not add pages or features here**. Delete them, their tests, `webapp/server.py`, and `webapp/serve.py`
together only after the rollback window is explicitly closed.

## Parsec: the app's standard feedback-reporting surface

Parsec (`webapp/frontend/src/components/Parsec.tsx`) is the husky pixel-pet mascot in the shared sidebar
and the app's central feedback authority. User-facing operations report a typed `ParsecEvent` through
`src/lib/parsec/coordinator.ts`; the coordinator owns prioritization, delayed progress, deduplication,
the bounded queue, character voice, the compact radio-log projection, and serialized activity-journal
writes. Keep exact errors in `technicalDetail` and keep the useful inline status or error in the tool
itself. The radio log uses playful character-facing copy and never replaces exact diagnostics.
`src/lib/notify.ts` is a
compatibility boundary for callers that have not yet migrated, not the API for new operation code.

`src/lib/parsec/journalTypes.ts` is an explicit persistence allowlist. It records typed event metadata,
reviewed Parsec copy, animation reaction, route/context identifiers, allowed technical detail, and timing;
it never serializes arbitrary event objects or lore bodies. Secret-shaped assignments are redacted before
persistence. `indexedDbJournal.ts` opens the browser-local `aphelion-parsec` IndexedDB database and falls
back to a session-memory journal without recursively reporting its own failure through Parsec. The bounded
`appState.parsecLog` is only the live UI projection; `appState.announcements` remains a temporary
compatibility projection and is not durable storage.

Her settings/info route is `/parsec`. Idle chatter is browser-local and defaults to **Rare**; the other
values are Off, Occasional, and Frequent. The single app-owned scheduler pauses while the document is
hidden, an editable control is focused, work is active, a connection problem needs attention, or Parsec
is already speaking. Page components must not create their own idle timers.

The same route owns local activity-history filters, storage status, JSON/CSV export, explicit clear
confirmation, and retention choices of 7, 30, 90 (default), or 365 days, or manual clear. Companion-profile
export is deliberately separate and never fabricates activity history. CSV export prefixes formula-shaped
cells, and profile/history data stays in the current browser unless the user explicitly exports it. A
newer, unreadable journal schema is preserved until the user explicitly confirms the incompatible-database
reset on this page; never delete or downgrade it automatically.

The canonical sprite is `webapp/frontend/src/assets/parsec.png`, cropped/repacked from "Husky Sprites"
(CC0/public domain). Coordinates, provenance, requested animations and icons, candidate status, and the
human-assistance backlog live in [`parsec-asset-register.md`](parsec-asset-register.md). Update that
register whenever an asset is added, evaluated, rejected, integrated, or relicensed.

Parsec's production companion library is versioned through
`webapp/frontend/src/assets/parsec/manifest.v1.ts`. It currently resolves all 60 required clips and 293
authored frames across seven actor/effect atlases, 11 separately anchored SS13 objects, and eight exact-copy
SS13 audio cues. `references/architecture/parsec-animation-storyboards.md` is the behavioral contract;
`references/parsec-asset-register.md` records exact source paths, states, revisions, hashes, licensing,
adaptations, rejections, and the remaining human-art backlog. Generated coordinates and anchor maps sit
beside each atlas. Do not hand-edit generated atlases or their coordinate JSON: update the prepared frames
or source inventory and rerun the corresponding script in `tools/parsec_assets/`.

The visual runtime selects manifest frames and authored durations. Effects use a separate pointer-inert
overlay, so hearts, alerts, scent, radio pings, and landing dust can never intercept application controls.
Every clip has an explicit reduced-motion frame. Audio cues are scheduled from their storyboard frame,
respect authored cue volume and cooldown, and pass through Parsec's master, voice, effects, alerts, and
rare-idle controls. Audio defaults on but waits for a direct browser interaction before unlocking; rare
idle remains deliberately quiet. Replacing a sound requires updating its source record and hash rather
than silently transcoding or substituting it.

`src/lib/parsec/runtime.ts` owns companion state, clip follow-ups, audio scheduling, and persistence.
`companionScheduler.ts` is the only autonomous-behavior scheduler. It observes consent, focus, visibility,
feedback duty, the current bed/cage state, reduced-distraction mode, and the configured presence policy.
Intrusive behavior is an explicit opt-in presence mode, not a separate component or a license to activate
application controls. Scruff handling, toys, movable furniture, and the viewport roaming layer all dispatch
typed companion intents; keep new interactions in that reducer/runtime boundary instead of mutating UI
state directly.

## Architecture summary (Lore Editor)

The `tools/lore_editor/content/` tree is the source of truth for writer groups, reviews, assignments,
and per-record overrides. LanceDB is a worktree-local, ignored projection. The catalog is derived data,
distributed through a release seed or rebuilt locally; neither it nor projection generations belong in
normal pull requests. `Meridian-Rift` supplies BYOND/DMI assets for catalog
generation and icon previews, and receives only the generated runtime artifact
(`modular_aphelion/modules/lore_overhaul/code/generated_lore_overrides.dm`) through the staged export
workflow — it never receives editor code or raw per-record content. Authentication, pushes, pull
requests, and complex merge conflicts are handled in GitHub Desktop; this tool only does local status,
branch, and commit operations.

The Solid route preserves the shared `AppShell`, tool registry, selected context, global search,
references, typed API client, and live-state owner. Inside that shell, `LoreEditorPage` coordinates a
two-pane workspace: `ReviewFilters` and the virtualized `ReviewList` remain mounted in the left queue,
while `EntryEditor`, `ReviewActions`, or `GroupManager` occupy the independently scrolling right pane.
Reviewer identity is a browser-local workspace preference; saved review records remain canonical
per-record files and carry their explicit reviewer value. The rollback-only Lore HTML and JavaScript
remain comparison references, not an alternate implementation.

Global text-entry controls fill their owning field, but global buttons are content-sized. A component
that needs a full-row action must opt into that width in its own CSS module. This prevents one page's
button assumptions from recreating the oversized-control regression across every SPA route.

Routine asynchronous feedback uses Parsec plus `LoadingIndicator`. Route-level `Suspense` is reserved
for the initial lazy module load. A tool that mounts asynchronous content after it is already visible
must add a nearer boundary so the shell and existing workspace remain mounted; its fallback uses the
shared indicator and, for discrete user actions, announces the load through Parsec. Continuous search
and filter requests keep quiet inline status so typing does not flood the announcement log.

## Content Graph

`tools/content_graph/scanner.py` walks a game checkout's `modular_nova/modules/*` and
`modular_aphelion/modules/*` directories (module nodes), `modular_nova/master_files/**` and
`modular_aphelion/master_files/**` (override nodes, mapped to their mirrored core path), and the
`code/` tree for `NOVA EDIT`/`APHELION EDIT` marker comments (`tools/content_graph/markers.py`).

The marker parser is deliberately tolerant: real markers in Meridian-Rift use `START` and `BEGIN`
interchangeably, many are single-line with no block at all, and — per a real scan — **the large
majority carry only a free-text reason, not a module id**. A marker only becomes a graph edge
(module → core file) when its label resolves to a real module directory; everything else lands in the
`unresolved_markers` list instead of being silently dropped or mis-attributed. Don't expect the graph's
edge count to reflect the true edit count — check `manifest.marker_count` vs. the graph's edge count
for the gap, and use the Unresolved markers panel to see the rest.

Scanning is explicit and cached, not automatic: use the **Scan modular content** tool button (or
`python tools/content_graph/cli.py scan --repo-root . --game-repo <path>`), which validates the
checkout identity the same way the Lore Editor does (`webapp/game_repository.py`), then writes
`tools/content_graph/cache/index.json` and `manifest.json` (gitignored — regenerate rather than commit
them). A real scan of Meridian-Rift takes a few seconds. The graph page reads the cache; it never scans
on page load.

## Refreshing the catalog

To replace an existing stale or unverified catalog with a matching release, use **Load release catalog**
in File Management, or run:

```bash
python tools/lore_editor/cli.py catalog-reload --repo-root . --game-repo <path-to-Meridian-Rift>
```

The command uses `tools/lore_editor/catalog-seed.json` and the per-user seed cache by default;
`--manifest` and `--cache-root` can select alternate locations. It verifies the release bytes and the
selected game revision, rechecks the checkout before activation, and replaces only the derived
catalog. Failure keeps the existing catalog and authored records. It never falls back to a local
probe. A matching release manifest must already be available; this checkout does not publish one yet.
Startup's `catalog-bootstrap` intentionally keeps a nonempty catalog, so it cannot perform this repair.

For local authoring data when the game repository's target list changes, use **Advanced catalog
actions** or run:

```bash
python tools/lore_editor/cli.py catalog-refresh --repo-root . --game-repo <path-to-Meridian-Rift>
```

This runs the maintained BYOND probe and atomically activates a new LanceDB projection containing its
catalog and provenance manifest. The probe uses game build artifacts and writes its runtime JSON;
it does not authorize tracked game-content edits. A failed catalog projection build preserves the
previous catalog. Source observations are checked before the probe and before publication.

Local probe output remains available for authoring, but its game-source freshness is unverified until
the compiler supplies an input receipt. A matching HEAD and fresh JSON do not prove the source of a
reused compiled binary. Verified release seeds retain their release revision; see
[catalog provenance](development/data-and-generation.md).

To package the active catalog as a release asset plus its small tracked manifest:

```bash
python tools/lore_editor/cli.py catalog-seed-package --repo-root . --seed-output <release-dir>/catalog-targets.json --manifest-output tools/lore_editor/catalog-seed.json --source-game-commit <Meridian-Rift-SHA> --download-url <published-release-asset-URL>
```

Packaging requires verified source provenance and the active catalog's exact source revision and
target hash. It cannot relabel an old seed or promote an unverified local probe. Until compiler input
receipts are integrated, local refresh can supply authoring data but cannot supply a new verified
release catalog or authorize staged export.

Publish the seed bytes at the exact URL before merging the manifest. Bootstrap downloads to a temporary
file, verifies schema, byte size, SHA-256, canonical JSON, and every catalog target, then atomically moves
it into `%LOCALAPPDATA%\AphelionContentTools\catalog-seeds`. Downloads use a 30-second socket timeout
and stop if the response exceeds the manifest's byte size. `catalog-bootstrap` uses the cache first
and falls back to `catalog-refresh` when a game checkout is available.

Two safeguards apply whenever `--game-repo` is passed (to `catalog-refresh`, and always for
`prepare-export`/`apply-export`):

- **Checkout identity.** `validate_game_repository()` rejects the path if `tgstation.dme` is missing
  (a fast check that the directory is even a tgstation-family checkout), and — if the path is a Git
  repository with an `origin` remote configured — if that remote's URL doesn't contain
  "meridian-rift". A checkout with no Git remote configured is accepted on the content-marker check
  alone, since there's nothing further to verify.
- **Drift reporting.** `catalog-refresh` prints a summary comparing the catalog snapshot before and
  after the refresh: type paths **removed** from the game repository, type paths that **changed**
  (label, field profile, editable root, parent type, or base name/description), and which existing
  overrides now reference a removed-or-changed target ("stale" overrides worth reviewing). This
  reaches the File Management page's Database and Git run log automatically, since it's just CLI
  stdout.

## Group and review oversight

Groups (`tools/lore_editor/content/groups/` in standalone mode) drive keyword/type-path matching and
the review queue's filters. As a maintainer, periodically check the group definitions still match
intent — a keyword that's too broad silently pulls unrelated targets into a group's review queue.
Reviews and per-record overrides are otherwise writer-owned; maintainers don't need to touch them
directly.

## Git operation safety

`webapp/git_adapter.py` — shared by every tool — serializes every multi-step operation (`repository_status`, `create_branch`,
`stage_and_commit`) with a per-repository-path lock, so two concurrent requests against the same
checkout (e.g. two browser tabs) can't interleave their Git index changes — different repositories are
never blocked on each other. Output is also bounded: Git error messages are truncated past 8,000
characters, and a status response lists at most 2,000 changed files (`truncated_change_count` reports
how many were left off). `open_in_github_desktop` is deliberately not locked — it only launches a
detached GUI process and never touches the working tree or index.

Only explicitly selected files under the canonical content roots, catalog release-manifest roots, or
the exact generated game-artifact path can be committed through the app. The previous Git index bytes
are restored if staging or commit fails. Pushes, pull requests, merges, and authentication stay in
GitHub Desktop. A workspace lease permits one mutating backend per worktree while allowing multiple tabs.

## The staged export mechanism

`prepare-export` and `apply-export` (exposed in the UI as **Prepare export** / **Apply selected
export**, and directly via the CLI) are deliberately split:

```bash
python tools/lore_editor/cli.py prepare-export --repo-root . --game-repo <path> [--stage-root <path>]
python tools/lore_editor/cli.py apply-export --stage <stage-directory> --game-repo <path>
```

`prepare-export` first refuses uncommitted authored records. It validates the tool-repo corpus,
generates the DM artifact, and writes it plus a manifest (tool revision, tool branch, canonical content
revision, catalog hash, game revision, entry/type-path lists, generated
artifact hash, and the game artifact's hash *at prepare time*) into a new timestamped directory under
`tools/lore_editor/stages/`. It never touches the game checkout.

`apply-export` re-validates all of the following against the *current* game checkout before writing
anything, and refuses (leaving the game checkout untouched) if any fail:

- the game checkout is clean (no uncommitted changes, no Git conflicts),
- the game checkout's current revision still matches the manifest's `game_repo_revision`,
- the game checkout's current generated-artifact hash still matches the manifest's
  `base_artifact_sha256` (`None` if the artifact didn't exist yet),
- the module directory (`modular_aphelion/modules/lore_overhaul/code/`) exists.

There is intentionally no dirty-checkout force flag in the API, CLI, or UI.

If everything holds, it atomically replaces the generated artifact and returns its path. See
[test_export.py](../tools/lore_editor/tests/test_export.py) for the exact refusal behavior.

After a successful apply, the server automatically opens the game checkout in GitHub Desktop as a
best-effort convenience step (`open_in_github_desktop(game_repo_root)`). If that fails — GitHub
Desktop isn't installed, say — the apply itself is still reported as successful; the response carries
`opened_in_github_desktop: false` and a `github_desktop_error` message instead, and the writer opens
it manually.

## Game-repository build integration

Three files in `Meridian-Rift` are intentionally touched by this migration, and nothing else should
be:

- **`tools/build/build.ts`** — adds `modular_aphelion/**` to the DreamMaker watch globs so the build
  picks up changes under the module. It does not reference this tool's paths.
- **`tgstation.dme`** — includes exactly five files under
  `modular_aphelion/modules/lore_overhaul/code/`: `catalog_probe.dm`, `lore_entry.dm`, `autowiki.dm`,
  `autowiki_tests.dm`, `generated_lore_overrides.dm`.
- **`code/modules/autowiki/autowiki.dm`** — skips the abstract `/datum/autowiki/lore_overhaul` base
  type when generating wiki pages, so only its generated subtypes publish.

`.github/workflows/autowiki.yml` is deliberately **unmodified** — it stays schedule/`workflow_dispatch`
-only and gated on the `AUTOWIKI_USERNAME` secret being set, exactly as before this migration. AutoWiki
publication must never run from a writer's local editor session.

Verify the integration with (from a Meridian-Rift checkout; BYOND does not need to be on PATH — pass
its full path if `dm.exe`/`dreamdaemon.exe` aren't found automatically, e.g.
`C:\Program Files (x86)\BYOND\bin`):

```powershell
& "<path-to-BYOND>\bin\dm.exe" tgstation.dme     # plain compile check
tools\build\build.bat --ci autowiki               # full AutoWiki generation, same as CI
```

A clean plain compile prints `0 errors` for `tgstation.dmb` (warnings from unrelated existing code are
expected and not a regression signal by themselves — compare against a compile from before your
change).

`build.bat --ci autowiki` additionally boots the compiled server headlessly and closes it once
initialization finishes, producing `data/autowiki_edits.txt` and `data/autowiki_files/`. On a Windows
machine, `dreamdaemon.exe -close`'s own shutdown exit code (observed: 144) is not zero, and the Juke
build tooling — written for the Linux CI runner, where this apparently returns 0 — reports the target
as failed regardless of whether the run actually succeeded. To tell a real failure from this known
quirk, don't trust the reported exit code alone: check `data/logs/ci/runtime.log` for errors and
confirm `data/autowiki_edits.txt` was produced with the content you expect (it will only contain
lore-overhaul pages for overrides that have `wiki.enabled` set — an override with no `wiki` field
produces no AutoWiki output by design). Clean up `data/logs/ci`, `data/autowiki_edits.txt`,
`data/autowiki_files`, `tgstation.test.*`, and `tgstation.dmb` afterward — none of them are meant to
be committed (`tgstation.dmb` and `data/**/*` are already gitignored).

## Release and bootstrap path

[`Launch Aphelion Content Tools.cmd`](../Launch%20Aphelion%20Content%20Tools.cmd) calls
[`tools/launcher/launch.ps1`](../tools/launcher/launch.ps1), which:

1. Looks for a compatible Python (3.11+, with all pinned runtime imports) via `python.exe`, `py -3`, or a previously
   installed private runtime, in that order.
2. If none is found, asks before downloading the pinned installer named in
   [`tools/launcher/runtime_manifest.json`](../tools/launcher/runtime_manifest.json), verifies its
   Authenticode signature is a valid Python Software Foundation signature before running it, and
   installs it per-user into `%LOCALAPPDATA%\AphelionContentTools\runtime` (no PATH changes, no
   all-users install). Declining leaves manual-install instructions on screen and changes nothing.
3. Resolves the game-checkout path (from `%LOCALAPPDATA%\AphelionContentTools\settings.json`, a nearby
   `Meridian-Rift` folder, or a manual prompt) and persists it for next time.
4. Runs `catalog-bootstrap`; release-seed failure never blocks canonical content, and a configured game
   checkout supplies the local-rebuild fallback.
5. Starts `webapp/serve_api.py` on a loopback port and opens the built Solid SPA. The minified
   `webapp/frontend/dist/` artifact is tracked so writers do not need Node; CI rebuilds it and refuses
   source/artifact drift. The legacy server remains available only during the rollback window.

To change the pinned Python version, edit `runtime_manifest.json`'s `version`, `installer_url`, and
`signature_subject_contains` fields together — an installer whose signature doesn't match the expected
subject is rejected outright, so all three must stay consistent.

### Projection recovery

Canonical Git records remain authoritative. Use these commands from the content-tools checkout; none
write to Meridian-Rift:

```powershell
python -m webapp.store.cli status --repo-root .
python -m webapp.store.cli reconcile --repo-root .
python -m webapp.store.cli rebuild --repo-root .
python -m webapp.store.cli backup --repo-root . --output <backup-root> --label <label>
python -m webapp.store.cli restore --repo-root . --backup <backup-directory>
```

`reconcile` is the normal branch-switch recovery path and changes only rows whose canonical record hash
changed. `rebuild` creates a fresh projection generation. `backup` copies a labeled projection snapshot;
`restore` activates that snapshot as explicitly stale data, after which `reconcile` reapplies the current
branch's canonical records. Never resolve a record conflict by restoring LanceDB over Git.

These commands currently establish canonical-lore currentness, not aggregate Meridian-Rift dataset
currentness. Compare catalog and Content Graph manifest revisions to the selected game checkout. The
planned workspace-snapshot CLI will make those dataset checks part of `status`, `verify`, and activation.

### Windows packaging spike

Install the pinned build toolchain and produce the isolated `onedir` artifact with:

```powershell
python -m pip install -r packaging/requirements-build.txt
./packaging/build-sidecar.ps1 -OutputRoot <temporary-output-directory>
```

The build requires the quantized FastEmbed model in
`%LOCALAPPDATA%\AphelionContentTools\models` and fails if it is absent. This is a measured spike, not a
release pipeline. See [windows-sidecar-packaging-spike.md](architecture/windows-sidecar-packaging-spike.md)
for size, startup, memory, offline, DMI, and process-tree results. Tauri work is blocked until the clean
catalog bootstrap activates precomputed vectors instead of recomputing them on every writer's machine.

## Verification checklist before calling a change complete

### Job and outfit authoring

The Solid `/job-editor` and `/outfit-editor` tools share the framework-independent
`tools/definition_editor` domain and thin `/api/definitions` routes. Versioned records in
`tools/job_editor/content` and `tools/outfit_editor/content` are canonical. Saves require the previous
record hash and use the repository write coordinator. Shared workspace revisions include these roots;
search reads their canonical records directly and carries the source catalog identity into navigation.
Game application receipts reconcile the saved record to the refreshed catalog only when its saved hash
and all expected game inputs still match. A concurrent edit requires explicit source-refresh review.

The packaged Windows Meridian-MCP executable is selected by `tools/definition_editor/runtime/analyzer.json`
and verified by SHA256 before execution. Its deterministic source catalog includes byte ranges,
whole-file hashes, raw expressions, inheritance, procedures, reference editability, parser provenance,
and build configuration. `job-outfit-definitions` is an optional workspace dataset built inactive and
activated through the existing atomic snapshot pointer. Missing analysis or BYOND never blocks saving
drafts. Unknown expressions and ambiguous physical occurrences remain inspectable and cannot authorize
automatic in-place edits.

Existing modular definitions are patched at their physical owning ranges. TG overrides and new
identities go to the dedicated `content_tools/code/generated_outfits.dm` and `generated_jobs.dm`
outputs, included in Meridian-Rift's explicit final phase. Generated blocks belong to their canonical
record; later saves replace that exact block. Job access belongs to a linked ID trim. Replacement
requires an explicit old-job selection choice and migrates only selected verified reference tokens;
saved preferences, bans, configuration, and dynamic/map references are compatibility concerns, not
silently migrated records.

This workflow uses the shared `GameChangeSetService` create/modify transaction, separately from the
single-artifact lore exporter. Validation copies private source, reparses the draft, and compiles the
exact candidate with the maintained game build. Prepare/apply verifies the source/asset fingerprint,
compiler/analyzer hashes, saved draft hash, clean compatible checkout, revision, and exact allowed file
bytes. Server-held stages expire and cannot be supplied by browser content. The durable game-side
journal supports complete rollback and interrupted-application recovery, including newly created files;
its durable receipt is the commit point. Applying to the developer's dirty game checkout is refused.
Private snapshots include referenced resource files even when Git ignores them, with the same input
fingerprint used for validation and application. Git administration and runtime configuration stay
excluded. The service retains at most two compiled candidates; superseded/applied candidates, failed
or analysis-only copies, and owned copies at shutdown are removed. Raw analyzer payloads are transient;
run status, bounded logs, images, and validation/application receipts remain available.

Native previews run only on explicit requests and use the `CONTENT_TOOLS_PREVIEW` game harness. The
runner owns compilation, daemon, and direct DreamSeeker process trees, bounded logs, readiness,
cancellation, and shutdown. Sessions use private runtime/configuration and reject remote clients and
Topic requests before ordinary game startup. BYOND may listen on all interfaces; the application gate
is not an OS network sandbox. A private directory is not a security sandbox for edited DM. The engine
can also use its existing BYOND login. The humanoid test map exercises outfit/job equipping and hooks;
it does not emulate round scheduling, saved preferences, player loadouts, or special role body creation.

```powershell
./tools/testing/run-python-suites.ps1
python -m ruff check .
python -m pyright
npm --prefix webapp/frontend run gen:api
npm --prefix webapp/frontend run typecheck
npm --prefix webapp/frontend test -- --run
npm --prefix webapp/frontend run build
# Until the rollback window closes, retain its syntax and unit gate.
$legacyRoots = @('webapp/web', 'tools/lore_editor/web', 'tools/content_graph/web')
$legacyScripts = foreach ($root in $legacyRoots) { Get-ChildItem -Recurse -File $root -Filter '*.js' | Where-Object { $_.FullName -notlike '*\vendor\*' -and $_.FullName -notlike '*\tests\*' } }
$legacyScripts | ForEach-Object { node --check $_.FullName; if ($LASTEXITCODE -ne 0) { throw "Syntax check failed: $($_.FullName)" } }
$legacyTests = Get-ChildItem -Recurse -File webapp/web/tests,tools/lore_editor/web/tests,tools/content_graph/web/tests -Filter '*.test.js'
node --test @($legacyTests.FullName)
python tools/lore_editor/cli.py generate --repo-root .
python tools/lore_editor/cli.py validate --repo-root . --check-generated
git diff --check
```

Plus, when BYOND is available: a Meridian-Rift compile and the AutoWiki CI job (see above). Leave all
changes uncommitted unless a commit or push has been explicitly requested.

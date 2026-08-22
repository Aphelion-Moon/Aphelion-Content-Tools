# SPA Rewrite — Session Handoff

**Date:** 2026-08-22
**Branch:** `main` (all work committed; working tree clean)
**Approved plan:** `C:\Users\Zoe\.claude\plans\we-re-going-to-rescope-replicated-snail.md`

## Where things stand

The app is mid-migration from a hand-rolled SPA facsimile to a real one. **Both stacks currently exist
side by side.** The legacy stack still runs and is untouched; the new stack is complete for four of the
five tools but is not yet the thing users get.

| Step | State |
|---|---|
| 1. Docs and `.agents/` framing | Done |
| 2. Frontend scaffold (Vite + Solid + TS) | Done |
| 3. FastAPI backend, typed models, WebSocket | Done |
| 4. Port tools — Home, File Management, Parsec, Lore Editor | Done |
| 4. Port tools — **Content Graph** | **In progress: engine foundation only** |
| 5. Retire the legacy shell | Not started |
| 6. Tauri shell, delete launcher | Not started |

### Commits this session, oldest first

```
7481004  Scaffold real SPA foundation: Vite + Solid + TS, shared store, tool registry
ecbabda  Track .agents/*.md and organise .gitignore
66bcf50  Add FastAPI backend with typed models, error taxonomy, and live updates
6d8514d  Port File Management and Parsec to the new shell
a38543a  Port Lore Editor and remove the 500-row cap
25002cb  WIP: Content Graph engine foundation (not yet wired up)
```

## How to run it

Two processes. The legacy app is unaffected and still starts the old way.

```bash
python webapp/serve_api.py --repo-root . --port 8765 --game-repo C:/Users/Zoe/Documents/GitHub/Meridian-Rift
```

```bash
npm --prefix webapp/frontend run dev
```

Then open `http://localhost:5173`. Vite proxies `/api` and `/ws` to `:8765`.
`.claude/launch.json` has both as `backend-for-frontend` and `frontend`.

First-time setup on a fresh checkout:

```bash
python -m pip install -e ".[dev]"
```

```bash
npm --prefix webapp/frontend install
```

### Regenerating the API types

Whenever a Pydantic model in `webapp/api/models.py` changes:

```bash
npm --prefix webapp/frontend run gen:api
```

No server needed — it runs `webapp/dump_openapi.py` and feeds the schema to `openapi-typescript`.
Both `openapi.json` and `src/lib/api-schema.d.ts` are gitignored, so **a fresh checkout must run this
before `tsc` will pass.**

## What is finished and verified

Everything below was checked against the real repository and the real 21,000-row store, not mocked.

- **Cross-tool live updates.** A job started in File Management appeared on Home as
  "Rebuild search embeddings — running for 2s" over the WebSocket, with no reload. This was impossible
  in the old architecture and is the core thing the rewrite was for.
- **Global search now reaches the whole store.** It calls `/api/search` — hybrid BM25 plus vector
  similarity, merged with reciprocal rank fusion, across all ten tables. Previously the box called
  `/api/review`, a substring filter over one table, so this capability existed and was simply unwired.
  Confirmed returning results spanning `catalog_targets` and `graph_nodes` together, including matches
  with no keyword overlap (the vector half working).
- **The 500-row cap is gone.** The Lore Editor virtualises rendering and pages the fetch: the DOM holds
  ~35 rows at any scroll position while the loaded set grows. Confirmed reaching all 12,264 matching
  entries. Note the corpus is bigger than the old cap implied — 17,500 catalog targets, less 409
  directional and 5,210 redundant hidden by default.
- **The Python → OpenAPI → TypeScript contract is real.** Verified by renaming a field in
  `models.py`, regenerating, and confirming `tsc` failed at the exact consuming line rather than the
  value reaching the UI as `undefined`. Then reverted.
- **Duplication is structurally gone.** `requestJson` went from 7 copies to 1, `formatBytes` 3 → 1,
  the announce helpers 3 → 1, `escapeHtml` 2 → 1, and the 5× duplicated sidebar markup to one
  `AppShell`. Adding a tool is now one entry in `src/tools/registry.ts`.

Test counts at handoff: **40 frontend (Vitest), 136 webapp, 133 lore_editor, 43 content_graph.**
`tsc` and `ruff` clean.

## Picking up Content Graph

This is the only unfinished tool, and it is the largest: the legacy
`tools/content_graph/web/graph.js` is **2,112 lines**, with 46 inputs and 40 element IDs in its HTML.
You chose a **full clean rewrite** over extracting the existing engine.

### Done — `webapp/frontend/src/tools/contentGraph/engine/`

- `types.ts` — wire shapes converted once into simulation types; force and tuning settings
- `colors.ts` — node, edge, ego-tier palettes
- `layout.ts` — placement maths as pure functions: cluster keys/anchors, spacing scale, packed-grid
  packing with centre-out spiral fill, all four seed shapes
- `forces.ts` — the three custom d3 forces (cluster, centre-pull, focus rings) and BFS hop distances

These compile but nothing imports them. `/graph` still renders the placeholder, so the app builds and
runs normally.

### Remaining

1. `engine/simulation.ts` — d3 simulation lifecycle: build, settle, ambient alpha, drag reheat, jiggle.
   Legacy reference: `createSimulation`, `runSimulation`, `syncForcesToSimulation`,
   `syncSimulationTuningToSimulation`, `nudgeSimulation`, `jiggleSimulation`.
2. `engine/renderer.ts` — graphology graph plus Sigma WebGL renderer, position/visibility sync, hover
   and click picking, node dragging. Legacy reference: `buildGraphologyGraph`, `rebuildRenderer`,
   `syncPositionsToGraphology`, `syncVisibilityToGraphology`, `attachRendererEvents`, `fitView`.
3. Solid components — explorer tree with subtree scoping, filter panel (kind/owner/relation, degree
   dual-range, search), physics tuning panel, node detail, scan orchestration.
4. Vendored libraries: `graphology.umd.min.js`, `sigma.min.js`, and the four d3 files currently live in
   `tools/content_graph/web/vendor/`. Prefer proper npm dependencies now that there is a bundler —
   they were vendored only because there was no build step.

### Things worth knowing before touching it

- **The legacy comments encode hard-won decisions.** Several explain *why* the maths is shaped as it is
  — uniform whole-graph translation instead of per-node centre pull (a per-node pull compressed
  branching structure into a filled disc), sqrt cell-size scaling (linear scaling made a 25,000-node
  cluster's footprint grow with the square of the spacing scale), degree-sorted centre-out spiral fill.
  None of that is recoverable from the maths alone. Carry it forward.
- **You cannot verify this in the automated browser pane.** It fires **zero** `requestAnimationFrame`
  callbacks and reports `document.hidden: true`, so it does not composite — WebGL rendering and physics
  both need a real browser window. Keep the maths in pure, tested functions (as `layout.ts` and
  `forces.ts` already are) and eyeball the rendering manually.

## Known issues and sharp edges

- **Job cancellation only takes effect when a job next writes output.** `_RunOutputStream.write` raises
  `JobCancelled` ([webapp/store_worker.py:60](../../webapp/store_worker.py)), so a job that is silent
  for a long stretch ignores Stop until it prints. Hit this by starting a full embedding rebuild: it
  ignored Stop for about two minutes while loading the 130 MB model, then stopped cleanly the instant it
  printed its first progress line. **Pre-existing, not a regression.** Worth fixing — a cancellation
  check inside the embedding chunk loop would do it.
- **Elapsed times freeze between WebSocket pushes.** The broadcaster only sends on change, and
  `formatElapsed` is computed at render time, so "running for 2s" stays "2s" until the next state
  change. Cosmetic. Fix with a ticking signal in the components that display elapsed time.
- **19 stylistic ruff findings remain** (SIM105, SIM117) in legacy files scheduled for deletion.
  Deliberately left rather than churning files that are going away.
- **`E501` is disabled in ruff.** It measures tab-expanded width and flagged ~100 lines that are well
  under the limit as written; the real p95 line length is 94 characters.

## Decisions made this session

Recorded so they are not silently revisited.

- **No full Rust backend.** Genuinely reconsidered — LanceDB is Rust-native and `fastembed-rs` ships the
  same `bge-small-en-v1.5` model — and it would dissolve the whole packaging problem, since the backend
  would simply *be* the Tauri binary. Rejected because Python is not what hurts maintainability here;
  the absence of a data model was. Reconsider only if this were greenfield or the BYOND/DMI-specific
  code did not exist.
- **Tauri is the destination**, wrapping the finished SPA at step 6. Chosen mainly because it makes the
  orphaned-process class of bug impossible (Tauri owns the sidecar lifecycle) and deletes the 194-line
  PowerShell launcher, which is really a hand-written installer.
- **Windows only**, and **local commits only** — GitHub Desktop keeps owning auth, pushes, PRs, and
  merge conflicts. Both re-examined against the new native-app capabilities and deliberately kept.
- **Rejected:** Zod (both sides of the boundary are this repo, with generated types), Module Federation
  (one repo, one maintainer), a second state library (Solid signals cover it).
- **`.agents/*.md` are now tracked.** They were gitignored, so the framing distinguishing Meridian-Rift
  game-checkout conventions from this repository's own never left one machine.

## Before deleting anything legacy (step 5)

The plan's anti-regression gate, restated so it is not skipped:

- Exactly one definition each of `requestJson`, `formatBytes`, `formatElapsed`, `escapeHtml`, and the
  announce helpers.
- Exactly one component renders the sidebar chrome.
- No `.module.css` declares a bare element selector. This is not style pedantry: `graph.css`'s
  `button { width: auto }` overrode the global `button { width: 100% }` and, because the old SPA
  appended stylesheets permanently, visiting Content Graph once silently changed every other tool's
  buttons for the rest of the session.
- Adding a throwaway dummy tool touches exactly one file.
- Full Python and frontend suites green.

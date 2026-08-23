# Content Graph renderer decision

**Recorded:** 2026-08-23  
**Decision:** Sigma 3 WebGL over Graphology 0.26, with d3-force 3 for bounded small-scope layout

## Workload

The authoritative Meridian-Rift scan at commit `c34175cab324ce34c768e698a0c7c6c488691f89`
contains 30,331 nodes and 31,375 edges. The semantic default contains 3,572 modules,
master-file overrides, and marker-bearing core files. A sandbox fallback scan that could not use Git
contained 41,703 nodes and 42,747 edges, which remains useful as the tested worst case.

The graph projection tables are keyword-only. Their text is made of paths, IDs, and relation names, so
full-text search is more accurate than semantic similarity and avoids embedding about 60,000 structural
records on a fresh authoritative scan. Lore and authored-content tables retain hybrid semantic search;
selected module/type/group context still supplies the bounded related-result boost across tools.

## Candidates

| Renderer | Result |
|---|---|
| SVG | Rejected. Tens of thousands of interactive DOM nodes and edges would make layout, updates, and accessibility worse; the app already supplies a separate semantic table rather than treating renderer primitives as accessible DOM. |
| Canvas2D | Rejected for the main renderer. It can draw this volume, but the legacy implementation had to own picking, hover, drag, label culling, and redraw scheduling itself. Repeating that infrastructure would preserve the largest maintenance burden in the old page. |
| Sigma WebGL + Graphology | Selected. It provides GPU node/edge programs, picking, camera behavior, label-grid culling, and a tested graph model while leaving layout/filter policy in small pure modules. |

The renderer is lazy-loaded only on the graph route. The production Sigma chunk is 163.43 kB
(39.74 kB gzip). d3-force is not used above the configured large-graph threshold in automatic mode;
large scopes use the deterministic packed seed and remain static unless the user explicitly enables
physics.

## Visible browser evidence

The production SPA was served by FastAPI and exercised in the visible in-app WebView2 browser:

- Sigma created seven 558×608 canvas layers, including its WebGL node and edge layers, and visibly
  rendered the real graph. The console contained no warnings or errors.
- The authoritative full scope reported 30,331 visible nodes and selected the `packed static layout`
  policy. It became ready about 2.45 seconds after **Tick all** in the measured run.
- The sandbox worst-case scope reported 41,703 visible nodes and also selected the packed static policy;
  it became ready about 3.67 seconds after **Tick all**.
- A selected-node deep link became ready in about 3.8 seconds against the standalone production server
  and 4.8 seconds through the shipped Windows launcher.
- The graph response initially reconstructed every normalized row and emitted Pydantic null fields:
  24.49 MB and about 3.4 seconds locally. Publishing a self-contained final snapshot row, excluding
  nulls, and enabling gzip reduced it to 10.16 MB / 0.37 seconds uncompressed and 0.80 MB / 0.45
  seconds over gzip.
- Label density, minimum edge thickness, and full-scope screen-space mark size were reduced after visual
  inspection. The default scope retains readable labels; full-repository mode becomes a density overview
  intended to be narrowed with scope and visibility controls, not a claim that 30,000 labels fit at once.
- Exact `?selected=module:aphelion:storage_navigation` navigation restored Details and shared selected
  context. A live global search then displayed both the related-results note and per-result `Boosted:`
  reason.

The shipped `Launch Aphelion Content Tools.cmd` path announced a loopback URL, served this production
SPA and authoritative graph revision, loaded the 17,500-target Lore Editor with all eight restored
groups, and closed its listening port when the launcher was stopped.

## Operational policy

- Git-tracked canonical records remain authoritative; the graph and its snapshot are disposable
  worktree-local LanceDB projections.
- Filters change renderer visibility only. They do not mutate force membership or node positions.
- Automatic physics is live only for small scopes, settles and freezes medium scopes, and skips force
  work for very large scopes.
- The accessible paginated node table is the keyboard/screen-reader path. Canvas marks are not presented
  as semantic DOM.
- Legacy graph assets remain during the rollback window. They are not the shipped launcher path.

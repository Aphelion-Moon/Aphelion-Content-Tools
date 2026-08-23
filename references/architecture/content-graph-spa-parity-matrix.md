# Content Graph SPA parity matrix

**Recorded:** 2026-08-23  
**Legacy surfaces:** `tools/content_graph/web/graph.html`, `graph.js`, `modular-debug.html`, and `modular-debug.js`  
**Replacement:** `webapp/frontend/src/tools/contentGraph/` behind typed FastAPI routes

This matrix is the deletion gate for the legacy Content Graph and Modular Debug pages. “Component
verified” means an automated engine, component, API, or accessibility regression covers the behavior.
Visible WebGL and launcher checks are separate gates and are not implied by component verification.

| Maintainer workflow | Legacy behavior | SPA replacement | Current evidence |
|---|---|---|---|
| Load a cached graph | Untyped JSON response | Generated OpenAPI contract plus explicit node, edge, marker, count, manifest, and query models | API/component verified |
| Scan and refresh | Start `scan-content`, poll output, reload cache | Same background tool and visible output/status | Component verified |
| Curated default scope | Modules, master_files overrides, and core files | Same semantic default | Engine/component verified |
| Browse the whole checkout | Expandable containment tree | Lazy expandable tree; collapsed branches do not create a 30k-node DOM | Component and visible-browser verified |
| Change scope | Tree checkboxes, default/all/none | Subtree checkboxes plus default, tick-all, and untick-all | Engine/component verified |
| Search the explorer | Flat matching tree rows | Bounded matching list over the full hierarchy | Component verified |
| Filter nodes | Kind, owner, text, and degree | Same independent filters | Engine/component verified |
| Filter relations | Five relation toggles | Same five relation toggles | Engine/component verified |
| Filter/physics policy | Hidden nodes were removed from force membership | Filters change visibility only; stable positions and full-scope force membership are deliberate | Engine verified |
| Large-catalog layout | Deterministic packed seed plus bounded force settle | Deterministic injected seed; automatic mode skips force settling above 4,000 nodes and paints the packed layout immediately | Engine and 30,331/41,703-node visible benchmarks verified |
| Small-scope physics | d3-force with live threshold | Same d3-force model and 1,500-node default threshold | Engine verified |
| Physics mode | Auto, on, and off | Same modes; explicit On is required to force live physics for a huge scope | Engine/component verified |
| Layout tuning | Kind/owner clustering, spacing, unlimited spacing, five seed modes | Same controls and tuned defaults | Component/type verified |
| Focus rings | Organize around selected node by BFS hop distance | Same BFS-based focus force and ring spacing | Engine/component verified |
| Ego view | Ctrl/Cmd-click component isolation and tier colors | Same isolation, explicit button, clear action, and tier colors | Engine/renderer verified |
| Force tuning | Repel, degree weighting, links, center, isolated pull, Barnes-Hut theta | Same live controls | Engine/component verified |
| Collision and motion | Collision, hub buffer, friction, cooling, ambient motion, jiggle | Same controls | Engine/component verified |
| Dragging | GPU picking, fixed node, drag temperature, temporary repel boost, optional pan | Same Sigma picking/drag lifecycle and temporary-only tuning | Engine/type verified; direct visible drag remains a manual playtest item |
| Graph rendering | Sigma WebGL over Graphology | Sigma 3 WebGL over Graphology 0.26, loaded as a lazy route chunk | Production build and visible WebView2 smoke verified |
| Selection and details | Canvas selection and path metadata | Selection, details, source actions, and shared selected search context | Component verified |
| Exact graph deep links | Custom selection state | `?selected=<graph-node-id>`; a deep-linked node is added to scope and restores shared selected context | Component and launcher-browser verified |
| Shared References | Pin graph nodes into sidebar | Same shared reference store and exact navigation | Component/type verified |
| Accessible fallback | Canvas only | Paginated semantic table for every visible node, with inspection actions | Axe/component verified |
| Missing module readmes | Separate Modular Debug page | Integrated Modular Debug panel | Component/type verified |
| Core-file marker lookup | Separate page | Integrated exact-core-path query | Component/type verified |
| Unresolved markers | First 200 rows only | Incremental 50-row pages with the complete count reachable | Component/type verified |
| Marker source/history | Open source and line history | Source actions plus corrected `/api/git/marker-history` route | API/type verified |
| Marker label repair | Stale-line checked edit then rescan | Same expected-line write guard and rescan workflow | API/component verified |

## Remaining acceptance work

- [x] Render curated and full authoritative/worst-case scopes in visible WebView2 and record load,
  interaction, WebGL-layer, response-size, and console evidence in `content-graph-renderer-decision.md`.
- [x] Verify exact selected-node deep links and related-result boosting against the real cache.
- [ ] Complete a direct keyboard-only pass through the accessible fallback and a canvas drag playtest.
- [ ] Exercise marker history and label repair against a disposable fixture or intentionally selected
  source line; do not mutate Meridian-Rift merely for a smoke test.
- [x] Cut `Launch Aphelion Content Tools.cmd` over to FastAPI plus the tracked production SPA.
- [x] Load the authoritative graph, selected-node deep link, boosted search, Lore catalog, restored groups,
  and authoring controls through the shipped launcher.
- [ ] Delete the legacy graph/debug assets only after the launcher gate and rollback window pass.

The SPA has implementation parity against the inventoried controls and is now the shipped browser path.
Legacy assets remain only for the explicit rollback window; deletion and the two manual interaction
items above are not represented as completed by this document.

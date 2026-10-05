# Aphelion Content Tools

Windows-first browser tools for authoring, maintaining, and understanding modular Aphelion/Nova
content outside the Meridian-Rift game repository. Currently includes **Home** (repository status,
local Git actions, and cache/storage management shared across every tool), the **Lore Editor** (catalog
review, writer groups, overrides, staged export), and the **Content Graph** (a visual map of
`modular_nova`/`modular_aphelion` modules, `master_files` overrides, and `NOVA EDIT`/`APHELION EDIT`
markers). Use the pills at the top of the page to switch between tools; Home carries its own accent
color to set it apart from the tool pages.

## Start here

1. Open this repository in GitHub Desktop and sign in.
2. Make sure your local `Meridian-Rift` checkout is available beside this repository, or have its full path ready.
3. Double-click [Launch Aphelion Content Tools.cmd](Launch%20Aphelion%20Content%20Tools.cmd).
4. The launcher opens the app in your browser and remembers the game-checkout path for later launches.

If Python 3.11+ with the pinned dependencies is already installed, the launcher uses it. Otherwise it
asks before downloading a private per-user Python runtime. Declining leaves installation instructions
and does not change the machine. GitHub Desktop remains responsible for sign-in, pushing, pull
requests, and merge conflicts.

## Data and collaboration model

Writer-authored overrides, groups, reviews, and assignments are deterministic records under
`tools/lore_editor/content/`. Those files are authoritative and are the files reviewed in pull
requests. LanceDB is a local, ignored projection for paging, graph data, and hybrid search; it can be
reconciled or rebuilt without changing authored records.

Use a separate Git branch (and preferably a separate worktree) for each writer or pull request. One
backend owns mutations in a workspace; multiple browser tabs may share it, but a second backend for the
same workspace is refused. The app requires expected record hashes on updates, so concurrent edits to
the same record produce a visible conflict instead of silently overwriting either writer.

## File Management

Served at `/file-management`. Use the repository panel to create a local branch and commit explicitly
selected tool-owned records; unrelated working-tree files are visible but cannot be staged by the app.
Open the relevant checkout in GitHub Desktop for pushes and pull requests. Use **Database and Git** to run
catalog refresh, validation, generation, and content-graph scan jobs without leaving this page — it
lists every tool's registered job, not just one tool's.

## Lore Editor

Use the catalog search and groups to find targets, mark current content as reviewed, or create a
per-record override. Global search combines keyword and semantic ranking across every tool. The shared
selected record boosts related results but does not hide stronger global matches; scope only filters
when you choose one explicitly. If the embedding model is unavailable, the UI says that search is in
keyword-only mode.

For a game change, commit the authored records and use **Prepare export**. Review the manifest, then
apply it only to a clean, unchanged game checkout. The app writes only
`modular_aphelion/modules/lore_overhaul/code/generated_lore_overrides.dm`; it refuses uncommitted authored
records, stale revisions, conflicts, dirty checkouts, and unexpected artifact changes. There is no
force override for a dirty game checkout.

## Content Graph

Open **Content Graph** and click **Scan modular content** to index the selected game checkout's modules, `master_files` overrides, and inline edit markers into a cached graph. Re-run the scan after the game checkout changes — it isn't automatic. Markers whose module attribution can't be confirmed against a real module directory appear in the Unresolved markers list rather than as graph edges, since most existing markers only carry a free-text reason, not a clean module id.

## Repository layout

- `webapp/` — the shared app shell: local HTTP server, Git integration, background job runner, and the Home page (`/`) shared by every tool.
- `tools/lore_editor/` — the Lore Editor tool (`/lore-editor`): canonical authored content and domain logic.
- `tools/content_graph/` — the Content Graph tool: scanner, marker parser, and its page.
- `references/` — maintainer and architecture documentation.
- `Launch Aphelion Content Tools.cmd` — the only launcher most writers need.

The launcher serves the tracked production SPA through the FastAPI backend. Contributors changing the
frontend run `npm --prefix webapp/frontend run build`; CI rebuilds the artifact and rejects drift, while
writers do not need Node installed.

The catalog-seed protocol is versioned and hash verified, and a local rebuild from the selected
Meridian-Rift checkout remains the fallback. No release seed manifest is currently published, so a
clean checkout uses that slower local fallback; the measured first-run limitation is tracked in the
[Windows packaging spike](references/architecture/windows-sidecar-packaging-spike.md). Catalog snapshots
and LanceDB generations are caches, not normal pull-request content. The game repository only receives
generated artifacts through explicit export workflows; never hand-edit a generated file.

## Contributing

Start with the repository [agent instructions](AGENTS.md), then read the normative
[maintainer guide](references/maintainer-guide.md) and the focused
[development guide index](references/development/README.md). The README stays writer-facing; backend,
frontend, schema, export, and verification contracts live in those versioned guides.

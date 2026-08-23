# Writer Guide

Aphelion Content Tools is a multi-tool suite; this guide covers the **Lore Editor** specifically — for
writers reviewing and editing Aphelion lore content. See [maintainer-guide.md](maintainer-guide.md) for
the Content Graph and other maintainer-facing tooling. It assumes you already have GitHub Desktop
installed and signed in, and a local checkout of `Meridian-Rift` somewhere on disk (it does not need to
be beside this repository, but the launcher will offer that location by default).

## First run

1. Open this repository (`aphelion-content-tools`) in GitHub Desktop and make sure it's up to date.
2. Double-click [`Launch Aphelion Content Tools.cmd`](../Launch%20Aphelion%20Content%20Tools.cmd).
3. If a compatible 64-bit Python 3.11+ with the tool's pinned dependencies isn't already on your machine, the launcher asks
   before downloading a private, per-user Python runtime into
   `%LOCALAPPDATA%\AphelionContentTools\runtime`. This does not touch any system-wide Python install.
   - If you decline, the launcher prints the manual install command
     (`python -m pip install -r tools\lore_editor\requirements.txt`) and exits without changing
     anything. Run it again after installing Python yourself.
4. The first time, the launcher asks for your `Meridian-Rift` checkout path (or offers a nearby one
   automatically if it finds `Meridian-Rift` next to this repository). You can continue without one —
   icon previews just won't resolve — and set it later by deleting
   `%LOCALAPPDATA%\AphelionContentTools\settings.json` and re-launching.
5. Your browser opens automatically to the Home page. Click the **Lore Editor** pill to start reviewing
   content. Closing the launcher's console window stops the local server.

On startup the app uses an already-valid local catalog, otherwise it verifies and activates the
versioned release seed. If the seed is unavailable and a game checkout is configured, it rebuilds the
catalog locally. A failed seed download never changes or blocks your authored records.

## Reviewing and editing content

- Use the search box and group checkboxes in the **Review** panel to find targets. Directional
  subtypes and redundant descriptions are hidden by default — toggle them on under **Visibility** if
  you need to see them.
- Selecting a target opens its entry editor. Mark it **Reviewed** once you've confirmed the content is
  correct, or **Flag for attention** if something needs a second opinion — flagging is always a writer
  decision, never automatic.
- To change base content, create an override from the selected target. Overrides live in
  `tools/lore_editor/content/overrides/` and are what the export workflow turns into the generated DM
  artifact — you never hand-edit generated DM.
- Catalog refresh, validation, and DM generation run from the **Database and Git** panel on
  the **File Management** page (not the Lore Editor page itself, since these jobs are shared across
  every tool). Refresh the catalog there after a game-repository update that adds or removes targets.

## Saving your work locally

The **Repositories** panel on the **Home** page covers this repository (`Aphelion Content Tools`) and, if
configured, your `Meridian-Rift` checkout (`Meridian-Rift`) separately:

1. Create a local branch for your change (e.g. `lore/company-review`). Use a separate branch/worktree
   for each pull request when several writers are active.
2. Select the authored records you intend to share and commit them with a message describing the
   change. The app cannot stage unrelated files.
3. Use **Open in GitHub Desktop** to push, open a pull request, or resolve anything more complex — the
   app never pushes, opens PRs, or handles GitHub credentials itself.

If the status panel shows **conflicts**, resolve them in GitHub Desktop before doing anything else —
the app refuses to commit or export against a conflicted repository.

If another writer changed the same record after you opened it, saving returns a conflict with the
base, current, and proposed versions. Review those versions and resolve the record deliberately; the
app does not silently choose a winner. Reviews and assignments are shared through the same pull request
as overrides and groups.

## Exporting to the game

Overrides only reach `Meridian-Rift` through the explicit staged export flow, run from the
**Game-repository export** panel on the **Home** page:

1. Commit the authored records selected for the export. **Prepare export** refuses uncommitted authored
   content so the manifest always names a Git commit that can reproduce it.
2. Click **Prepare export**. This validates your content and generates the runtime DM artifact into a
   new timestamped stage folder under `tools/lore_editor/stages/` — your `Meridian-Rift` checkout is
   never touched at this step.
3. Review the prepared stage's manifest (content revision, catalog hash, override count, affected type paths) in the **Prepared
   stage** list.
4. Click **Apply selected export**. The app only writes
   `modular_aphelion/modules/lore_overhaul/code/generated_lore_overrides.dm` in your game checkout, and
   only if all of these still hold:
   - the game checkout has no uncommitted changes and no Git conflicts,
   - the game checkout's revision hasn't moved since you prepared the export,
   - the existing generated artifact hasn't changed since you prepared the export.
5. After a successful apply, GitHub Desktop opens automatically for the game checkout so you can
   review the diff, commit, and open a pull request. If it can't be opened automatically (for example,
   it isn't installed), the export output area says so — the apply itself still succeeded either way;
   use the **Meridian-Rift** repository panel on the Home page or open GitHub Desktop manually instead.

### If apply is refused

Every refusal message tells you exactly what changed and leaves your game checkout untouched:

| Message contains... | What happened | What to do |
| --- | --- | --- |
| "uncommitted changes" | Something in the game checkout isn't committed | Commit or discard it in GitHub Desktop, then apply again |
| "Commit the selected records" | Authored content is not represented by the current tool commit | Commit the intended records, then prepare again |
| "unresolved Git conflicts" | The game checkout has an unfinished merge | Resolve the conflict in GitHub Desktop, then apply again |
| "revision changed" | Someone (or a `git pull`) moved the game checkout forward since you prepared | Prepare a new export — the old stage is now stale |
| "artifact changed" | The generated DM file itself was edited outside this workflow since you prepared | Prepare a new export; do not hand-edit generated DM |
| "module is missing" | The `modular_aphelion/modules/lore_overhaul` folder doesn't exist in that checkout | You're pointed at the wrong game checkout, or it needs updating first |

A stale projection is reported in File Management. Reconcile it to re-project the current branch's
canonical records. A stale catalog usually means the game repository changed since the seed or last
catalog refresh — run **Refresh catalog**, then reload the Lore Editor.

Maintainers changing this workflow must preserve the complete prepare/apply refusal contract in the
[export-safety development guide](development/export-safety.md).

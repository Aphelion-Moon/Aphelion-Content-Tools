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

On startup the app keeps an existing local catalog, otherwise it verifies and activates the
versioned release seed. If the seed is unavailable and a game checkout is configured, it rebuilds the
catalog locally. A failed seed download never changes or blocks your authored records. The current
release does not publish a seed manifest yet, so a clean checkout takes the local-rebuild path; keep the
launcher open while its progress is displayed. Maintainers are replacing this slow first-run path before
the desktop installer work proceeds.

## Reviewing and editing content

- The Lore Editor keeps the **Catalog** review queue on the left and the selected target's authoring
  surface on the right. Each pane scrolls independently so browsing does not push the editor below the
  page. On a narrow window the same controls stack with the queue first.
- Enter your name in **Reviewer** at the top of the workspace. The browser remembers it for later
  selections and launches; each saved review decision still records the reviewer explicitly.
- Use the search box and group checkboxes in the left review queue to find targets. Directional
  subtypes and redundant descriptions are hidden by default — toggle them on under **Visibility** if
  you need to see them. Results can be sorted by name, type path, review status, or review time.
- Selecting a target opens its entry editor. Mark it **Reviewed** once you've confirmed the content is
  correct, or **Flag for attention** if something needs a second opinion — flagging is always a writer
  decision, never automatic.
- Use **Group configuration** above the right pane to create or edit writer-maintained groups. The
  catalog queue remains available while that tab is open. Unsaved group changes are protected when
  switching tools, replacing a draft, or closing the page.
- To change base content, create an override from the selected target. Overrides live in
  `tools/lore_editor/content/overrides/` and are what the export workflow turns into the generated DM
  artifact — you never hand-edit generated DM.
- Catalog loading, validation, and DM generation run from the **Database and Git** panel on the
  **File Management** page. After a game-repository update, use **Load release catalog** when a
  maintainer has supplied a matching release manifest. It replaces the derived catalog while keeping
  authored records. An unavailable or incompatible release leaves the existing catalog in place.
  **Advanced catalog actions** contains local refresh, which needs the game build tools and probe;
  its output can be used for authoring but is not verified for export.

## Parsec feedback and idle chatter

Parsec, the husky in the shared sidebar, reports saves, searches, longer loads, background jobs,
connection trouble, and validation refusals without replacing the page you are working on. Her compact
station-radio log contains the short character-facing explanation. The affected panel keeps its normal
inline status, and the **Parsec** page keeps exact technical details in browser-local activity history
when troubleshooting is needed. The log can be Compact (the default), Collapsed, or Expanded.

Parsec occasionally comments on the current page while the app is idle. This defaults to **Rare** and
never quotes selected lore content. Open **Parsec** from the navigation to choose Off, Rare, Occasional,
or Frequent. Idle chatter pauses while you are typing, while work is running, while the live connection
needs attention, or while another Parsec message is visible.

After you interact with Parsec, choose whether she may leave the habitat. Her default roaming style favors
the edges of the app and avoids controls; **Annoying and intrusive** is an explicit option for cursor play,
loitering, demands for attention, and rare zoomies. **Stay in the habitat**, ask-each-time consent, and a
reduced-distraction switch are available when you want a quieter workspace. Tone, handling reactions, and
carry physics are also configurable. You can pick Parsec up by the scruff and move her; depending on those
settings she may dangle calmly, squirm, complain, pout, or land with a gentle bounce.

**Ask each time** offers **Allow this excursion** or **Stay in the habitat this time** before each
autonomous outing. Approving once keeps the ask-each-time preference. Choosing another interaction
dismisses an older request. Saving habitat-only settings brings her home; if you are holding her, she
returns after you finish the gesture.

The interaction bar offers Pat, Ball, Tug, Brush, Treat, Whistle, Bed, and Cage. Bed is a voluntary hangout
or a temporary timeout; it is not a care meter. Cage latches until you release her, and her reaction follows
her selected personality. The closed cage disables other interactions until you choose **Release**.
Each action has an icon and text label, and the selected toy stays highlighted until put away. Drag the
bed or cage artwork to keep it in the habitat or place it along the
app edge, and use **Return bed and cage home** on the Parsec page if either gets lost. You can also drop
Parsec onto either furnishing.

Audio is enabled by default after the browser's first direct interaction. The Parsec page has separate
master, voice, effects, alerts, and rare-idle sliders plus a complete off switch. Parsec animates regardless
of operating-system animation preferences. Choose **Reduce motion** on her page to use a representative
still frame instead. Companion settings,
familiarity, and furniture positions persist only in this browser unless you explicitly export the profile.
Reduced motion still completes timed transitions such as lying down and landing. Press Escape to finish
a held gesture or put away a toy; finishing brushing returns Parsec to her resting pose.
Pats and completed play build familiarity. Hovering over a treat or interrupting a toy animation does
not count as completed play. Handling and furniture dialogue appears in the radio log and activity history.

The **Parsec** page can filter activity by text, tool, event, outcome, and date. History is retained for
90 days by default; the available choices are 7, 30, 90, or 365 days, or until you clear it manually.
Use **Older** and **Newer** to browse history in pages of 100 records. JSON/CSV activity exports include
all records matching the applied filters, across every page; unapplied filter edits do not change an
export. Activity export and companion-profile export are separate. Clearing activity requires an
in-page confirmation and does not clear Parsec's profile. The journal never stores complete lore bodies,
and secret-shaped technical values are redacted before they reach browser storage. If this app version
cannot read a newer activity database, it preserves the data and offers a separate, confirmed reset rather
than deleting it automatically.

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

## Exporting lore to the game

Overrides only reach `Meridian-Rift` through the explicit staged export flow, run from the
**Game-repository export** panel on the **Home** page:

Preparation requires a verified release catalog for the selected game revision. Local catalog refresh
can supply authoring data, but source verification for local builds is not yet integrated. Those
catalogs are marked unverified and cannot be exported or packaged as release seeds. Keep authoring
normally; a maintainer must supply a matching verified release catalog before export.

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
| "catalog source is unverified" | The active catalog has no verified source provenance | Obtain a matching release manifest from a maintainer, then use **Load release catalog** |
| "catalog source revision" | The catalog belongs to a different game revision | Obtain a release manifest matching the selected game checkout, then use **Load release catalog** |
| "catalog hash" | The active targets do not match their provenance manifest | Use **Load release catalog** to restore verified data before preparing |
| "unresolved Git conflicts" | The game checkout has an unfinished merge | Resolve the conflict in GitHub Desktop, then apply again |
| "revision changed" | Someone (or a `git pull`) moved the game checkout forward since you prepared | Prepare a new export — the old stage is now stale |
| "artifact changed" | The generated DM file itself was edited outside this workflow since you prepared | Prepare a new export; do not hand-edit generated DM |
| "module is missing" | The `modular_aphelion/modules/lore_overhaul` folder doesn't exist in that checkout | You're pointed at the wrong game checkout, or it needs updating first |

A stale projection is reported in File Management. Reconcile it to re-project the current branch's
canonical records. A stale catalog usually means the game repository changed since the seed or last
catalog refresh. **Load release catalog** checks the selected game revision and refuses publication if
the checkout changes during the job. It never falls back to a local refresh. If the release manifest is
missing, ask a maintainer to provide one; retrying cannot create a release. **Refresh catalog** under
**Advanced catalog actions** updates local authoring data, but does not verify it for export.

Maintainers changing this workflow must preserve the complete prepare/apply refusal contract in the
[export-safety development guide](development/export-safety.md).

## Job Editor and Outfit Editor

Open either editor from the shared tool navigation. **Refresh source catalog** indexes the selected
game checkout. Search by name or type path, inspect inherited values and their owners, and choose:

- **Override** to add an Aphelion definition while retaining TG source.
- **Update module** to change a definition in its owning Nova/Aphelion file. When more than one module
  owns declarations, select the destination for additional overrides.
- **Create from this** to make a distinct child identity. The station-job bundle action links a new
  job, outfit, and ID trim; access is edited on the trim.
- **Replace** to create a distinct identity and select verified references to migrate. For jobs,
  explicitly retain or retire the original from player selection. Retirement retains the old type and
  its registered title/configuration identity; choose unique replacement names and aliases.

Equipment fields use the shared type picker and item preview. Contents retain order and counts.
**DM expression** exposes the exact field expression; the advanced procedure area edits complete DM
headers and bodies. Complex expressions are never simplified into a form value automatically. Save
and use **Reparse draft** to inspect effective values for that exact saved version before compiling.
**Reset** removes a local change; **Clear** explicitly sets `null`.

Use **Save draft → Validate and compile → Prepare changes → Apply reviewed changes**. Preparation
shows the exact source diff. Application requires a clean compatible game checkout and the same
source, draft, and toolchain that were validated. Any change requires validation again. Compilations
are temporary: restarting the app or validating several other drafts may require revalidation. After applying,
inspect the receipt and wait for catalog refresh/reconciliation. If the source changed independently,
use **Review source refresh**, inspect the differences, accept them into the draft, then save. Saving
a conflicting record never silently replaces the other writer's version.

Item previews show direction and frame controls. **Render character** runs native rendering for the
chosen species/body settings; **Launch test map** opens a private local BYOND session with equipment,
ID access, and equip hooks. **Stop** closes only the session's owned processes. These explicit actions
execute local game code and are not security sandboxes. The test body does not simulate saved player
preferences, loadouts, round scheduling, or special role body creation. Runtime failures appear in
the operation panel and bounded log. Missing BYOND disables compilation/native preview/application;
draft editing and static inspection remain available.

Existing generated definitions reopen their owning saved draft. Shared jobs/outfits/trims are flagged
through references and linked navigation. A reference or search result from an older catalog must be
resolved against a current catalog before editing. External saved preferences, bans, operator
configuration, dynamic references, and map placements remain a separate review responsibility.

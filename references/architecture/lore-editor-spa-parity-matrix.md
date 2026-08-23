# Lore Editor SPA parity matrix

**Recorded:** 2026-08-22  
**Legacy surface:** `tools/lore_editor/web/index.html` and `tools/lore_editor/web/app.js`  
**Replacement:** `webapp/frontend/src/tools/loreEditor/` behind the typed FastAPI routes

This matrix is the deletion gate for the legacy Lore Editor. “Component verified” means the behavior
has an automated frontend or API regression. The shipped launcher has been cut over, but destructive
writer scenarios and the rollback window remain separate acceptance gates.

| Writer workflow | Legacy behavior | SPA replacement | Current evidence |
|---|---|---|---|
| Browse the full catalog | Incremental pages with a manual load-more control | Paged feed plus virtualized rows and automatic prefetch; every matching row remains reachable | Component verified |
| Search and sort | Debounced text search; name, type-path, status, and review-time sorting | Server-backed text search with the same sorts | Component verified |
| Filter by several groups | Checkbox set, including select-all and clear | Multi-select checkbox set, including select-all and clear | Component verified |
| Filter by several statuses | Checkbox set | Multi-select checkbox set | Component verified |
| Directional/redundant visibility | Explicit opt-in toggles and suppression counts | Same opt-in toggles and counts | Component verified |
| Clear filters | Reset search, groups, statuses, sort, and visibility | One reset restores the SPA defaults | Component verified |
| Identify status and grouping | Row status, group labels, match-reason tooltip, selected status pill | Row status/group labels plus selected-entry advanced details with match reasons | Component verified |
| Select from global search | Custom event selected the exact type path | Typed deep link and shared selected context select the exact type path; context boosts related search results but never filters them | Component verified |
| Create an override | Create mode, existing/new source group, validate, save, generate | Same workflow; IDs are collision-free and canonical Git records are written before the LanceDB projection | Component verified |
| Edit an override | Edit text and generated fields, then validate/save/generate | Same, with required expected-record hash | Component verified |
| Remove an override | Confirmation, delete, regenerate | Same, with required expected-record hash | Component verified |
| Base/override text preview | Side-by-side name and description | Same | Component verified |
| Examine-more fields | Requirement and special description | Same | Component verified |
| Icon overrides | Main, worn, and in-hand DMI file/state selection; base and override previews; unavailable-state warning | Same slots, repository file/state lookup, previews, preview errors, and unavailable-state warning | Component verified |
| AutoWiki fields | Enabled, slug, summary, export icon | Same | Component verified |
| Validation feedback | Prevent save and list field issues | Same, using typed validation issues | Component verified |
| Review decisions | Reviewer, notes, reviewed, needs-attention, clear | Same, with independent review record hashes | Component verified |
| Manual group assignment | Persist explicit assignments alongside automatic matches | Same, with independent assignment record hashes | Component verified |
| Group configuration | Create/edit label, color, keywords, keyword scope, and type-path prefixes | Same, plus safe delete with assignment cleanup | Component verified |
| Open source | Original and override in editor, Explorer, or GitHub, with original line anchor | Same actions; override opens its real canonical per-record JSON rather than the retired virtual group file | Component verified |
| Shared References | Pin selected catalog targets into the cross-tool sidebar | Shared SPA sidebar; pin, exact navigation, and remove are restored | Component verified |
| Unsaved-change protection | Browser unload warning for an edited entry | Browser unload, SPA route, tab, and selection guards cover override drafts and review notes | Component verified |
| Concurrent writer conflict | Expected hash was sent but legacy UI had no comparison workflow | Typed 409; Base/Current/Proposed comparison; no force overwrite or automatic merge | Component verified |
| Duplicate create conflict | Duplicate group create could overwrite; duplicate entry create was a generic 400 | Both are safe structured 409 conflicts and preserve the current record | API verified |
| Accessibility | Basic labels and live list | Keyboard listbox/combobox behavior, focused errors/conflicts, live status, landmarks, and automated axe checks | Component verified |

## Remaining acceptance work

- [ ] Exercise create, edit, conflict, review, grouping, icon, AutoWiki, reference, and delete scenarios in a real browser against a real Meridian-Rift catalog.
- [x] Cut `Launch Aphelion Content Tools.cmd` over to FastAPI plus the tracked production SPA.
- [x] Through the shipped launcher, load the real 17,500-target catalog, all eight restored groups,
  select an entry, and expose create-override, review, assignment, reference, and source controls without
  mutating canonical content.
- [ ] Repeat the destructive create/edit/conflict/delete scenarios through the launcher against a disposable branch/worktree.
- [ ] Delete the legacy server and Lore assets only after the launcher gate passes and a short rollback window ends.

The SPA implementation is feature-complete against the inventoried Lore Editor controls and the shipped
launcher now serves it. Destructive browser scenarios and legacy deletion remain open and are not
represented as completed by this document.

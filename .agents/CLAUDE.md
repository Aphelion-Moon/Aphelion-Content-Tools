# Meridian Rift

> **Scope: this file governs the Meridian-Rift game checkout, not this repository.**
>
> You are reading this inside `aphelion-content-tools` — a Python/TypeScript tool suite that *targets*
> Meridian-Rift, reading its content and exporting generated artifacts into it. These files were brought
> here early on as a shared foundation, and every rule below (DM style, edit markers, modular placement,
> BYOND compile gates) applies to code **in the game checkout**, which normally sits beside this
> repository as a sibling directory.
>
> **They do not describe this repository's own code.** Nothing here governs `webapp/`, `tools/*/`, the
> web frontend, or the Python backend. For those, the authority is
> [`references/maintainer-guide.md`](../references/maintainer-guide.md).
>
> Read this file when the task touches the game checkout's DM/Rust. Read the maintainer guide when the
> task touches this tool suite.

BYOND/Dream Maker SS13 codebase; a Nova Sector downstream, which is itself a fork of /tg/station that
continuously merges upstream. That merge pressure is why the placement and comment rules below are
strict — they are what makes conflicts resolvable.

## Communication

Be direct. Answer the actual question or make the requested change without ornamental wording. Avoid
vague metaphors; do not talk about the "shape" of a solution. Prefer concrete, verifiable statements,
and say plainly when something is unknown, untested, or inferred from local context rather than
confirmed.

## Required reading

Read the guide before writing code in an area it covers. These are versioned in-repo and change;
do not work from memory of them.

- `.github/guides/STYLE.md` — all style decisions.
- `.github/guides/AUTODOC.md` — doc comment format. Required, see Comments below.
- `.github/guides/STANDARDS.md` — architecture, security, optimization, DM quirks.
- `modular_nova/readme.md` — the modularization handbook. Decides *where* code goes; outranks the
  instinct to edit a core file.
- `.github/guides/HARDDELETES.md` before touching `Destroy()` or anything holding refs.
- `.github/guides/VISUALS.md` before touching planes, layers, filters, or overlays.

## Before editing

Research the codebase before making meaningful edits. Use `rg` to find existing implementations,
defines, macros, helper procs, datums, components, and patterns. Do not assume a new structure is
needed until nearby code proves it, and prefer changing the smallest reasonable surface that
satisfies the request.

Readability and maintainability come first — code should be easy for a future maintainer to review
and safely modify. Reuse existing macros, defines, helpers, component patterns, and subsystem
structures rather than reinventing infrastructure that already exists. Keep logic object-oriented and
idiomatic for DM. Avoid duplicated code; extract or reuse a local helper when it meaningfully
improves clarity. Avoid unnecessary guards, indirection, and boilerplate — cover realistic failure
modes, not theoretical edge cases that add disproportionate complexity.

## Where code goes (Nova modular rules)

- New Nova content: `modular_nova/modules/<module_id>/{code,icons,sound}/`. Flat — do **not** mirror
  the core folder tree inside a module, and do not mix file types across those folders.
- New Aphelion content: `modular_aphelion/modules/<module_id>/{code,icons,sound}/`, using the same
  flat layout.
- Overrides of core files: `modular_nova/master_files/`, mirroring the core path exactly.
  `code/modules/mob/living/living.dm` -> `modular_nova/master_files/code/modules/mob/living/living.dm`.
- Unavoidable Aphelion core edits get marker comments, with the module ID:
  - `// APHELION EDIT ADDITION START - MODULE_ID` ... `// APHELION EDIT ADDITION END`
  - `/* // APHELION EDIT REMOVAL START - MODULE_ID` ... `*/ // APHELION EDIT REMOVAL END`
  - `// APHELION EDIT CHANGE - ORIGINAL: <the full original line>`
- Preserve existing NOVA EDIT markers in inherited Nova-owned regions. Do not add new NOVA EDIT
  markers for Aphelion work.
  - Multi-line changes are a removal+addition pair, not a multi-line CHANGE.
- Defines used in more than one file: `code/__DEFINES/~nova_defines` or the corresponding Aphelion
  define location. Single-file defines are
  declared at the top and `#undef`'d at the bottom.
- New TGUI files start with `// THIS IS A NOVA SECTOR UI FILE` on line 1 when required by the
  current TGUI tooling. This header is pipeline metadata, not an edit-marker choice. Aphelion edits
  to upstream TGUI use APHELION EDIT markers, inline in the JSX tag where possible; preserve NOVA
  EDIT markers in inherited Nova-owned regions.
- Do not edit tg maps. Use the automapper (`_maps/nova/automapper/automapper_config.toml` templates,
  or the simple area automapper for a single item). There are no `_nova` map variants.
- Non-trivial modules need a `readme.md` from `modular_nova/module_template.md`.
- In modular code, delete dead code rather than commenting it out. Does not apply to core edits.

Two judgment calls the handbook stresses: a tg-specific bugfix should go upstream rather than be
modularized here; and do not copy a whole tg proc into a modular override to change one line — that
rots silently when upstream moves. For Aphelion-owned changes, a marked APHELION EDIT is often the
better choice, especially in hot procs like `Life()` where override chaining costs real overhead.

## Comments

Keep discretionary commentary at zero — only where the code is genuinely non-obvious, and prefer
fixing a wrong existing comment over adding a new one. The mandatory exceptions:

- AUTODOC: `/** */` on classes and public procs, `///` on class-level vars and defines. One-line
  summary first, then detail, then `Arguments: * arg - meaning`.
- APHELION EDIT markers on Aphelion-owned core edits; preserve NOVA EDIT markers on inherited
  Nova-owned core regions.

No box comments as headers.

## Style essentials

Tabs, never spaces, and never mid-line alignment. Absolute type paths beginning with `/`, snake_case,
datums start with `/datum`. Early returns over nesting. `static`, not `global`. No magic numbers —
`#define` them. Time defines (`1.5 SECONDS`). Descriptive names, never `M`/`C`/`H`; units in the name
when not deciseconds. `::` over `initial()` for static types. `src.var = var` for Initialize args.
Named arguments where the meaning is not obvious. Macros are SCREAMING_SNAKE_CASE, parenthesized,
hygienic, and `#undef`'d.

## Correctness

- Treat player input as hostile. Re-check context *after* an input resolves. Never `locate(ref)`
  without scoping to a list.
- `PROC_REF`/`TYPE_PROC_REF`/`GLOBAL_PROC_REF` always; `SIGNAL_HANDLER` on every registered proc.
- `for (var/type/name as anything in list)` when the list is known-homogeneous.
- `process()` must be frame-independent: per-second values times `seconds_per_tick`.
- `Destroy()` clears references and has no side effects. Undo in `Destroy()` whatever
  `Initialize()` did.
- Prefer explicit `return value` over bare `.`; `. = ..()` is the accepted exception.
- Never the `:` operator, never string type paths, never `walk*()` — use `SSmove_manager`.
- Ghost roles, antags and event mobs must support `get_policy(KEYWORD)`.

## Verification

Compile before reporting done, rather than reasoning about whether DM will accept a change:

```
"/c/Program Files (x86)/BYOND/bin/dm.exe" tgstation.dme
```

Takes ~65s. Expect `0 errors` and a small number of pre-existing `#warn` warnings about building via
BUILD.cmd. The resulting `.dmb` is gitignored. If a change is not tested, say so explicitly.

## Workflow

Leave changes in the working tree. Do not `git commit` or push unless explicitly asked.

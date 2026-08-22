from __future__ import annotations

from pathlib import Path

from webapp.store import db
from webapp.store.schema import decode, table

from .model import (
    SUPPORTED_ICON_KEYS,
    CatalogTarget,
    LoreCorpus,
    LoreEntry,
    WikiRecord,
    as_bool,
    as_object,
    as_string,
    freeze_json,
)

# Overrides no longer live in real files -- each one carries a free-text `group` label instead (still
# picked/typed the same way in the UI, see app.js's "entity group" selector), but `LoreEntry.source_path`
# and everything downstream of it (validation issue paths, the entry list's "category", the export
# manifest) still expects a `Path`. This synthesizes one from the group so none of that code needs to
# change: it's a virtual identifier, not a real filesystem location.
OVERRIDES_GROUP_ROOT = Path("tools/lore_editor/content/overrides")


def source_path_for_group(group: str) -> Path:
    return OVERRIDES_GROUP_ROOT / f"{group}.json"


def group_for_source_path(source_path: Path | str) -> str:
    return Path(source_path).stem


def make_catalog_target(raw_target: object) -> CatalogTarget:
    frozen_target = freeze_json(raw_target)
    target_object = as_object(frozen_target)
    type_path = None
    label = None
    editable_root = None
    parent_type = None
    base_name = None
    base_description = None
    field_profile = None
    if target_object is not None:
        type_path = as_string(target_object.get("type_path"))
        label = as_string(target_object.get("label"))
        editable_root = as_string(target_object.get("editable_root"))
        parent_type = as_string(target_object.get("parent_type"))
        base_values = as_object(target_object.get("base_values"))
        if base_values is not None:
            base_name = as_string(base_values.get("name"))
            base_description = as_string(base_values.get("description"))
        field_profile = as_string(target_object.get("field_profile"))
    return CatalogTarget(
        raw_data=frozen_target,
        type_path=type_path,
        label=label,
        editable_root=editable_root,
        parent_type=parent_type,
        base_name=base_name,
        base_description=base_description,
        field_profile=field_profile,
    )


def make_lore_entry(source_path: Path, raw_entry: object) -> LoreEntry:
    frozen_entry = freeze_json(raw_entry)
    entry_object = as_object(frozen_entry)
    entry_id = None
    type_path = None
    name = None
    description = None
    special_desc_requirement = None
    special_desc = None
    icons: list = []
    wiki = None

    if entry_object is not None:
        entry_id = as_string(entry_object.get("id"))
        type_path = as_string(entry_object.get("type_path"))
        name = as_string(entry_object.get("name"))
        description = as_string(entry_object.get("description"))
        special_desc_requirement = as_string(entry_object.get("special_desc_requirement"))
        special_desc = as_string(entry_object.get("special_desc"))

        icon_object = as_object(entry_object.get("icons"))
        if icon_object is not None:
            from .model import IconRecord
            for key in SUPPORTED_ICON_KEYS:
                icon_value = as_object(icon_object.get(key))
                if icon_value is None:
                    continue
                icon_file = as_string(icon_value.get("file"))
                icon_state = as_string(icon_value.get("state"))
                if icon_file is None or icon_state is None:
                    continue
                icons.append(IconRecord(key=key, file=icon_file, state=icon_state))

        wiki_object = as_object(entry_object.get("wiki"))
        if wiki_object is not None:
            wiki = WikiRecord(
                enabled=as_bool(wiki_object.get("enabled")),
                slug=as_string(wiki_object.get("slug")),
                summary=as_string(wiki_object.get("summary")),
                export_icon=as_bool(wiki_object.get("export_icon")),
            )

    return LoreEntry(
        source_path=source_path,
        entry_id=entry_id,
        type_path=type_path,
        name=name,
        description=description,
        special_desc_requirement=special_desc_requirement,
        special_desc=special_desc,
        icons=tuple(icons),
        wiki=wiki,
        raw_data=frozen_entry,
    )


def load_catalog_targets(repo_root: Path) -> tuple[CatalogTarget, ...]:
    rows = db.all_rows(table(repo_root, "catalog_targets"))
    targets = tuple(make_catalog_target(decode(row)) for row in rows)
    return tuple(sorted(targets, key=lambda target: target.type_path or ""))


def load_corpus(repo_root: Path) -> LoreCorpus:
    targets = load_catalog_targets(repo_root)
    override_rows = db.all_rows(table(repo_root, "overrides"))
    entries = tuple(
        make_lore_entry(source_path_for_group(row["group"]), decode(row))
        for row in override_rows
    )
    # Deterministic order regardless of the store's own row order -- several validation/generation code
    # paths (duplicate-id/duplicate-field-ownership messages, generated DM ordering) depend on a stable
    # entry order, the same way the old per-file JSON store's alphabetical file listing was implicitly
    # stable.
    entries = tuple(sorted(entries, key=lambda entry: (entry.source_path.as_posix(), entry.entry_id or "")))
    return LoreCorpus(targets=targets, entries=entries)


def list_entity_groups(repo_root: Path) -> list[str]:
    rows = db.all_rows(table(repo_root, "overrides"))
    return sorted({row["group"] for row in rows})


def list_entity_files(repo_root: Path) -> list[str]:
    """Return the set of override "group" identifiers, formatted as the virtual paths the UI already
    expects (see app.js's "entity group" dropdown, populated from this list)."""
    return [source_path_for_group(group).as_posix() for group in list_entity_groups(repo_root)]

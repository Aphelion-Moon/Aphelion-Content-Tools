from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.dmi import Dmi
from tools.lore_editor.model import LoreCorpus
from tools.lore_editor.source import load_corpus, make_lore_entry
from tools.lore_editor.tests.store_helpers import seed_override, seed_targets
from tools.lore_editor.validation import validate_corpus


def write_dmi(path: Path, *states: str) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	dmi = Dmi(32, 32)
	for state_name in states:
		state = dmi.state(state_name)
		state.frame(Image.new("RGBA", (32, 32), (255, 0, 0, 255)))
	dmi.to_file(path)


class ValidateCorpusTests(unittest.TestCase):
	def init_repo(self, repo_root: Path, *, targets: object | None = None) -> None:
		if targets is None:
			targets = [
				{"type_path": "/obj/item/radio"},
				{"type_path": "/obj/item/radio/headset"},
			]
		seed_targets(repo_root, targets)

	def issue_rows(self, repo_root: Path) -> list[tuple[str, str, str]]:
		corpus = load_corpus(repo_root)
		return [
			(issue.path, issue.message, issue.severity)
			for issue in validate_corpus(repo_root, corpus)
		]

	def test_validate_corpus_reports_duplicate_entry_ids(self) -> None:
		# The store's own primary key already prevents two *stored* overrides from sharing an id (see
		# `api.create_entry`'s `require_new` guard) -- but `validate_corpus` itself is a pure function
		# over whatever `LoreCorpus` it's given, and a batch candidate build (`api.validate_entries`) can
		# still momentarily construct one with a duplicate id before it's ever written. Exercise that
		# pure-function behavior directly rather than via the store.
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(repo_root)
			corpus = load_corpus(repo_root)
			first = make_lore_entry(Path("tools/lore_editor/content/overrides/alpha-first.json"), {"id": "shared.entry", "type_path": "/obj/item/radio"})
			second = make_lore_entry(Path("tools/lore_editor/content/overrides/beta-second.json"), {"id": "shared.entry", "type_path": "/obj/item/radio/headset"})
			corpus = LoreCorpus(targets=corpus.targets, entries=(first, second))

			issues = [(issue.path, issue.message, issue.severity) for issue in validate_corpus(repo_root, corpus)]

			self.assertEqual(
				issues,
				[
					(
						"tools/lore_editor/content/overrides/beta-second.json#shared.entry.id",
						"Duplicate lore entry id 'shared.entry'; first defined in tools/lore_editor/content/overrides/alpha-first.json.",
						"error",
					)
				],
			)

	def test_validate_corpus_reports_duplicate_target_field_ownership(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(repo_root)
			seed_override(repo_root, "alpha-first", {"id": "alpha.first", "type_path": "/obj/item/radio", "name": "One"})
			seed_override(repo_root, "beta-second", {"id": "beta.second", "type_path": "/obj/item/radio", "name": "Two"})

			issues = self.issue_rows(repo_root)

			self.assertEqual(
				issues,
				[
					(
						"tools/lore_editor/content/overrides/beta-second.json#beta.second.name",
						"Target field 'name' for /obj/item/radio is already owned by tools/lore_editor/content/overrides/alpha-first.json#alpha.first.name.",
						"error",
					)
				],
			)

	def test_validate_corpus_rejects_entry_ids_outside_the_schema_grammar(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(repo_root)
			seed_override(
				repo_root,
				"alpha",
				{"id": "missing' OR true OR id = 'alpha.entry", "type_path": "/obj/item/radio"},
			)

			issues = self.issue_rows(repo_root)

			self.assertEqual(len(issues), 1)
			self.assertEqual(issues[0][1], "Entry id must match ^[A-Za-z0-9][A-Za-z0-9._-]*$.")

	def test_validate_corpus_rejects_invalid_absolute_type_paths(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(repo_root)
			seed_override(repo_root, "alpha", {"id": "alpha.entry", "type_path": "obj/item/radio"})

			issues = self.issue_rows(repo_root)

			self.assertEqual(
				issues,
				[
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.type_path",
						"Type path must be an absolute BYOND path with identifier segments.",
						"error",
					)
				],
			)

	def test_validate_corpus_accepts_uppercase_byond_type_path_segments(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(repo_root, targets=[{"type_path": "/obj/item/HFR_core"}])
			seed_override(repo_root, "alpha", {"id": "alpha.entry", "type_path": "/obj/item/HFR_core"})

			self.assertEqual(self.issue_rows(repo_root), [])

	def test_validate_corpus_accepts_optional_special_description_overrides(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(repo_root)
			seed_override(repo_root, "alpha", {
				"id": "alpha.entry",
				"type_path": "/obj/item/radio",
				"special_desc_requirement": "mindshield",
				"special_desc": "A protected briefing is etched into the casing.",
			})

			self.assertEqual(self.issue_rows(repo_root), [])

	def test_validate_corpus_rejects_special_description_overrides_for_named_datums(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(
				repo_root,
				targets=[
					{
						"type_path": "/datum/language/common",
						"field_profile": "named_datum",
					},
				],
			)
			seed_override(repo_root, "alpha", {
				"id": "alpha.entry",
				"type_path": "/datum/language/common",
				"special_desc_requirement": "none",
				"special_desc": "This cannot be assigned to a language datum.",
			})

			self.assertEqual(
				self.issue_rows(repo_root),
				[
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.special_desc_requirement",
						"Field profile 'named_datum' does not support special description overrides.",
						"error",
					),
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.special_desc",
						"Field profile 'named_datum' does not support special description overrides.",
						"error",
					),
				],
			)

	def test_validate_corpus_rejects_unknown_special_description_requirement(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(repo_root)
			seed_override(repo_root, "alpha", {
				"id": "alpha.entry",
				"type_path": "/obj/item/radio",
				"special_desc_requirement": "classified",
			})

			self.assertEqual(
				self.issue_rows(repo_root),
				[
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.special_desc_requirement",
						"Special description requirement must be one of contractor, faction, job, mindshield, none, role, syndicate, syndicate_toy.",
						"error",
					)
				],
			)

	def test_validate_corpus_rejects_type_paths_absent_from_catalog(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(
				repo_root,
				targets=[
					{"type_path": "/obj/item/radio"},
				],
			)
			seed_override(repo_root, "alpha", {"id": "alpha.entry", "type_path": "/obj/item/megaphone"})

			issues = self.issue_rows(repo_root)

			self.assertEqual(
				issues,
				[
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.type_path",
						"Type path '/obj/item/megaphone' is not present in the catalog.",
						"error",
					)
				],
			)

	def test_validate_corpus_rejects_unsupported_icon_keys(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(repo_root)
			seed_override(repo_root, "alpha", {
				"id": "alpha.entry",
				"type_path": "/obj/item/radio",
				"icons": {
					"badge": {"file": "icons/radio.dmi", "state": "radio"},
				},
			})

			issues = self.issue_rows(repo_root)

			self.assertEqual(
				issues,
				[
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.icons.badge",
						"Unsupported icon key 'badge'.",
						"error",
					)
				],
			)

	def test_validate_corpus_reports_missing_icon_files(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(repo_root)
			seed_override(repo_root, "alpha", {
				"id": "alpha.entry",
				"type_path": "/obj/item/radio",
				"icons": {
					"icon": {"file": "icons/missing.dmi", "state": "radio"},
				},
			})

			issues = self.issue_rows(repo_root)

			self.assertEqual(
				issues,
				[
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.icons.icon.file",
						"Icon file 'icons/missing.dmi' does not exist.",
						"error",
					)
				],
			)

	def test_validate_corpus_reports_missing_dmi_states(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(repo_root)
			write_dmi(repo_root / "icons" / "fixture.dmi", "present")
			seed_override(repo_root, "alpha", {
				"id": "alpha.entry",
				"type_path": "/obj/item/radio",
				"icons": {
					"icon": {"file": "icons/fixture.dmi", "state": "missing"},
				},
			})

			issues = self.issue_rows(repo_root)

			self.assertEqual(
				issues,
				[
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.icons.icon.state",
						"Icon state 'missing' was not found in icons/fixture.dmi.",
						"error",
					)
				],
			)

	def test_validate_corpus_rejects_invalid_wiki_slugs(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(repo_root)
			seed_override(repo_root, "alpha", {
				"id": "alpha.entry",
				"type_path": "/obj/item/radio",
				"wiki": {
					"enabled": True,
					"slug": "Bad Slug",
					"summary": "summary",
					"export_icon": False,
				},
			})

			issues = self.issue_rows(repo_root)

			self.assertEqual(
				issues,
				[
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.wiki.slug",
						"Wiki slug must match ^[a-z0-9]+(?:-[a-z0-9]+)*$.",
						"error",
					)
				],
			)

	def test_validate_corpus_rejects_missing_required_wiki_members(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(repo_root)
			seed_override(repo_root, "alpha", {
				"id": "alpha.entry",
				"type_path": "/obj/item/radio",
				"wiki": {
					"enabled": True,
				},
			})

			issues = self.issue_rows(repo_root)

			self.assertEqual(
				issues,
				[
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.wiki.slug",
						"Field 'slug' is required.",
						"error",
					),
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.wiki.summary",
						"Field 'summary' is required.",
						"error",
					),
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.wiki.export_icon",
						"Field 'export_icon' is required.",
						"error",
					),
				],
			)

	def test_validate_corpus_rejects_extra_nested_fields(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(repo_root)
			write_dmi(repo_root / "icons" / "fixture.dmi", "radio")
			seed_override(repo_root, "alpha", {
				"id": "alpha.entry",
				"type_path": "/obj/item/radio",
				"icons": {
					"icon": {"file": "icons/fixture.dmi", "state": "radio", "extra": "x"},
				},
				"wiki": {
					"enabled": True,
					"slug": "alpha-entry",
					"summary": "summary",
					"export_icon": False,
					"extra": "x",
				},
			})

			issues = self.issue_rows(repo_root)

			self.assertEqual(
				issues,
				[
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.icons.icon.extra",
						"Unsupported field 'extra'.",
						"error",
					),
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.wiki.extra",
						"Unsupported field 'extra'.",
						"error",
					),
				],
			)

	def test_validate_corpus_rejects_icon_path_traversal(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(repo_root)
			seed_override(repo_root, "alpha", {
				"id": "alpha.entry",
				"type_path": "/obj/item/radio",
				"icons": {
					"icon": {"file": "../outside.dmi", "state": "radio"},
				},
			})

			issues = self.issue_rows(repo_root)

			self.assertEqual(
				issues,
				[
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.icons.icon.file",
						"Icon file '../outside.dmi' must stay within the repository root.",
						"error",
					)
				],
			)

	def test_validate_corpus_returns_issues_in_deterministic_order(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(repo_root)
			seed_override(repo_root, "beta", {
				"id": "beta.entry",
				"type_path": "/obj/item/radio",
				"icons": {
					"icon": {"file": "icons/missing.dmi", "state": "radio"},
				},
			})
			seed_override(repo_root, "alpha", {
				"id": "alpha.entry",
				"type_path": "obj/item/radio",
				"wiki": {
					"enabled": True,
					"slug": "Bad Slug",
					"summary": "summary",
					"export_icon": False,
				},
			})

			issues = self.issue_rows(repo_root)

			self.assertEqual(
				issues,
				[
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.type_path",
						"Type path must be an absolute BYOND path with identifier segments.",
						"error",
					),
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.wiki.slug",
						"Wiki slug must match ^[a-z0-9]+(?:-[a-z0-9]+)*$.",
						"error",
					),
					(
						"tools/lore_editor/content/overrides/beta.json#beta.entry.icons.icon.file",
						"Icon file 'icons/missing.dmi' does not exist.",
						"error",
					),
				],
			)

	def test_validate_corpus_rejects_duplicate_autowiki_slugs(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(
				repo_root,
				targets=[
					{"type_path": "/obj/item/radio"},
					{"type_path": "/obj/item/radio/headset"},
				],
			)
			seed_override(repo_root, "alpha-first", {
				"id": "alpha.first",
				"type_path": "/obj/item/radio",
				"wiki": {
					"enabled": True,
					"slug": "shared-radio",
					"summary": "First.",
					"export_icon": False,
				},
			})
			seed_override(repo_root, "beta-second", {
				"id": "beta.second",
				"type_path": "/obj/item/radio/headset",
				"wiki": {
					"enabled": True,
					"slug": "shared-radio",
					"summary": "Second.",
					"export_icon": False,
				},
			})

			issues = self.issue_rows(repo_root)

			self.assertEqual(
				issues,
				[
					(
						"tools/lore_editor/content/overrides/beta-second.json#beta.second.wiki.slug",
						"Duplicate AutoWiki slug 'shared-radio'; first defined in tools/lore_editor/content/overrides/alpha-first.json#alpha.first.",
						"error",
					)
				],
			)

	def test_validate_corpus_requires_a_primary_icon_for_autowiki_icon_export(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(repo_root, targets=[{"type_path": "/obj/item/radio"}])
			seed_override(repo_root, "alpha", {
				"id": "alpha.entry",
				"type_path": "/obj/item/radio",
				"wiki": {
					"enabled": True,
					"slug": "alpha-entry",
					"summary": "summary",
					"export_icon": True,
				},
			})

			issues = self.issue_rows(repo_root)

			self.assertEqual(
				issues,
				[
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.wiki.export_icon",
						"AutoWiki icon export requires an 'icons.icon' record.",
						"error",
					)
				],
			)

	def test_validate_corpus_rejects_icons_for_named_datums(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			self.init_repo(
				repo_root,
				targets=[{"type_path": "/datum/language", "field_profile": "named_datum"}],
			)
			write_dmi(repo_root / "icons" / "fixture.dmi", "radio")
			seed_override(repo_root, "alpha", {
				"id": "alpha.entry",
				"type_path": "/datum/language",
				"icons": {"icon": {"file": "icons/fixture.dmi", "state": "radio"}},
			})

			issues = self.issue_rows(repo_root)

			self.assertEqual(
				issues,
				[
					(
						"tools/lore_editor/content/overrides/alpha.json#alpha.entry.icons",
						"Field profile 'named_datum' does not support icon overrides.",
						"error",
					)
				],
			)


if __name__ == "__main__":
	unittest.main()

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tools.lore_editor import export
from tools.lore_editor.catalog import activate_catalog_targets, read_current_targets
from tools.lore_editor.export import apply_export, prepare_export
from tools.lore_editor.reconcile import scan_canonical_records
from tools.lore_editor.records import atomic_write_record, record_path
from tools.lore_editor.tests.store_helpers import seed_override, seed_targets
from webapp.git_adapter import RepositoryStatus, repository_revision

RADIO_TARGET = {
	"type_path": "/obj/item/radio",
	"label": "radio",
	"editable_root": "/obj/item",
	"parent_type": "/obj/item",
	"field_profile": "atom_like",
	"base_values": {"name": "radio", "description": "radio"},
	"icon_metadata": {},
}


def run_git(repo_root: Path, *arguments: str) -> None:
	subprocess.run(["git", "-C", str(repo_root), *arguments], check=True, capture_output=True, text=True)


class ExportTests(unittest.TestCase):
	def setUp(self) -> None:
		model = patch("webapp.store.embeddings._load_model", return_value=None)
		model.start()
		self.addCleanup(model.stop)

	def test_prepare_refuses_stale_unverified_or_changed_catalog_before_creating_stage(self) -> None:
		for problem in ("revision", "unverified", "hash"):
			with self.subTest(problem=problem), TemporaryDirectory() as temp:
				tool, game, stages = self.make_prepared_pair(Path(temp))
				activate_catalog_targets(tool, [RADIO_TARGET], source_game_revision="older-revision" if problem == "revision" else repository_revision(game), source_provenance="unverified" if problem == "unverified" else "release-seed")
				if problem == "hash":
					seed_targets(tool, [{**RADIO_TARGET, "label": "Changed after publication"}])
				with self.assertRaisesRegex(ValueError, "catalog|Catalog"):
					prepare_export(tool, game, stages)
				self.assertFalse(stages.exists())

	def test_rejects_an_in_root_alias_for_the_allowed_artifact(self) -> None:
		with TemporaryDirectory() as temporary_directory:
			root = Path(temporary_directory).resolve()
			other_code = root / "other_code"
			other_code.mkdir()
			other_artifact = other_code / export.ARTIFACT_RELATIVE_PATH.name
			other_artifact.write_bytes(b"unrelated game source\n")
			alias = root / export.ARTIFACT_RELATIVE_PATH.parent
			alias.parent.mkdir(parents=True)
			if os.name == "nt":
				subprocess.run(
					["cmd.exe", "/d", "/c", "mklink", "/J", str(alias), str(other_code)],
					check=True, capture_output=True, text=True, timeout=10,
				)
			else:
				alias.symlink_to(other_code, target_is_directory=True)
			try:
				with self.assertRaisesRegex(ValueError, "canonical"):
					export._resolve_child(root, export.ARTIFACT_RELATIVE_PATH)
				self.assertEqual(other_artifact.read_bytes(), b"unrelated game source\n")
			finally:
				if os.name == "nt":
					alias.rmdir()
				else:
					alias.unlink()

	def test_prepare_refuses_truncated_tool_status(self) -> None:
		with TemporaryDirectory() as temp:
			tool, game, stages = self.make_prepared_pair(Path(temp))
			status = RepositoryStatus('main', None, 0, 0, True, (), (), 1)
			with patch('tools.lore_editor.export.repository_status', return_value=status), self.assertRaisesRegex(ValueError, 'truncated'):
				prepare_export(tool, game, stages)
			self.assertFalse(stages.exists())

	def test_apply_rolls_back_a_write_that_fails_verification(self) -> None:
		with TemporaryDirectory() as temp:
			tool, game, stages = self.make_prepared_pair(Path(temp))
			prepared = prepare_export(tool, game, stages)
			artifact = game / export.ARTIFACT_RELATIVE_PATH
			before = artifact.read_bytes()
			with patch('tools.lore_editor.export._atomic_write', side_effect=lambda path, content: path.write_bytes(b'corrupt')), self.assertRaisesRegex(OSError, 'verification'):
				apply_export(prepared.directory, game)
			self.assertEqual(artifact.read_bytes(), before)

	def make_git_repo(self, path: Path) -> None:
		path.mkdir(parents=True)
		run_git(path, "init", "--initial-branch=main")
		run_git(path, "config", "user.name", "Lore Writer")
		run_git(path, "config", "user.email", "writer@example.invalid")

	def make_prepared_pair(self, root: Path, *, with_module: bool = True) -> tuple[Path, Path, Path]:
		tool_root = root / "tool"
		game_root = root / "game"
		stage_root = root / "stages"
		self.make_git_repo(tool_root)
		self.make_git_repo(game_root)
		seed_targets(tool_root, [])
		(game_root / "tgstation.dme").write_text("", encoding="utf-8")
		if with_module:
			artifact = game_root / "modular_aphelion/modules/lore_overhaul/code/generated_lore_overrides.dm"
			artifact.parent.mkdir(parents=True)
			artifact.write_text("old\n", encoding="utf-8")
		run_git(tool_root, "add", "--all")
		run_git(tool_root, "commit", "-m", "Tool source")
		run_git(game_root, "add", "--all")
		run_git(game_root, "commit", "-m", "Game source")
		self.install_catalog_fixture(tool_root, game_root)
		return tool_root, game_root, stage_root

	def install_catalog_fixture(self, tool_root: Path, game_root: Path) -> None:
		activate_catalog_targets(tool_root, read_current_targets(tool_root), source_game_revision=repository_revision(game_root), source_provenance="release-seed")

	def test_prepare_export_is_read_only_for_game_checkout_and_apply_is_atomic(self) -> None:
		with TemporaryDirectory() as temporary_directory:
			root = Path(temporary_directory)
			tool_root = root / "tool"
			game_root = root / "game"
			stage_root = root / "stages"
			self.make_git_repo(tool_root)
			self.make_git_repo(game_root)
			seed_targets(tool_root, [RADIO_TARGET])
			seed_override(tool_root, "lore", {
				"id": "lore.radio",
				"type_path": "/obj/item/radio",
				"name": "Updated radio",
			})
			(game_root / "tgstation.dme").write_text("", encoding="utf-8")
			artifact = game_root / "modular_aphelion/modules/lore_overhaul/code/generated_lore_overrides.dm"
			artifact.parent.mkdir(parents=True)
			artifact.write_text("old artifact\n", encoding="utf-8")
			run_git(tool_root, "add", "--all")
			run_git(tool_root, "commit", "-m", "Tool source")
			run_git(game_root, "add", "--all")
			run_git(game_root, "commit", "-m", "Game source")
			self.install_catalog_fixture(tool_root, game_root)
			before = artifact.read_bytes()

			prepared = prepare_export(tool_root, game_root, stage_root)

			self.assertEqual(before, artifact.read_bytes())
			self.assertTrue((prepared.directory / "manifest.json").is_file())
			self.assertTrue(prepared.artifact_path.is_file())
			self.assertEqual(
				prepared.manifest.content_revision,
				scan_canonical_records(tool_root).content_revision,
			)

			apply_export(prepared.directory, game_root)

			self.assertNotEqual(before, artifact.read_bytes())
			self.assertIn('name = "Updated radio"', artifact.read_text(encoding="utf-8"))

	def test_prepare_export_requires_authored_records_to_be_committed(self) -> None:
		with TemporaryDirectory() as temporary_directory:
			root = Path(temporary_directory)
			tool_root, game_root, stage_root = self.make_prepared_pair(root)
			atomic_write_record(record_path(tool_root, "group", "items"), {
				"id": "items",
				"label": "Items",
				"color": "#9614d0",
				"keywords": [],
				"type_path_prefixes": ["/obj/item"],
			})

			with self.assertRaisesRegex(ValueError, "Commit the selected records"):
				prepare_export(tool_root, game_root, stage_root)

			self.assertFalse(stage_root.exists())

	def test_apply_export_refuses_when_game_artifact_changed(self) -> None:
		with TemporaryDirectory() as temporary_directory:
			root = Path(temporary_directory)
			tool_root = root / "tool"
			game_root = root / "game"
			self.make_git_repo(tool_root)
			self.make_git_repo(game_root)
			seed_targets(tool_root, [])
			(game_root / "tgstation.dme").write_text("", encoding="utf-8")
			artifact = game_root / "modular_aphelion/modules/lore_overhaul/code/generated_lore_overrides.dm"
			artifact.parent.mkdir(parents=True)
			artifact.write_text("old\n", encoding="utf-8")
			run_git(tool_root, "add", "--all")
			run_git(tool_root, "commit", "-m", "Tool source")
			run_git(game_root, "add", "--all")
			run_git(game_root, "commit", "-m", "Game source")
			self.install_catalog_fixture(tool_root, game_root)

			prepared = prepare_export(tool_root, game_root, root / "stages")
			artifact.write_text("unexpected change\n", encoding="utf-8")

			with self.assertRaises(ValueError):
				apply_export(prepared.directory, game_root)
			self.assertEqual("unexpected change\n", artifact.read_text(encoding="utf-8"))

	def test_apply_export_refuses_when_game_revision_changed(self) -> None:
		with TemporaryDirectory() as temporary_directory:
			root = Path(temporary_directory)
			tool_root, game_root, stage_root = self.make_prepared_pair(root)
			artifact = game_root / "modular_aphelion/modules/lore_overhaul/code/generated_lore_overrides.dm"

			prepared = prepare_export(tool_root, game_root, stage_root)

			(game_root / "unrelated.txt").write_text("new commit\n", encoding="utf-8")
			run_git(game_root, "add", "--all")
			run_git(game_root, "commit", "-m", "Unrelated game change")
			before = artifact.read_bytes()

			with self.assertRaisesRegex(ValueError, "revision changed"):
				apply_export(prepared.directory, game_root)
			self.assertEqual(before, artifact.read_bytes())

	def test_apply_export_refuses_when_game_checkout_is_dirty(self) -> None:
		with TemporaryDirectory() as temporary_directory:
			root = Path(temporary_directory)
			tool_root, game_root, stage_root = self.make_prepared_pair(root)
			artifact = game_root / "modular_aphelion/modules/lore_overhaul/code/generated_lore_overrides.dm"

			prepared = prepare_export(tool_root, game_root, stage_root)

			(game_root / "uncommitted.txt").write_text("pending\n", encoding="utf-8")
			before = artifact.read_bytes()

			with self.assertRaisesRegex(ValueError, "uncommitted changes"):
				apply_export(prepared.directory, game_root)
			self.assertEqual(before, artifact.read_bytes())

	def test_apply_export_refuses_when_git_status_is_truncated(self) -> None:
		with TemporaryDirectory() as temporary_directory:
			root = Path(temporary_directory)
			tool_root, game_root, stage_root = self.make_prepared_pair(root)
			artifact = game_root / "modular_aphelion/modules/lore_overhaul/code/generated_lore_overrides.dm"
			prepared = prepare_export(tool_root, game_root, stage_root)
			status = RepositoryStatus(
				branch="main",
				upstream=None,
				ahead=0,
				behind=0,
				dirty=False,
				changed_files=("omitted-1.txt",),
				conflict_files=(),
				truncated_change_count=1,
			)
			before = artifact.read_bytes()

			with patch.object(export, "repository_status", return_value=status), self.assertRaises(ValueError) as raised:
				apply_export(prepared.directory, game_root)

			self.assertIn("truncated", str(raised.exception).lower())
			self.assertEqual(before, artifact.read_bytes())

	def test_apply_export_has_no_dirty_checkout_override(self) -> None:
		with TemporaryDirectory() as temporary_directory:
			root = Path(temporary_directory)
			tool_root, game_root, stage_root = self.make_prepared_pair(root)
			artifact = game_root / "modular_aphelion/modules/lore_overhaul/code/generated_lore_overrides.dm"

			prepared = prepare_export(tool_root, game_root, stage_root)

			(game_root / "uncommitted.txt").write_text("pending\n", encoding="utf-8")
			before = artifact.read_bytes()

			with self.assertRaises(TypeError):
				apply_export(prepared.directory, game_root, allow_dirty=True)

			self.assertEqual(before, artifact.read_bytes())

	def test_apply_export_refuses_when_game_module_is_missing(self) -> None:
		with TemporaryDirectory() as temporary_directory:
			root = Path(temporary_directory)
			tool_root, game_root, stage_root = self.make_prepared_pair(root, with_module=False)

			prepared = prepare_export(tool_root, game_root, stage_root)

			with self.assertRaisesRegex(ValueError, "module is missing"):
				apply_export(prepared.directory, game_root)

	def test_prepare_export_removes_partial_stage_directory_on_failure(self) -> None:
		with TemporaryDirectory() as temporary_directory:
			root = Path(temporary_directory)
			tool_root, game_root, stage_root = self.make_prepared_pair(root)

			original_atomic_write = export._atomic_write
			calls = {"count": 0}

			def flaky_atomic_write(path: Path, content: bytes) -> None:
				calls["count"] += 1
				if calls["count"] == 2:
					raise OSError("simulated disk failure")
				original_atomic_write(path, content)

			with (
				patch.object(export, "_atomic_write", side_effect=flaky_atomic_write),
				self.assertRaises(OSError),
			):
				prepare_export(tool_root, game_root, stage_root)

			self.assertEqual([], list(stage_root.glob("*")) if stage_root.is_dir() else [])

	def test_prepare_export_rejects_game_repository_missing_marker_file(self) -> None:
		with TemporaryDirectory() as temporary_directory:
			root = Path(temporary_directory)
			tool_root = root / "tool"
			game_root = root / "game"
			self.make_git_repo(tool_root)
			self.make_git_repo(game_root)
			seed_targets(tool_root, [])
			run_git(tool_root, "add", "--all")
			run_git(tool_root, "commit", "-m", "Tool source")

			with self.assertRaisesRegex(ValueError, "does not look like a Meridian-Rift checkout"):
				prepare_export(tool_root, game_root, root / "stages")

	def test_apply_export_rejects_game_repository_missing_marker_file(self) -> None:
		with TemporaryDirectory() as temporary_directory:
			root = Path(temporary_directory)
			tool_root, game_root, stage_root = self.make_prepared_pair(root)
			prepared = prepare_export(tool_root, game_root, stage_root)
			(game_root / "tgstation.dme").unlink()

			with self.assertRaisesRegex(ValueError, "does not look like a Meridian-Rift checkout"):
				apply_export(prepared.directory, game_root)


if __name__ == "__main__":
	unittest.main()

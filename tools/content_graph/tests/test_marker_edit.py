from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.content_graph.marker_edit import apply_marker_label_edit
from webapp.git_adapter import RepositoryStatus


def run_git(repo_root: Path, *arguments: str) -> None:
	subprocess.run(["git", "-C", str(repo_root), *arguments], check=True, capture_output=True, text=True)


def make_repo(repo_root: Path) -> None:
	repo_root.mkdir(parents=True)
	run_git(repo_root, "init", "--initial-branch=main")
	run_git(repo_root, "config", "user.name", "Writer")
	run_git(repo_root, "config", "user.email", "writer@example.invalid")
	core_file = repo_root / "code" / "modules" / "other" / "other.dm"
	core_file.parent.mkdir(parents=True)
	core_file.write_text(
		"/obj/item/other\n"
		"\t// NOVA EDIT ADDITION - some future module\n",
		encoding="utf-8",
	)
	(repo_root / 'tgstation.dme').write_text('// test game', encoding='utf-8')
	run_git(repo_root, "add", "--all")
	run_git(repo_root, "commit", "-m", "Initial")


class ApplyMarkerLabelEditTests(unittest.TestCase):
	def test_http_prepare_requires_separate_apply_and_cannot_be_replayed(self) -> None:
		from webapp.api import create_app
		from webapp.tests.http_client import TestClient
		with tempfile.TemporaryDirectory() as temp_dir:
			root = Path(temp_dir) / 'game'
			make_repo(root)
			path = root / 'code/modules/other/other.dm'
			before = path.read_bytes()
			client = TestClient(create_app(Path(temp_dir) / 'tool', root))
			try:
				prepared = client.post('/api/graph/markers/edit', json={'core_file': 'code/modules/other/other.dm', 'line_number': 2, 'expected_line': '\t// NOVA EDIT ADDITION - some future module', 'new_label': 'shuttle_toggle'})
				self.assertEqual(prepared.status_code, 200, prepared.text)
				self.assertEqual(path.read_bytes(), before)
				payload = {'stage_id': prepared.json()['stage_id']}
				applied = client.post('/api/graph/markers/apply', json=payload)
				self.assertEqual(applied.status_code, 200, applied.text)
				self.assertIn('code/modules/other/other.dm', applied.json()['sha256'])
				self.assertEqual(client.post('/api/graph/markers/apply', json=payload).status_code, 400)
			finally:
				client.close()

	def test_shared_change_set_rolls_back_all_files_on_partial_failure(self) -> None:
		from webapp.game_changes import GameChangeSetService
		from webapp.json_storage import atomic_write
		with tempfile.TemporaryDirectory() as temp_dir:
			root = Path(temp_dir) / 'game'
			make_repo(root)
			paths = ('tgstation.dme', 'code/modules/other/other.dm')
			before = {path: (root / path).read_bytes() for path in paths}
			service = GameChangeSetService(root)
			stage = service.prepare({path: (content, content + b'// changed\n') for path, content in before.items()}, allowed_paths=frozenset(paths))
			def fail_second(path: Path, content: bytes) -> None:
				if path.name == 'other.dm':
					raise OSError('fixture write failure')
				atomic_write(path, content)
			with patch('webapp.game_changes.atomic_write', side_effect=fail_second), self.assertRaises(OSError):
				service.apply(stage.stage_id)
			self.assertEqual({path: (root / path).read_bytes() for path in paths}, before)

	def test_label_cannot_inject_source_lines_or_close_a_comment(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			root = Path(temp_dir) / 'game'
			make_repo(root)
			for label in ('label\n/obj/injected', 'label */ /obj/injected', 'label\0'):
				with self.subTest(label=label), self.assertRaisesRegex(ValueError, 'single-line'):
					apply_marker_label_edit(root, 'code/modules/other/other.dm', 2, '\t// NOVA EDIT ADDITION - some future module', label)

	def test_preparation_preserves_bytes_and_apply_refuses_later_changes(self) -> None:
		from tools.content_graph.marker_edit import prepare_marker_label_edit
		from webapp.game_changes import GameChangeSetService
		with tempfile.TemporaryDirectory() as temp_dir:
			root = Path(temp_dir) / 'game'
			make_repo(root)
			path = root / 'code/modules/other/other.dm'
			before = path.read_bytes()
			service = GameChangeSetService(root)
			stage = prepare_marker_label_edit(service, 'code/modules/other/other.dm', 2, '\t// NOVA EDIT ADDITION - some future module', 'shuttle_toggle')
			self.assertEqual(path.read_bytes(), before)
			self.assertIn('shuttle_toggle', stage.preview)
			path.write_bytes(before + b'// another edit\n')
			with self.assertRaisesRegex(ValueError, 'clean'):
				service.apply(stage.stage_id)
			self.assertEqual(path.read_bytes(), before + b'// another edit\n')

	def test_apply_preserves_crlf_and_returns_receipt(self) -> None:
		from tools.content_graph.marker_edit import prepare_marker_label_edit
		from webapp.game_changes import GameChangeSetService
		with tempfile.TemporaryDirectory() as temp_dir:
			root = Path(temp_dir) / 'game'
			make_repo(root)
			path = root / 'code/modules/other/other.dm'
			run_git(root, 'config', 'core.autocrlf', 'false')
			path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
			run_git(root, 'add', '--all')
			run_git(root, 'commit', '--allow-empty', '-m', 'CRLF fixture')
			service = GameChangeSetService(root)
			stage = prepare_marker_label_edit(service, 'code/modules/other/other.dm', 2, '\t// NOVA EDIT ADDITION - some future module', 'shuttle_toggle')
			receipt = service.apply(stage.stage_id)
			self.assertEqual(receipt['paths'], ['code/modules/other/other.dm'])
			self.assertEqual(path.read_bytes(), b'/obj/item/other\r\n\t// NOVA EDIT ADDITION - shuttle_toggle\r\n')

	def test_rewrites_the_marker_line_in_place(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			game_root = Path(temp_dir) / "game"
			make_repo(game_root)
			core_file = game_root / "code" / "modules" / "other" / "other.dm"

			apply_marker_label_edit(
				game_root,
				"code/modules/other/other.dm",
				2,
				"\t// NOVA EDIT ADDITION - some future module",
				"shuttle_toggle",
			)

			content = core_file.read_text(encoding="utf-8")
			self.assertIn("\t// NOVA EDIT ADDITION - shuttle_toggle\n", content)
			self.assertIn("/obj/item/other\n", content)

	def test_refuses_when_the_line_no_longer_matches_expected_line(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			game_root = Path(temp_dir) / "game"
			make_repo(game_root)

			with self.assertRaisesRegex(ValueError, "changed since this marker was loaded"):
				apply_marker_label_edit(
					game_root,
					"code/modules/other/other.dm",
					2,
					"\t// NOVA EDIT ADDITION - a stale expectation",
					"shuttle_toggle",
				)

	def test_refuses_a_line_number_beyond_the_end_of_the_file(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			game_root = Path(temp_dir) / "game"
			make_repo(game_root)

			with self.assertRaises(ValueError):
				apply_marker_label_edit(game_root, "code/modules/other/other.dm", 999, "anything", "shuttle_toggle")

	def test_refuses_an_empty_new_label(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			game_root = Path(temp_dir) / "game"
			make_repo(game_root)

			with self.assertRaises(ValueError):
				apply_marker_label_edit(
					game_root,
					"code/modules/other/other.dm",
					2,
					"\t// NOVA EDIT ADDITION - some future module",
					"   ",
				)

	def test_refuses_when_the_game_checkout_has_git_conflicts(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			game_root = Path(temp_dir) / "game"
			make_repo(game_root)
			conflicted_status = RepositoryStatus(
				branch="main",
				upstream=None,
				ahead=0,
				behind=0,
				dirty=True,
				changed_files=(),
				conflict_files=("code/modules/other/other.dm",),
			)

			with (
				patch("webapp.game_changes.repository_status", return_value=conflicted_status),
				self.assertRaisesRegex(ValueError, "unresolved Git conflicts"),
			):
				apply_marker_label_edit(
					game_root,
					"code/modules/other/other.dm",
					2,
					"\t// NOVA EDIT ADDITION - some future module",
					"shuttle_toggle",
				)

	def test_refuses_a_line_that_is_not_a_recognizable_marker(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			game_root = Path(temp_dir) / "game"
			make_repo(game_root)

			with self.assertRaises(ValueError):
				apply_marker_label_edit(game_root, "code/modules/other/other.dm", 1, "/obj/item/other", "shuttle_toggle")


if __name__ == "__main__":
	unittest.main()

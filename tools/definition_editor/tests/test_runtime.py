from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.definition_editor.catalog import Analyzer, verify_inputs
from tools.definition_editor.process import Cancelled, RunContext
from tools.definition_editor.tests.test_authoring import FILE, SOURCE, catalog


class AnalyzerAndProcessTests(unittest.TestCase):
	def test_native_world_log_is_captured_with_a_size_limit(self) -> None:
		from tools.definition_editor.models import EditorRun, PreviewRequest
		from tools.definition_editor.preview import run_preview
		for oversized in (False, True):
			with self.subTest(oversized=oversized), tempfile.TemporaryDirectory() as temporary:
				root = Path(temporary)
				context = RunContext(root / 'run', threading.Event(), max_log_bytes=4096)
				payload = b'x' * 8192 if oversized else b'Native client admitted.\n'
				def command(arguments: list[str], cwd: Path, *, root: Path = root, payload: bytes = payload, context: RunContext = context, **kwargs) -> None:
					(root / 'data/content_tools/daemon.log').write_bytes(payload)
					(root / 'data/content_tools/result.json').write_text(json.dumps({'schema_version': 1, 'status': 'ready'}), encoding='utf-8')
					context.cancel.wait(5)
					context.check()
				request = PreviewRequest(kind='outfit', id='example', record_hash='a' * 64, type_path='/datum/outfit/example', mode='render')
				state = EditorRun(id='example', operation='render', status='running')
				with patch('tools.definition_editor.preview.build_candidate'), patch('tools.definition_editor.preview.byond_binary', side_effect=Path), patch.object(context, 'command', side_effect=command) as launched:
					if oversized:
						with self.assertRaisesRegex(ValueError, 'log.*limit'):
							run_preview(root, request, context, state, lambda: None)
					else:
						run_preview(root, request, context, state, lambda: None)
					self.assertEqual(launched.call_args.args[0][-2:], ['-log', 'data/content_tools/daemon.log'])
				log = (context.directory / 'run.log').read_bytes()
				self.assertLessEqual(len(log), context.max_log_bytes)
				if not oversized:
					self.assertIn(payload, log)

	def test_explicit_preview_stop_remains_cancelled_when_daemon_exits_first(self) -> None:
		from tools.definition_editor.models import PreviewRequest
		from tools.definition_editor.preview import run_preview
		from tools.definition_editor.service import EditorService
		from webapp.game_changes import GameChangeSetService
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			service = EditorService(root, root, GameChangeSetService(root))
			server_threads = []
			def command(context: RunContext, arguments: list[str], cwd: Path, **kwargs) -> None:
				context.check()
				server_threads.append(threading.current_thread())
				(root / 'data/content_tools/result.json').write_text(json.dumps({'schema_version': 1, 'status': 'ready'}), encoding='utf-8')
				if not context.cancel.wait(5):
					raise TimeoutError('Test did not request stop')
				context.check()
			def action(state, context: RunContext) -> None:
				def stop_after_ready() -> None:
					context.cancel.set()
					server_threads[0].join(timeout=5)
					self.assertFalse(server_threads[0].is_alive())
				request = PreviewRequest(kind='job', id='example', record_hash='a' * 64, type_path='/datum/job/assistant', mode='interactive')
				run_preview(root, request, context, state, stop_after_ready)
			try:
				with patch('tools.definition_editor.preview.build_candidate'), patch('tools.definition_editor.preview.byond_binary', side_effect=Path), patch.object(RunContext, 'command', command):
					service._start('interactive', action, 'a' * 64)
					deadline = time.monotonic() + 10
					while service._busy and time.monotonic() < deadline:
						time.sleep(.01)
					self.assertFalse(service._busy)
				state = service.runs()[0]
				self.assertEqual(state.status, 'cancelled', state.message)
				self.assertEqual(state.diagnostics, [])
			finally:
				service.shutdown()

	def test_daemon_resolution_never_selects_unrelated_coreutils_dd(self) -> None:
		from tools.definition_editor.preview import byond_binary
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			wrong = root / 'git/dd.exe'
			wrong.parent.mkdir()
			wrong.write_bytes(b'coreutils dd')
			daemon = root / 'BYOND/bin/DreamDaemon.exe'
			daemon.parent.mkdir(parents=True)
			daemon.write_bytes(b'BYOND daemon')
			with patch.dict(os.environ, {'ProgramFiles(x86)': str(root)}, clear=True), patch('tools.definition_editor.preview.shutil.which', side_effect=lambda name: str(wrong) if name == 'dd.exe' else None) as which:
				self.assertEqual(byond_binary('dd.exe'), daemon)
				self.assertNotIn(('dd.exe',), [call.args for call in which.call_args_list])

	def test_verified_inputs_cannot_copy_git_administration(self) -> None:
		from tools.content_graph.tests.test_marker_edit import make_repo
		from tools.definition_editor.models import SourceInput
		from tools.definition_editor.preview import copy_source
		with tempfile.TemporaryDirectory() as temporary:
			root, destination = Path(temporary) / 'game', Path(temporary) / 'copy'
			make_repo(root)
			(root / '.git/included.dm').write_bytes(b'/datum/private')
			item = SourceInput(path='.git/included.dm', sha256=hashlib.sha256(b'/datum/private').hexdigest())
			with self.assertRaisesRegex(ValueError, 'Git administration'):
				copy_source(root, destination, RunContext(destination, threading.Event()), [item])
			self.assertFalse((destination / '.git').exists())

	def test_analysis_failure_and_cancellation_release_private_source_but_keep_status(self) -> None:
		from tools.content_graph.tests.test_marker_edit import make_repo
		from tools.definition_editor.models import DraftAction
		from tools.definition_editor.service import EditorService
		from tools.definition_editor.tests.test_authoring import draft
		from webapp.game_changes import GameChangeSetService
		for outcome in ('analyzed', 'analysis-failed', 'compile-failed', 'cancelled'):
			with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as temporary:
				root, game = Path(temporary) / 'app', Path(temporary) / 'game'
				make_repo(game)
				(game / FILE).parent.mkdir(parents=True)
				(game / FILE).write_bytes(SOURCE)
				service = EditorService(root, game, GameChangeSetService(game))
				saved = service.drafts.save(draft(), expected_hash=None)
				def export(source: Path, output: Path, context: RunContext, outcome: str = outcome):
					output.write_bytes(b'transient full analyzer payload')
					if outcome == 'analysis-failed':
						raise ValueError('invalid draft')
					if outcome == 'cancelled':
						raise Cancelled()
					return catalog()
				try:
					with patch.object(service.catalogs, 'verify', return_value=catalog()), patch.object(service.analyzer, 'export', side_effect=export), patch('tools.definition_editor.service.build_candidate', side_effect=ValueError('compiler failed')):
						run = service.validate(DraftAction(kind='outfit', id=saved.draft.id, record_hash=saved.record_hash), compile_game=outcome == 'compile-failed')
						deadline = time.monotonic() + 10
						while service._busy and time.monotonic() < deadline:
							time.sleep(.01)
						self.assertFalse(service._busy)
					self.assertEqual(service.runs()[0].status, {'analyzed': 'ready', 'cancelled': 'cancelled'}.get(outcome, 'failed'))
					self.assertEqual(list((root / 'webapp/store/dm').iterdir()), [])
					self.assertTrue((service.cache / 'runs' / run.id / 'status.json').exists())
					self.assertFalse((service.cache / 'runs' / run.id / 'candidate.json').exists())
				finally:
					service.shutdown()

	def test_validated_source_retention_is_bounded_and_shutdown_preserves_unowned_files(self) -> None:
		from tools.definition_editor.models import EditorRun
		from tools.definition_editor.service import EditorService, ValidatedCandidate
		from webapp.game_changes import GameChangeSetService
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			service = EditorService(root, root, GameChangeSetService(root))
			unowned = root / 'webapp/store/dm/external'
			unowned.mkdir(parents=True)
			(unowned / 'keep').write_bytes(b'unrelated')
			sources = []
			try:
				for number in range(4):
					run = EditorRun(id=str(number), operation='validate', status='running')
					with service._source_workspace(run) as source:
						(source / 'owned').write_bytes(b'candidate')
						service._retain_candidate(ValidatedCandidate(str(number), 'catalog', 'revision', {}, source, {'draft_id': 'same' if number < 2 else str(number), 'draft_kind': 'outfit'}, {}), run)
						sources.append(source)
					self.assertTrue(source.is_dir())
				self.assertFalse(sources[0].exists(), 'Superseded same-draft source remained')
				self.assertEqual(sum(source.exists() for source in sources), 2)
			finally:
				service.shutdown()
			self.assertFalse(any(source.exists() for source in sources))
			self.assertEqual((unowned / 'keep').read_bytes(), b'unrelated')

	def test_private_snapshot_copies_and_binds_referenced_ignored_resources(self) -> None:
		from tools.content_graph.tests.test_marker_edit import make_repo
		from tools.definition_editor.preview import copy_source, source_fingerprint
		with tempfile.TemporaryDirectory() as temporary:
			root, destination = Path(temporary) / 'game', Path(temporary) / 'copy'
			make_repo(root)
			(root / '.gitignore').write_text('icon/\nconfig/\n', encoding='utf-8')
			(root / 'icon').mkdir()
			(root / 'icon/used.dmi').write_bytes(b'compiled icon')
			(root / 'icon/unreferenced.dmi').write_bytes(b'not an input')
			(root / 'config').mkdir()
			(root / 'config/private.png').write_bytes(b'private configuration')
			(root / 'example.dm').write_text("/obj/item/example\n\ticon = 'icon/used.dmi'\n// 'config/private.png'\n// 'subdir/../config/private.png'\n", encoding='utf-8')
			before = source_fingerprint(root, [])
			self.assertEqual(copy_source(root, destination, RunContext(destination, threading.Event()), []), before)
			self.assertEqual((destination / 'icon/used.dmi').read_bytes(), b'compiled icon')
			self.assertFalse((destination / 'icon/unreferenced.dmi').exists())
			self.assertFalse((destination / 'config/private.png').exists())
			(root / 'icon/used.dmi').write_bytes(b'changed icon')
			self.assertNotEqual(source_fingerprint(root, []), before)

	def test_private_snapshot_includes_resources_introduced_by_the_draft(self) -> None:
		from tools.content_graph.tests.test_marker_edit import make_repo
		from tools.definition_editor.preview import copy_source, source_fingerprint
		with tempfile.TemporaryDirectory() as temporary:
			root, destination = Path(temporary) / 'game', Path(temporary) / 'copy'
			make_repo(root)
			(root / '.gitignore').write_text('draft.dmi\n', encoding='utf-8')
			(root / 'draft.dmi').write_bytes(b'new draft asset')
			proposed = [b"/obj/item/example\n\ticon = 'draft.dmi'\n"]
			before = source_fingerprint(root, [], proposed)
			self.assertEqual(copy_source(root, destination, RunContext(destination, threading.Event()), [], proposed), before)
			self.assertTrue((destination / 'draft.dmi').exists())
			(root / 'draft.dmi').write_bytes(b'changed')
			self.assertNotEqual(source_fingerprint(root, [], proposed), before)

	def test_private_snapshot_rejects_resource_paths_outside_the_checkout(self) -> None:
		from tools.content_graph.tests.test_marker_edit import make_repo
		from tools.definition_editor.preview import source_fingerprint
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary) / 'game'
			make_repo(root)
			(root / 'example.dm').write_text("/obj/item/example\n\ticon = '../private.dmi'\n", encoding='utf-8')
			with self.assertRaisesRegex(ValueError, 'escapes root'):
				source_fingerprint(root, [])

	def test_package_discovery_excludes_private_game_workspaces(self) -> None:
		import tomllib

		from setuptools.config.expand import find_packages
		config = tomllib.loads((Path(__file__).resolve().parents[3] / 'pyproject.toml').read_text(encoding='utf-8'))['tool']['setuptools']['packages']['find']
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			for relative in ('webapp/api', 'tools/definition_editor', 'webapp/store/dm/abcdefgh/scripts', 'webapp/store/definition-editor/runs/abcdef/source/scripts'):
				path = root / relative / 'example.py'
				path.parent.mkdir(parents=True, exist_ok=True)
				path.write_text('private = True', encoding='utf-8')
			packages = find_packages(where=[str(root)], include=config['include'], exclude=config.get('exclude', []))
			self.assertIn('webapp.api', packages)
			self.assertIn('tools.definition_editor', packages)
			self.assertFalse(any(name.startswith(('webapp.store.dm', 'webapp.store.definition-editor')) for name in packages), packages)

	def test_private_native_source_uses_short_unique_store_paths(self) -> None:
		from tools.definition_editor.preview import create_source_directory
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			first, second = create_source_directory(root), create_source_directory(root)
			self.assertEqual(first.parent, root / 'webapp/store/dm')
			self.assertNotEqual(first, second)
			self.assertLessEqual(len(first.name), 12)
			self.assertTrue(first.is_dir() and second.is_dir())

	@unittest.skipUnless(os.name == 'nt', 'BYOND Windows path limit')
	def test_build_rejects_long_native_paths_before_starting_commands(self) -> None:
		from tools.definition_editor.preview import build_candidate
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			(root / 'tools/build').mkdir(parents=True)
			(root / 'tools/build/build.bat').write_text('fixture', encoding='utf-8')
			long = root / ('a' * 100) / ('b' * 100) / ('c' * 60 + '.dm')
			long.parent.mkdir(parents=True)
			long.write_text('/datum/example', encoding='utf-8')
			context = RunContext(root, threading.Event())
			with patch.object(context, 'command') as command, patch('tools.definition_editor.preview.byond_binary', return_value=root / 'dm.exe'):
				with self.assertRaisesRegex(ValueError, 'BYOND.*260.*shorter'):
					build_candidate(root, context)
				command.assert_not_called()

	def test_status_observation_detects_source_changes_without_authorizing_mutation(self) -> None:
		from tools.definition_editor.catalog import CatalogStore
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			(root / FILE).parent.mkdir(parents=True)
			(root / FILE).write_bytes(SOURCE)
			store = CatalogStore(root, root)
			with patch.object(store, 'read', return_value=('fixture', catalog(), 'revision')), patch('tools.definition_editor.catalog.repository_revision', return_value='revision'):
				store.verify('fixture')
				with patch('tools.definition_editor.catalog.verify_inputs', side_effect=AssertionError('status rehashed every source')):
					store.observe('fixture')
					(root / FILE).write_bytes(SOURCE + b'changed')
					with self.assertRaisesRegex(ValueError, 'Source files changed'):
						store.observe('fixture')
				with self.assertRaisesRegex(ValueError, 'changed|stale'):
					store.verify('fixture')

	def test_compilation_binding_rejects_a_changed_asset_even_when_catalog_source_matches(self) -> None:
		from tools.content_graph.tests.test_marker_edit import make_repo
		from tools.definition_editor.preview import source_fingerprint
		from tools.definition_editor.service import EditorService, ValidatedCandidate
		from webapp.game_changes import GameChangeSetService
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary) / 'game'
			make_repo(root)
			(root / 'asset.dmi').write_bytes(b'compiled version')
			base = catalog().model_copy(update={'input_files': []})
			candidate = ValidatedCandidate('record', 'catalog', 'revision', {}, root, {'source_sha256': source_fingerprint(root, [])}, {})
			service = EditorService(root, root, GameChangeSetService(root))
			try:
				(root / 'asset.dmi').write_bytes(b'restored different version')
				with self.assertRaisesRegex(ValueError, 'build inputs differ'):
					service._verify_compilation(candidate, base)
			finally:
				service.shutdown()

	def test_private_candidate_changes_invalidate_native_preview(self) -> None:
		from tools.definition_editor.service import EditorService
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			(root / 'source.dm').write_bytes(b'changed')
			with self.assertRaisesRegex(ValueError, 'Private candidate source changed'):
				EditorService._verify_private_inputs(root, {'source.dm': hashlib.sha256(b'compiled').hexdigest()})

	def test_command_waits_for_ownership_and_running_cancellation_stops_it(self) -> None:
		from webapp.process_tree import KillOnCloseJob
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			cancel = threading.Event()
			original_assign = KillOnCloseJob.assign
			def delayed_assign(owner: KillOnCloseJob, pid: int) -> None:
				time.sleep(.2)
				self.assertFalse((root / 'started').exists(), 'Native command started before process ownership was assigned.')
				original_assign(owner, pid)
			timer = threading.Timer(1, cancel.set)
			timer.start()
			try:
				with patch.object(KillOnCloseJob, 'assign', delayed_assign), self.assertRaises(Cancelled):
					RunContext(root, cancel).command([sys.executable, '-c', 'from pathlib import Path; import time; Path("started").touch(); time.sleep(30)'], root, timeout=5)
				self.assertTrue((root / 'started').exists())
			finally:
				timer.cancel()

	@unittest.skipUnless(os.name == 'nt', 'Windows job descendant ownership')
	def test_cancellation_terminates_a_started_descendant(self) -> None:
		import ctypes
		from ctypes import wintypes
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			cancel = threading.Event()
			context = RunContext(root, cancel)
			failures: list[BaseException] = []
			def run() -> None:
				try:
					context.command([sys.executable, '-c', 'import subprocess,sys,time; from pathlib import Path; p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"]); Path("child.pid").write_text(str(p.pid)); time.sleep(30)'], root, timeout=5)
				except Cancelled:
					pass
				except BaseException as exc:
					failures.append(exc)
			thread = threading.Thread(target=run)
			thread.start()
			kernel = ctypes.WinDLL('kernel32', use_last_error=True)
			kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
			kernel.OpenProcess.restype = wintypes.HANDLE
			kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
			kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
			kernel.CloseHandle.argtypes = [wintypes.HANDLE]
			handle = None
			try:
				deadline = time.monotonic() + 4
				while not (root / 'child.pid').exists() and time.monotonic() < deadline:
					time.sleep(.05)
				self.assertTrue((root / 'child.pid').exists())
				handle = kernel.OpenProcess(0x00100001, False, int((root / 'child.pid').read_text()))
				self.assertTrue(handle)
				cancel.set()
				thread.join(timeout=5)
				self.assertFalse(thread.is_alive())
				self.assertEqual(kernel.WaitForSingleObject(handle, 2000), 0)
				self.assertFalse(failures)
			finally:
				cancel.set()
				if handle:
					kernel.TerminateProcess(handle, 1)
					kernel.CloseHandle(handle)
				thread.join(timeout=5)
	def test_snapshot_fingerprint_tracks_non_parser_assets(self) -> None:
		from tools.content_graph.tests.test_marker_edit import make_repo
		from tools.definition_editor.preview import source_fingerprint
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary) / 'game'
			make_repo(root)
			(root / 'asset.dmi').write_bytes(b'first')
			before = source_fingerprint(root, [])
			(root / 'asset.dmi').write_bytes(b'second')
			self.assertNotEqual(before, source_fingerprint(root, []))

	def test_status_write_failure_does_not_leak_busy_reservation(self) -> None:
		from unittest.mock import patch

		from tools.definition_editor.service import EditorService
		from webapp.game_changes import GameChangeSetService
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			service = EditorService(root, root, GameChangeSetService(root))
			try:
				with patch.object(service, '_persist', side_effect=OSError('disk full')), self.assertRaises(OSError):
					service.index()
				self.assertFalse(service._busy)
			finally:
				service.shutdown()
	def test_analyzer_pin_rejects_replaced_executable(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			(root / 'analyzer.exe').write_bytes(b'expected')
			(root / 'analyzer.json').write_text(json.dumps({'schema_version': 1, 'file': 'analyzer.exe', 'sha256': hashlib.sha256(b'expected').hexdigest()}))
			self.assertEqual(Analyzer(root / 'analyzer.json').executable(), root / 'analyzer.exe')
			(root / 'analyzer.exe').write_bytes(b'replaced')
			with self.assertRaisesRegex(ValueError, 'checksum'):
				Analyzer(root / 'analyzer.json').executable()

	def test_every_catalog_input_hash_is_verified(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			(root / FILE).parent.mkdir(parents=True)
			(root / FILE).write_bytes(SOURCE)
			verify_inputs(root, catalog())
			(root / FILE).write_bytes(SOURCE + b'changed')
			with self.assertRaisesRegex(ValueError, 'changed|stale'):
				verify_inputs(root, catalog())

	def test_owned_command_has_bounded_output_and_checks_exit(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			context = RunContext(Path(temporary), threading.Event(), max_log_bytes=100)
			with self.assertRaisesRegex(ValueError, 'exit'):
				context.command([sys.executable, '-c', 'print("x" * 10000); raise SystemExit(3)'], Path(temporary), timeout=10)
			self.assertLessEqual(len(context.output), 100)

	def test_cancelled_command_never_starts(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			cancel = threading.Event()
			cancel.set()
			with self.assertRaises(Cancelled):
				RunContext(Path(temporary), cancel).command([sys.executable, '-c', 'print(1)'], Path(temporary), timeout=10)

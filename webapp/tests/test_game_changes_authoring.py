from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.content_graph.tests.test_marker_edit import make_repo
from webapp.game_changes import GameChangeSetService
from webapp.json_storage import atomic_write


class AuthoringGameChangesTests(unittest.TestCase):
	def test_receipt_write_failure_rolls_back_immediately(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary) / 'game'
			make_repo(root)
			service = GameChangeSetService(root)
			stage = service.prepare({'new.dm': (None, b'new')}, allowed_paths=frozenset({'new.dm'}))
			def fail_receipt(path: Path, content: bytes) -> None:
				if path.parent.name == 'receipts':
					raise OSError('receipt storage failed')
				atomic_write(path, content)
			with patch('webapp.json_storage.atomic_write', side_effect=fail_receipt), self.assertRaises(OSError):
				service.apply(stage.stage_id)
			self.assertFalse((root / 'new.dm').exists())
	def test_committed_receipt_prevents_rollback_after_cleanup_interruption(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary) / 'game'
			make_repo(root)
			service = GameChangeSetService(root)
			stage = service.prepare({'new.dm': (None, b'new')}, allowed_paths=frozenset({'new.dm'}))
			unlink = Path.unlink
			def interrupt(path: Path, *args: object, **kwargs: object) -> None:
				if path.name == 'pending.json':
					raise KeyboardInterrupt()
				unlink(path, *args, **kwargs)
			with patch.object(Path, 'unlink', interrupt), self.assertRaises(KeyboardInterrupt):
				service.apply(stage.stage_id)
			GameChangeSetService(root).recover()
			self.assertEqual((root / 'new.dm').read_bytes(), b'new')

	def test_create_file_and_preserve_existing_non_utf8_source(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary) / 'game'
			make_repo(root)
			service = GameChangeSetService(root)
			new = 'modular_aphelion/modules/content_tools/code/generated_outfits.dm'
			stage = service.prepare({new: (None, b'/datum/outfit/test\n\tname = "Test"\n')}, allowed_paths=frozenset({new}))
			self.assertFalse((root / new).exists())
			receipt = service.apply(stage.stage_id)
			self.assertEqual(receipt['paths'], [new])
			self.assertTrue((root / new).is_file())

	def test_failed_multifile_apply_removes_new_file_and_preserves_old(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary) / 'game'
			make_repo(root)
			service = GameChangeSetService(root)
			new, old = 'new.dm', 'tgstation.dme'
			before = (root / old).read_bytes()
			stage = service.prepare({new: (None, b'new'), old: (before, before + b'\nnew')}, allowed_paths=frozenset({new, old}))
			def write(path: Path, content: bytes) -> None:
				if path.name == old:
					raise OSError('simulated interruption')
				atomic_write(path, content)
			with patch('webapp.game_changes.atomic_write', side_effect=write), self.assertRaises(OSError):
				service.apply(stage.stage_id)
			self.assertFalse((root / new).exists())
			self.assertEqual((root / old).read_bytes(), before)

	def test_recover_interrupted_write_on_next_prepare(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary) / 'game'
			make_repo(root)
			service = GameChangeSetService(root)
			before = (root / 'tgstation.dme').read_bytes()
			stage = service.prepare({'tgstation.dme': (before, b'changed')}, allowed_paths=frozenset({'tgstation.dme'}))
			def interrupt(path: Path, content: bytes) -> None:
				atomic_write(path, content)
				raise KeyboardInterrupt()
			with patch('webapp.game_changes.atomic_write', side_effect=interrupt), self.assertRaises(KeyboardInterrupt):
				service.apply(stage.stage_id)
			self.assertEqual((root / 'tgstation.dme').read_bytes(), b'changed')
			restarted = GameChangeSetService(root)
			restarted.recover()
			self.assertEqual((root / 'tgstation.dme').read_bytes(), before)

	def test_recovery_refuses_to_overwrite_independent_edit(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary) / 'game'
			make_repo(root)
			service = GameChangeSetService(root)
			before = (root / 'tgstation.dme').read_bytes()
			stage = service.prepare({'tgstation.dme': (before, b'changed')}, allowed_paths=frozenset({'tgstation.dme'}))
			def interrupt(path: Path, content: bytes) -> None:
				atomic_write(path, content)
				raise KeyboardInterrupt()
			with patch('webapp.game_changes.atomic_write', side_effect=interrupt), self.assertRaises(KeyboardInterrupt):
				service.apply(stage.stage_id)
			(root / 'tgstation.dme').write_bytes(b'independent')
			with self.assertRaisesRegex(ValueError, 'recovery'):
				GameChangeSetService(root).recover()
			self.assertEqual((root / 'tgstation.dme').read_bytes(), b'independent')

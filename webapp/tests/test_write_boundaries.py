from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from tools.lore_editor.reconcile import reconcile_projection
from tools.lore_editor.records import atomic_write_record, record_path
from tools.lore_editor.tests.store_helpers import seed_targets
from tools.lore_editor.write_coordinator import repository_write_lock
from webapp.api.deps import AppContext
from webapp.api.errors import Conflict


class AuthoringBoundaryTests(unittest.TestCase):
	def test_currentness_is_rechecked_after_context_resolution(self) -> None:
		with tempfile.TemporaryDirectory() as temp:
			root = Path(temp)
			seed_targets(root, [])
			reconcile_projection(root)
			context = AppContext(root, root)
			atomic_write_record(record_path(root, 'group', 'outside'), {'id': 'outside', 'label': 'External change', 'color': '#56d4dc'})
			with self.assertRaises(Conflict), context.authoring():
				self.fail('Stale authoring was admitted')

	def test_authoring_holds_the_write_lock_until_the_operation_finishes(self) -> None:
		with tempfile.TemporaryDirectory() as temp:
			root = Path(temp)
			seed_targets(root, [])
			reconcile_projection(root)
			context = AppContext(root, root)
			entered = threading.Event()
			def writer() -> None:
				with repository_write_lock(root):
					entered.set()
			thread = threading.Thread(target=writer)
			with context.authoring():
				thread.start()
				self.assertFalse(entered.wait(0.1))
			thread.join(5)
			self.assertTrue(entered.is_set())

from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from tools.lore_editor.write_coordinator import repository_write_lock


class WriteCoordinatorTests(unittest.TestCase):
	def test_repository_write_lock_serializes_the_same_workspace(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			first_entered = threading.Event()
			release_first = threading.Event()
			second_entered = threading.Event()

			def hold_first() -> None:
				with repository_write_lock(repo_root):
					first_entered.set()
					release_first.wait(timeout=5)

			def enter_second() -> None:
				with repository_write_lock(repo_root):
					second_entered.set()

			first = threading.Thread(target=hold_first)
			second = threading.Thread(target=enter_second)
			first.start()
			self.assertTrue(first_entered.wait(timeout=5))
			second.start()
			self.assertFalse(second_entered.wait(timeout=0.1))

			release_first.set()
			first.join(timeout=5)
			second.join(timeout=5)
			self.assertTrue(second_entered.is_set())


if __name__ == "__main__":
	unittest.main()

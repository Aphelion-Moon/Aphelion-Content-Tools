from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from tools.lore_editor.write_coordinator import repository_write_lock


class WriteCoordinatorTests(unittest.TestCase):
	def test_lock_is_reentrant_and_excludes_another_process(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			root = Path(temp_dir)
			with repository_write_lock(root), repository_write_lock(root):
				child = subprocess.Popen([sys.executable, '-B', '-c',
					"from pathlib import Path; import sys; from tools.lore_editor.write_coordinator import repository_write_lock; print('ready', flush=True);\nwith repository_write_lock(Path(sys.argv[1])): print('entered', flush=True)", temp_dir], stdout=subprocess.PIPE, text=True)
				try:
					self.assertEqual(child.stdout.readline().strip(), 'ready')
					with self.assertRaises(subprocess.TimeoutExpired):
						child.wait(timeout=0.25)
				finally:
					if child.poll() is not None:
						child.stdout.close()
			try:
				output, _ = child.communicate(timeout=10)
				self.assertEqual(output.strip(), 'entered')
			finally:
				if child.poll() is None:
					child.kill()
					child.wait()

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

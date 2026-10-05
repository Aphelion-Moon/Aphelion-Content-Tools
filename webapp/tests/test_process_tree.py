from __future__ import annotations

import os
import subprocess
import sys
import unittest

from webapp import process_tree


@unittest.skipUnless(os.name == "nt", "Windows Job Objects are Windows-only.")
class WindowsProcessTreeTests(unittest.TestCase):
	def test_closing_owner_terminates_assigned_process(self) -> None:
		owner = process_tree.KillOnCloseJob()
		child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
		try:
			owner.assign(child.pid)
			owner.close()
			child.wait(timeout=5)
			self.assertIsNotNone(child.returncode)
		finally:
			owner.close()
			if child.poll() is None:
				child.kill()
				child.wait(timeout=5)


if __name__ == "__main__":
	unittest.main()

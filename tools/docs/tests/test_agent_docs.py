from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.docs.check_agent_docs import check_repository


class AgentDocumentTests(unittest.TestCase):
	def test_cross_repository_game_policy_is_rejected(self) -> None:
		with tempfile.TemporaryDirectory() as temporary_directory:
			root = Path(temporary_directory)
			(root / "AGENTS.md").write_text(
				"# Meridian Rift agent instructions\nmodular_nova/readme.md\n",
				encoding="utf-8",
			)
			errors = check_repository(root)
			self.assertIn("AGENTS.md must identify Aphelion Content Tools", errors)

	def test_broken_local_link_is_reported(self) -> None:
		with tempfile.TemporaryDirectory() as temporary_directory:
			root = Path(temporary_directory)
			(root / "AGENTS.md").write_text(
				"# Aphelion Content Tools\n[missing](missing.md)\n",
				encoding="utf-8",
			)
			errors = check_repository(root)
			self.assertTrue(any("broken local link: missing.md" in error for error in errors))

	def test_compatibility_file_rejects_game_policy(self) -> None:
		with tempfile.TemporaryDirectory() as temporary_directory:
			root = Path(temporary_directory)
			(root / ".agents").mkdir()
			(root / ".agents" / "AGENTS.md").write_text(
				"# Meridian Rift agent instructions\n",
				encoding="utf-8",
			)
			errors = check_repository(root)
			self.assertIn(
				".agents/AGENTS.md must point to the root Aphelion Content Tools policy",
				errors,
			)

	def test_ci_rejects_unbounded_python_discovery(self) -> None:
		with tempfile.TemporaryDirectory() as temporary_directory:
			root = Path(temporary_directory)
			(root / ".github" / "workflows").mkdir(parents=True)
			(root / ".github" / "workflows" / "ci.yml").write_text(
				"steps:\n  - run: python -m unittest discover\n",
				encoding="utf-8",
			)
			errors = check_repository(root)
			self.assertIn("CI must not run monolithic Python unittest discovery", errors)

	def test_checked_in_repository_is_consistent(self) -> None:
		root = Path(__file__).resolve().parents[3]
		self.assertEqual(check_repository(root), [])


if __name__ == "__main__":
	unittest.main()

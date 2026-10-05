from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from webapp.store.datasets import evaluate_compatibility
from webapp.store.snapshots import (
	ActivationReceipt,
	DatasetArtifact,
	DatasetBuild,
	DatasetDiagnostics,
	DatasetRequirement,
	DatasetSource,
	RepositoryIdentity,
	WorkspaceSnapshot,
	identify_repository,
)

GAME_REVISION = "a" * 40
LORE_REVISION = "b" * 64


def _repository(repository_id: str, revision: str) -> RepositoryIdentity:
	return RepositoryIdentity(
		repository_id=repository_id,
		remote_identity=f"https://example.invalid/{repository_id}.git",
		revision=revision,
	)


def _build(
	kind: str,
	*,
	repository: RepositoryIdentity,
	schema_version: int = 1,
	capabilities: frozenset[str] = frozenset(),
	succeeded: bool = True,
) -> DatasetBuild:
	return DatasetBuild.create(
		kind=kind,
		schema_version=schema_version,
		sources=(DatasetSource(repository=repository, file_set_sha256="c" * 64),),
		extractor_version="fixture-extractor-v1",
		indexer_version="fixture-indexer-v1",
		model_version=None,
		content_sha256="d" * 64,
		counts={"records": 3},
		diagnostics=DatasetDiagnostics(succeeded=succeeded, error_count=0 if succeeded else 1),
		created_at="2026-08-27T12:00:00+00:00",
		artifacts=(DatasetArtifact(kind="table", reference=f"tables/{kind}", sha256="e" * 64, count=3),),
		capabilities=capabilities,
	)


class WorkspaceSnapshotTests(unittest.TestCase):
	def setUp(self) -> None:
		self.game_repository = _repository("meridian-rift", GAME_REVISION)
		self.tool_repository = _repository("aphelion-content-tools", "f" * 40)
		self.requirements = (
			DatasetRequirement(kind="lore", accepted_schema_versions=(1,), required=True),
			DatasetRequirement(kind="catalog", accepted_schema_versions=(1,), required=True),
			DatasetRequirement(
				kind="graph",
				accepted_schema_versions=(1,),
				required=False,
				required_capabilities=frozenset({"module_edges"}),
			),
		)

	def test_build_and_snapshot_ids_are_deterministic(self) -> None:
		first_build = _build("catalog", repository=self.game_repository)
		second_build = _build("catalog", repository=self.game_repository)
		self.assertEqual(first_build.build_id, second_build.build_id)

		first_snapshot = WorkspaceSnapshot.create(
			datasets=(first_build,),
			requirements=(DatasetRequirement(kind="catalog", accepted_schema_versions=(1,)),),
		)
		second_snapshot = WorkspaceSnapshot.create(
			datasets=(second_build,),
			requirements=(DatasetRequirement(kind="catalog", accepted_schema_versions=(1,)),),
		)
		self.assertEqual(first_snapshot.snapshot_id, second_snapshot.snapshot_id)
		activated_snapshot = WorkspaceSnapshot.create(
			datasets=(second_build,),
			requirements=(DatasetRequirement(kind="catalog", accepted_schema_versions=(1,)),),
			activation=ActivationReceipt(
				activated_at="2026-08-27T12:01:00+00:00",
				previous_snapshot_id=None,
				manifest_sha256="1" * 64,
			),
		)
		self.assertEqual(first_snapshot.snapshot_id, activated_snapshot.snapshot_id)

	def test_repository_identity_omits_local_paths_and_remote_credentials(self) -> None:
		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir) / "private-profile" / "checkout"
			repo_root.mkdir(parents=True)
			for arguments in (
				("init", "--initial-branch=main"),
				("config", "user.name", "Fixture Author"),
				("config", "user.email", "fixture@example.invalid"),
				("remote", "add", "origin", "https://build-user:secret@example.invalid/meridian-rift.git"),
			):
				subprocess.run(["git", "-C", str(repo_root), *arguments], check=True, capture_output=True)
			(repo_root / "README.md").write_text("fixture\n", encoding="utf-8")
			subprocess.run(["git", "-C", str(repo_root), "add", "README.md"], check=True, capture_output=True)
			subprocess.run(["git", "-C", str(repo_root), "commit", "-m", "Fixture"], check=True, capture_output=True)

			identity = identify_repository(repo_root, repository_id="meridian-rift")

			self.assertEqual(identity.remote_identity, "example.invalid/meridian-rift.git")
			self.assertNotIn(temp_dir, str(identity.to_dict()))
			self.assertNotIn("secret", str(identity.to_dict()))

	def test_missing_required_dataset_is_incompatible(self) -> None:
		decision = evaluate_compatibility(
			datasets=(_build("lore", repository=self.tool_repository),),
			requirements=self.requirements,
			selected_repositories=(self.tool_repository, self.game_repository),
		)

		self.assertFalse(decision.compatible)
		self.assertIn("Required dataset 'catalog' is missing.", decision.reasons)

	def test_game_revision_mismatch_is_incompatible(self) -> None:
		stale_game = _repository("meridian-rift", "0" * 40)
		decision = evaluate_compatibility(
			datasets=(
				_build("lore", repository=self.tool_repository),
				_build("catalog", repository=stale_game),
			),
			requirements=self.requirements,
			selected_repositories=(self.tool_repository, self.game_repository),
		)

		self.assertFalse(decision.compatible)
		self.assertTrue(any("meridian-rift" in reason and "revision" in reason for reason in decision.reasons))

	def test_mismatched_schema_is_incompatible(self) -> None:
		decision = evaluate_compatibility(
			datasets=(
				_build("lore", repository=self.tool_repository),
				_build("catalog", repository=self.game_repository, schema_version=2),
			),
			requirements=self.requirements,
			selected_repositories=(self.tool_repository, self.game_repository),
		)

		self.assertFalse(decision.compatible)
		self.assertIn("Dataset 'catalog' schema 2 is not accepted; expected one of [1].", decision.reasons)

	def test_optional_dataset_failure_does_not_block_compatibility(self) -> None:
		decision = evaluate_compatibility(
			datasets=(
				_build("lore", repository=self.tool_repository),
				_build("catalog", repository=self.game_repository),
				_build("graph", repository=self.game_repository, succeeded=False),
			),
			requirements=self.requirements,
			selected_repositories=(self.tool_repository, self.game_repository),
		)

		self.assertTrue(decision.compatible)
		self.assertIn("Optional dataset 'graph' failed its build.", decision.warnings)

	def test_required_capability_is_checked(self) -> None:
		decision = evaluate_compatibility(
			datasets=(
				_build("lore", repository=self.tool_repository),
				_build("catalog", repository=self.game_repository),
				_build("graph", repository=self.game_repository),
			),
			requirements=self.requirements,
			selected_repositories=(self.tool_repository, self.game_repository),
		)

		self.assertTrue(decision.compatible)
		self.assertIn("Optional dataset 'graph' lacks capabilities: module_edges.", decision.warnings)

	def test_serialization_round_trip_preserves_immutable_models(self) -> None:
		builds = (
			_build("lore", repository=self.tool_repository),
			_build("catalog", repository=self.game_repository),
		)
		decision = evaluate_compatibility(
			datasets=builds,
			requirements=self.requirements,
			selected_repositories=(self.tool_repository, self.game_repository),
		)
		snapshot = WorkspaceSnapshot.create(
			datasets=builds,
			requirements=self.requirements,
			compatibility=decision,
			activation=ActivationReceipt(
				activated_at="2026-08-27T12:01:00+00:00",
				previous_snapshot_id=None,
				manifest_sha256="1" * 64,
			),
		)

		self.assertEqual(WorkspaceSnapshot.from_dict(snapshot.to_dict()), snapshot)
		self.assertNotIn("C:\\", str(snapshot.to_dict()))


if __name__ == "__main__":
	unittest.main()

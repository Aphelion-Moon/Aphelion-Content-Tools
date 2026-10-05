from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from webapp.store.snapshot_registry import (
	activate_snapshot,
	active_snapshot,
	previous_snapshot,
	stage_snapshot,
	verify_snapshot,
)
from webapp.store.snapshots import (
	CompatibilityDecision,
	DatasetArtifact,
	DatasetBuild,
	DatasetDiagnostics,
	DatasetRequirement,
	DatasetSource,
	RepositoryIdentity,
	WorkspaceSnapshot,
)


def _snapshot(artifact_bytes: bytes, *, compatible: bool = True) -> WorkspaceSnapshot:
	repository = RepositoryIdentity(repository_id="fixture", remote_identity=None, revision="a" * 40)
	build = DatasetBuild.create(
		kind="fixture",
		schema_version=1,
		sources=(DatasetSource(repository=repository, file_set_sha256="b" * 64),),
		extractor_version="fixture-v1",
		indexer_version=None,
		model_version=None,
		content_sha256=hashlib.sha256(artifact_bytes).hexdigest(),
		counts={"records": 1},
		diagnostics=DatasetDiagnostics(succeeded=True),
		created_at="2026-08-27T12:00:00+00:00",
		artifacts=(
			DatasetArtifact(
				kind="file",
				reference="artifacts/fixture.json",
				sha256=hashlib.sha256(artifact_bytes).hexdigest(),
				count=1,
			),
		),
	)
	return WorkspaceSnapshot.create(
		datasets=(build,),
		requirements=(DatasetRequirement(kind="fixture", accepted_schema_versions=(1,)),),
		compatibility=CompatibilityDecision(compatible=compatible, reasons=() if compatible else ("fixture mismatch",)),
	)


class SnapshotRegistryTests(unittest.TestCase):
	def test_revision_metadata_does_not_authorize_corrupt_artifacts(self) -> None:
		from webapp.store.snapshot_registry import active_snapshot_metadata, snapshot_path
		artifact = b'original'
		snapshot = _snapshot(artifact)
		stage_snapshot(self.repo_root, snapshot, {'artifacts/fixture.json': artifact})
		activate_snapshot(self.repo_root, snapshot.snapshot_id, activated_at='2026-10-05T00:00:00+00:00')
		(snapshot_path(self.repo_root, snapshot.snapshot_id) / 'artifacts/fixture.json').write_bytes(b'changed')
		self.assertEqual(active_snapshot_metadata(self.repo_root).snapshot_id, snapshot.snapshot_id)
		with self.assertRaisesRegex(ValueError, 'hash'):
			active_snapshot(self.repo_root)

	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp_dir.cleanup)
		self.repo_root = Path(self.temp_dir.name)

	def test_stage_verify_and_activate_use_one_atomic_pointer(self) -> None:
		artifact = b'{"fixture":true}\n'
		snapshot = _snapshot(artifact)

		stage_snapshot(self.repo_root, snapshot, {"artifacts/fixture.json": artifact})
		verified = verify_snapshot(self.repo_root, snapshot.snapshot_id)
		activated = activate_snapshot(self.repo_root, snapshot.snapshot_id, activated_at="2026-08-27T12:01:00+00:00")

		self.assertEqual(verified, snapshot)
		self.assertEqual(active_snapshot(self.repo_root), activated)
		self.assertIsNotNone(activated.activation)
		self.assertIsNone(previous_snapshot(self.repo_root))

	def test_second_activation_retains_previous_verified_snapshot(self) -> None:
		first_bytes = b"first\n"
		second_bytes = b"second\n"
		first = _snapshot(first_bytes)
		second = _snapshot(second_bytes)
		stage_snapshot(self.repo_root, first, {"artifacts/fixture.json": first_bytes})
		activate_snapshot(self.repo_root, first.snapshot_id, activated_at="2026-08-27T12:01:00+00:00")
		stage_snapshot(self.repo_root, second, {"artifacts/fixture.json": second_bytes})

		activate_snapshot(self.repo_root, second.snapshot_id, activated_at="2026-08-27T12:02:00+00:00")

		self.assertEqual(active_snapshot(self.repo_root).snapshot_id, second.snapshot_id)
		self.assertEqual(previous_snapshot(self.repo_root).snapshot_id, first.snapshot_id)

	def test_failed_stage_never_changes_the_active_pointer(self) -> None:
		artifact = b"valid\n"
		first = _snapshot(artifact)
		stage_snapshot(self.repo_root, first, {"artifacts/fixture.json": artifact})
		activate_snapshot(self.repo_root, first.snapshot_id, activated_at="2026-08-27T12:01:00+00:00")
		broken = _snapshot(b"expected\n")

		with self.assertRaisesRegex(ValueError, "hash"):
			stage_snapshot(self.repo_root, broken, {"artifacts/fixture.json": b"wrong\n"})

		self.assertEqual(active_snapshot(self.repo_root).snapshot_id, first.snapshot_id)

	def test_incompatible_snapshot_cannot_activate(self) -> None:
		artifact = b"incompatible\n"
		snapshot = _snapshot(artifact, compatible=False)
		stage_snapshot(self.repo_root, snapshot, {"artifacts/fixture.json": artifact})

		with self.assertRaisesRegex(ValueError, "compatible"):
			activate_snapshot(self.repo_root, snapshot.snapshot_id, activated_at="2026-08-27T12:01:00+00:00")

		self.assertIsNone(active_snapshot(self.repo_root))

	def test_artifact_references_cannot_escape_the_snapshot(self) -> None:
		artifact = b"escape\n"
		snapshot = _snapshot(artifact)
		original = snapshot.datasets[0]
		unsafe_build = DatasetBuild.create(
			kind=original.kind,
			schema_version=original.schema_version,
			sources=original.sources,
			extractor_version=original.extractor_version,
			indexer_version=original.indexer_version,
			model_version=original.model_version,
			content_sha256=original.content_sha256,
			counts=dict(original.counts),
			diagnostics=original.diagnostics,
			created_at=original.created_at,
			artifacts=(
				DatasetArtifact(
					kind="file",
					reference="../escape",
					sha256=hashlib.sha256(artifact).hexdigest(),
					count=1,
				),
			),
			capabilities=original.capabilities,
		)
		unsafe = WorkspaceSnapshot.create(
			datasets=(unsafe_build,),
			requirements=snapshot.requirements,
			compatibility=snapshot.compatibility,
		)

		with self.assertRaisesRegex(ValueError, "escapes"):
			stage_snapshot(self.repo_root, unsafe, {"../escape": artifact})


if __name__ == "__main__":
	unittest.main()

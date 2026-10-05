from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path

from tools.lore_editor.write_coordinator import repository_write_lock
from webapp.git_adapter import repository_revision
from webapp.json_storage import canonical_json_bytes
from webapp.path_safety import resolve_repo_path
from webapp.store.snapshot_registry import (
	activate_snapshot,
	active_snapshot,
	active_snapshot_metadata,
	snapshot_path,
	stage_snapshot,
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

from .models import AuthoringCatalog
from .process import RunContext

CATALOG_KIND = 'job-outfit-definitions'
ARTIFACT = 'authoring/catalog.json'


def verify_inputs(root: Path, catalog: AuthoringCatalog) -> None:
	if not catalog.input_files:
		raise ValueError('Analyzer catalog has no source input receipt.')
	for item in catalog.input_files:
		path = resolve_repo_path(root, Path(item.path))
		if path.relative_to(root.resolve()).as_posix() != item.path or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item.sha256:
			raise ValueError(f'Catalog source changed or is stale: {item.path}. Refresh before continuing.')


class Analyzer:
	def __init__(self, manifest: Path | None = None) -> None:
		self.manifest = manifest or Path(__file__).with_name('runtime') / 'analyzer.json'

	def executable(self) -> Path:
		if not self.manifest.is_file():
			raise ValueError('The pinned Meridian analyzer is unavailable. Install the packaged authoring analyzer.')
		manifest = json.loads(self.manifest.read_bytes())
		if manifest.get('schema_version') != 1:
			raise ValueError('Unsupported analyzer package manifest.')
		path = resolve_repo_path(self.manifest.parent, Path(manifest['file']))
		if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != manifest.get('sha256'):
			raise ValueError('The analyzer executable checksum does not match its package manifest.')
		return path

	def export(self, root: Path, output: Path, run: RunContext) -> AuthoringCatalog:
		executable = self.executable()
		package_hash = hashlib.sha256(executable.read_bytes()).hexdigest()
		run.command([str(executable), 'authoring-export', '--project', str(root), '--output', str(output)], root, timeout=1200)
		catalog = AuthoringCatalog.model_validate_json(output.read_bytes())
		catalog.analyzer_package_sha256 = package_hash
		verify_inputs(root, catalog)
		return catalog


class CatalogStore:
	def __init__(self, tool_root: Path, game_root: Path) -> None:
		self.tool_root, self.game_root = tool_root, game_root
		self._cached: tuple[str, AuthoringCatalog, str] | None = None
		self._artifact_stamp: tuple[int, int, int, int] | None = None
		self._observed: tuple[str, list[tuple[Path, tuple[int, int, int, int]]]] | None = None
		self._read_lock = threading.RLock()

	@staticmethod
	def _stamp(path: Path) -> tuple[int, int, int, int]:
		stat = path.stat()
		return stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino

	def read(self, *, force_verify: bool = False) -> tuple[str, AuthoringCatalog, str]:
		with self._read_lock:
			return self._read(force_verify=force_verify)

	def _read(self, *, force_verify: bool) -> tuple[str, AuthoringCatalog, str]:
		snapshot = active_snapshot_metadata(self.tool_root)
		if not snapshot:
			raise ValueError('Build the job/outfit catalog before selecting game definitions.')
		build = next((item for item in snapshot.datasets if item.kind == CATALOG_KIND), None)
		if not build:
			raise ValueError('Build the job/outfit catalog before selecting game definitions.')
		path = snapshot_path(self.tool_root, snapshot.snapshot_id) / ARTIFACT
		stamp = self._stamp(path)
		if not force_verify and self._cached and self._cached[0] == build.build_id and stamp == self._artifact_stamp:
			return self._cached
		active_snapshot(self.tool_root)
		catalog = self._cached[1] if self._cached and self._cached[0] == build.build_id else AuthoringCatalog.model_validate_json(path.read_bytes())
		self._cached = build.build_id, catalog, build.sources[0].repository.revision
		self._artifact_stamp = stamp
		return self._cached

	def verify(self, catalog_id: str) -> AuthoringCatalog:
		current_id, catalog, revision = self.read(force_verify=True)
		if current_id != catalog_id or repository_revision(self.game_root) != revision:
			raise ValueError('The draft references a stale catalog or game revision. Rebase it explicitly after refreshing.')
		self._verify_analyzer(catalog)
		verify_inputs(self.game_root, catalog)
		self._remember(catalog_id, catalog)
		return catalog

	def _remember(self, catalog_id: str, catalog: AuthoringCatalog) -> None:
		self._observed = catalog_id, [(self.game_root / item.path, self._stamp(self.game_root / item.path)) for item in catalog.input_files]

	def observe(self, catalog_id: str) -> None:
		"""Cheap UI currentness; edits still call verify for complete byte hashes."""
		current_id, catalog, revision = self.read()
		if current_id != catalog_id or repository_revision(self.game_root) != revision:
			raise ValueError('The source catalog belongs to a different game revision.')
		self._verify_analyzer(catalog)
		if self._observed is None or self._observed[0] != catalog_id:
			self.verify(catalog_id)
			return
		if any(self._stamp(path) != stamp for path, stamp in self._observed[1]):
			raise ValueError('Source files changed after indexing. Refresh the source catalog.')

	@staticmethod
	def _verify_analyzer(catalog: AuthoringCatalog) -> None:
		if catalog.analyzer_package_sha256 and hashlib.sha256(Analyzer().executable().read_bytes()).hexdigest() != catalog.analyzer_package_sha256:
			raise ValueError('The packaged analyzer changed. Refresh the source catalog.')

	def publish(self, catalog: AuthoringCatalog, revision: str) -> str:
		with repository_write_lock(self.tool_root), repository_write_lock(self.game_root):
			if repository_revision(self.game_root) != revision:
				raise ValueError('Game revision changed during analysis.')
			verify_inputs(self.game_root, catalog)
			# The deterministic export already orders definitions and members. Serialize
			# directly to avoid a second full object graph for a large inherited catalog.
			data = catalog.model_dump_json().encode('utf-8')
			digest = hashlib.sha256(data).hexdigest()
			inputs_hash = hashlib.sha256(canonical_json_bytes([item.model_dump() for item in catalog.input_files])).hexdigest()
			now = datetime.now(UTC).isoformat()
			build = DatasetBuild.create(kind=CATALOG_KIND, schema_version=1,
				sources=(DatasetSource(RepositoryIdentity('meridian-rift', None, revision), inputs_hash),),
				extractor_version=f'{catalog.analyzer_version}:{catalog.analyzer_package_sha256}:{catalog.spacemandmm_revision}:{catalog.spacemandmm_local_patch_sha256}', indexer_version='authoring-1', model_version=None,
				content_sha256=digest, counts={'definitions': len(catalog.definitions)},
				diagnostics=DatasetDiagnostics(True, len(catalog.diagnostics), 0, 'Source-bound authoring catalog'),
				created_at=now, artifacts=(DatasetArtifact('file', ARTIFACT, digest),),
				capabilities=frozenset({'exact', 'structural', 'source-editing'}))
			previous = active_snapshot(self.tool_root)
			datasets = [item for item in previous.datasets if item.kind != CATALOG_KIND] if previous else []
			requirements = [item for item in previous.requirements if item.kind != CATALOG_KIND] if previous else []
			artifacts = {}
			if previous:
				for dataset in datasets:
					for artifact in dataset.artifacts:
						artifacts[artifact.reference] = (snapshot_path(self.tool_root, previous.snapshot_id) / artifact.reference).read_bytes()
			datasets.append(build)
			requirements.append(DatasetRequirement(CATALOG_KIND, (1,), required=False))
			artifacts[ARTIFACT] = data
			# Adding an optional editor dataset cannot promote an incompatible existing snapshot.
			compatibility = previous.compatibility if previous else CompatibilityDecision(True)
			snapshot = WorkspaceSnapshot.create(datasets=tuple(datasets), requirements=tuple(requirements), compatibility=compatibility)
			stage_snapshot(self.tool_root, snapshot, artifacts)
			activate_snapshot(self.tool_root, snapshot.snapshot_id, activated_at=now)
			self._cached = build.build_id, catalog, revision
			self._artifact_stamp = self._stamp(snapshot_path(self.tool_root, snapshot.snapshot_id) / ARTIFACT)
			self._remember(build.build_id, catalog)
			return build.build_id

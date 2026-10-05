from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from webapp.git_adapter import repository_remote_url, repository_revision
from webapp.json_storage import canonical_json_bytes

WorkspaceStatus = Literal["unverified", "compatible", "incompatible"]


def _required_string(payload: dict[str, object], field_name: str) -> str:
	value = payload.get(field_name)
	if not isinstance(value, str) or not value:
		raise ValueError(f"{field_name} must be a non-empty string.")
	return value


def _optional_string(payload: dict[str, object], field_name: str) -> str | None:
	value = payload.get(field_name)
	if value is not None and (not isinstance(value, str) or not value):
		raise ValueError(f"{field_name} must be a non-empty string or null.")
	return value


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
	if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
		raise ValueError(f"{field_name} must be an array of non-empty strings.")
	return tuple(value)


def _content_id(prefix: str, payload: dict[str, object]) -> str:
	return f"{prefix}-{hashlib.sha256(canonical_json_bytes(payload)).hexdigest()}"


def _public_remote_identity(remote_url: str | None) -> str | None:
	if remote_url is None:
		return None
	value = remote_url.strip()
	if "://" in value:
		parsed = urlsplit(value)
		if parsed.hostname is None or parsed.scheme == "file":
			return None
		return f"{parsed.hostname.casefold()}/{parsed.path.lstrip('/').rstrip('/')}"
	if "@" in value and ":" in value:
		host, separator, path = value.rpartition("@")[-1].partition(":")
		if separator and host and path:
			return f"{host.casefold()}/{path.rstrip('/')}"
	return None


def identify_repository(repo_root: Path, *, repository_id: str) -> RepositoryIdentity:
	"""Resolve Git identity without persisting a local path or remote credentials."""

	resolved_root = repo_root.resolve(strict=True)
	return RepositoryIdentity(
		repository_id=repository_id,
		remote_identity=_public_remote_identity(repository_remote_url(resolved_root)),
		revision=repository_revision(resolved_root),
	)


@dataclass(frozen=True)
class RepositoryIdentity:
	"""Stable public repository identity and revision without a local filesystem path."""

	repository_id: str
	remote_identity: str | None
	revision: str

	def to_dict(self) -> dict[str, object]:
		return {
			"repository_id": self.repository_id,
			"remote_identity": self.remote_identity,
			"revision": self.revision,
		}

	@classmethod
	def from_dict(cls, payload: object) -> RepositoryIdentity:
		if not isinstance(payload, dict):
			raise ValueError("Repository identity must be an object.")
		return cls(
			repository_id=_required_string(payload, "repository_id"),
			remote_identity=_optional_string(payload, "remote_identity"),
			revision=_required_string(payload, "revision"),
		)


@dataclass(frozen=True)
class DatasetSource:
	repository: RepositoryIdentity
	file_set_sha256: str
	canonical_revision: str | None = None

	def to_dict(self) -> dict[str, object]:
		return {
			"repository": self.repository.to_dict(),
			"file_set_sha256": self.file_set_sha256,
			"canonical_revision": self.canonical_revision,
		}

	@classmethod
	def from_dict(cls, payload: object) -> DatasetSource:
		if not isinstance(payload, dict):
			raise ValueError("Dataset source must be an object.")
		return cls(
			repository=RepositoryIdentity.from_dict(payload.get("repository")),
			file_set_sha256=_required_string(payload, "file_set_sha256"),
			canonical_revision=_optional_string(payload, "canonical_revision"),
		)


@dataclass(frozen=True)
class DatasetDiagnostics:
	succeeded: bool
	warning_count: int = 0
	error_count: int = 0
	summary: str | None = None

	def to_dict(self) -> dict[str, object]:
		return {
			"succeeded": self.succeeded,
			"warning_count": self.warning_count,
			"error_count": self.error_count,
			"summary": self.summary,
		}

	@classmethod
	def from_dict(cls, payload: object) -> DatasetDiagnostics:
		if not isinstance(payload, dict) or not isinstance(payload.get("succeeded"), bool):
			raise ValueError("Dataset diagnostics require a Boolean succeeded value.")
		warning_count = payload.get("warning_count", 0)
		error_count = payload.get("error_count", 0)
		if not isinstance(warning_count, int) or warning_count < 0:
			raise ValueError("warning_count must be a non-negative integer.")
		if not isinstance(error_count, int) or error_count < 0:
			raise ValueError("error_count must be a non-negative integer.")
		return cls(
			succeeded=payload["succeeded"],
			warning_count=warning_count,
			error_count=error_count,
			summary=_optional_string(payload, "summary"),
		)


@dataclass(frozen=True)
class DatasetArtifact:
	kind: str
	reference: str
	sha256: str
	count: int | None = None

	def to_dict(self) -> dict[str, object]:
		return {"kind": self.kind, "reference": self.reference, "sha256": self.sha256, "count": self.count}

	@classmethod
	def from_dict(cls, payload: object) -> DatasetArtifact:
		if not isinstance(payload, dict):
			raise ValueError("Dataset artifact must be an object.")
		count = payload.get("count")
		if count is not None and (not isinstance(count, int) or count < 0):
			raise ValueError("Artifact count must be a non-negative integer or null.")
		return cls(
			kind=_required_string(payload, "kind"),
			reference=_required_string(payload, "reference"),
			sha256=_required_string(payload, "sha256"),
			count=count,
		)


@dataclass(frozen=True)
class DatasetBuild:
	build_id: str
	kind: str
	schema_version: int
	sources: tuple[DatasetSource, ...]
	extractor_version: str
	indexer_version: str | None
	model_version: str | None
	content_sha256: str
	counts: tuple[tuple[str, int], ...]
	diagnostics: DatasetDiagnostics
	created_at: str
	artifacts: tuple[DatasetArtifact, ...]
	capabilities: frozenset[str]

	@classmethod
	def create(
		cls,
		*,
		kind: str,
		schema_version: int,
		sources: tuple[DatasetSource, ...],
		extractor_version: str,
		indexer_version: str | None,
		model_version: str | None,
		content_sha256: str,
		counts: dict[str, int],
		diagnostics: DatasetDiagnostics,
		created_at: str,
		artifacts: tuple[DatasetArtifact, ...],
		capabilities: frozenset[str] = frozenset(),
	) -> DatasetBuild:
		candidate = cls(
			build_id="pending",
			kind=kind,
			schema_version=schema_version,
			sources=tuple(sources),
			extractor_version=extractor_version,
			indexer_version=indexer_version,
			model_version=model_version,
			content_sha256=content_sha256,
			counts=tuple(sorted(counts.items())),
			diagnostics=diagnostics,
			created_at=created_at,
			artifacts=tuple(artifacts),
			capabilities=frozenset(capabilities),
		)
		return cls(
			build_id=_content_id("dataset", candidate._content_payload()),
			kind=candidate.kind,
			schema_version=candidate.schema_version,
			sources=candidate.sources,
			extractor_version=candidate.extractor_version,
			indexer_version=candidate.indexer_version,
			model_version=candidate.model_version,
			content_sha256=candidate.content_sha256,
			counts=candidate.counts,
			diagnostics=candidate.diagnostics,
			created_at=candidate.created_at,
			artifacts=candidate.artifacts,
			capabilities=candidate.capabilities,
		)

	def _content_payload(self) -> dict[str, object]:
		return {
			"kind": self.kind,
			"schema_version": self.schema_version,
			"sources": [source.to_dict() for source in self.sources],
			"extractor_version": self.extractor_version,
			"indexer_version": self.indexer_version,
			"model_version": self.model_version,
			"content_sha256": self.content_sha256,
			"counts": dict(self.counts),
			"diagnostics": self.diagnostics.to_dict(),
			"created_at": self.created_at,
			"artifacts": [artifact.to_dict() for artifact in self.artifacts],
			"capabilities": sorted(self.capabilities),
		}

	def to_dict(self) -> dict[str, object]:
		return {"build_id": self.build_id, **self._content_payload()}

	@classmethod
	def from_dict(cls, payload: object) -> DatasetBuild:
		if not isinstance(payload, dict):
			raise ValueError("Dataset build must be an object.")
		build_id = _required_string(payload, "build_id")
		kind = _required_string(payload, "kind")
		schema_version = payload.get("schema_version")
		if not isinstance(schema_version, int) or schema_version < 1:
			raise ValueError("schema_version must be a positive integer.")
		sources = payload.get("sources")
		counts = payload.get("counts")
		artifacts = payload.get("artifacts")
		capabilities = payload.get("capabilities")
		if not isinstance(sources, list) or not sources:
			raise ValueError("Dataset build requires at least one source.")
		if not isinstance(counts, dict) or any(not isinstance(key, str) or not isinstance(value, int) or value < 0 for key, value in counts.items()):
			raise ValueError("Dataset build counts must map names to non-negative integers.")
		if not isinstance(artifacts, list):
			raise ValueError("Dataset build artifacts must be an array.")
		capability_values = _string_tuple(capabilities, "capabilities")
		candidate = cls(
			build_id=build_id,
			kind=kind,
			schema_version=schema_version,
			sources=tuple(DatasetSource.from_dict(value) for value in sources),
			extractor_version=_required_string(payload, "extractor_version"),
			indexer_version=_optional_string(payload, "indexer_version"),
			model_version=_optional_string(payload, "model_version"),
			content_sha256=_required_string(payload, "content_sha256"),
			counts=tuple(sorted(counts.items())),
			diagnostics=DatasetDiagnostics.from_dict(payload.get("diagnostics")),
			created_at=_required_string(payload, "created_at"),
			artifacts=tuple(DatasetArtifact.from_dict(value) for value in artifacts),
			capabilities=frozenset(capability_values),
		)
		expected_id = _content_id("dataset", candidate._content_payload())
		if build_id != expected_id:
			raise ValueError("Dataset build id does not match its content.")
		return candidate


@dataclass(frozen=True)
class DatasetRequirement:
	kind: str
	accepted_schema_versions: tuple[int, ...]
	required: bool = True
	required_capabilities: frozenset[str] = frozenset()

	def to_dict(self) -> dict[str, object]:
		return {
			"kind": self.kind,
			"accepted_schema_versions": list(self.accepted_schema_versions),
			"required": self.required,
			"required_capabilities": sorted(self.required_capabilities),
		}

	@classmethod
	def from_dict(cls, payload: object) -> DatasetRequirement:
		if not isinstance(payload, dict):
			raise ValueError("Dataset requirement must be an object.")
		versions = payload.get("accepted_schema_versions")
		if not isinstance(versions, list) or not versions or any(not isinstance(value, int) or value < 1 for value in versions):
			raise ValueError("accepted_schema_versions must contain positive integers.")
		required = payload.get("required", True)
		if not isinstance(required, bool):
			raise ValueError("required must be a Boolean.")
		return cls(
			kind=_required_string(payload, "kind"),
			accepted_schema_versions=tuple(versions),
			required=required,
			required_capabilities=frozenset(_string_tuple(payload.get("required_capabilities", []), "required_capabilities")),
		)


@dataclass(frozen=True)
class CompatibilityDecision:
	compatible: bool
	reasons: tuple[str, ...] = ()
	warnings: tuple[str, ...] = ()

	def to_dict(self) -> dict[str, object]:
		return {"compatible": self.compatible, "reasons": list(self.reasons), "warnings": list(self.warnings)}

	@classmethod
	def from_dict(cls, payload: object) -> CompatibilityDecision:
		if not isinstance(payload, dict) or not isinstance(payload.get("compatible"), bool):
			raise ValueError("Compatibility decision requires a Boolean compatible value.")
		return cls(
			compatible=payload["compatible"],
			reasons=_string_tuple(payload.get("reasons", []), "reasons"),
			warnings=_string_tuple(payload.get("warnings", []), "warnings"),
		)


@dataclass(frozen=True)
class ActivationReceipt:
	activated_at: str
	previous_snapshot_id: str | None
	manifest_sha256: str

	def to_dict(self) -> dict[str, object]:
		return {
			"activated_at": self.activated_at,
			"previous_snapshot_id": self.previous_snapshot_id,
			"manifest_sha256": self.manifest_sha256,
		}

	@classmethod
	def from_dict(cls, payload: object) -> ActivationReceipt:
		if not isinstance(payload, dict):
			raise ValueError("Activation receipt must be an object.")
		return cls(
			activated_at=_required_string(payload, "activated_at"),
			previous_snapshot_id=_optional_string(payload, "previous_snapshot_id"),
			manifest_sha256=_required_string(payload, "manifest_sha256"),
		)


@dataclass(frozen=True)
class WorkspaceSnapshot:
	snapshot_id: str
	datasets: tuple[DatasetBuild, ...]
	requirements: tuple[DatasetRequirement, ...]
	status: WorkspaceStatus
	compatibility: CompatibilityDecision | None
	activation: ActivationReceipt | None

	@classmethod
	def create(
		cls,
		*,
		datasets: tuple[DatasetBuild, ...],
		requirements: tuple[DatasetRequirement, ...],
		compatibility: CompatibilityDecision | None = None,
		activation: ActivationReceipt | None = None,
	) -> WorkspaceSnapshot:
		datasets = tuple(sorted(datasets, key=lambda value: value.kind))
		requirements = tuple(sorted(requirements, key=lambda value: value.kind))
		status: WorkspaceStatus = "unverified"
		if compatibility is not None:
			status = "compatible" if compatibility.compatible else "incompatible"
		payload = cls._payload(datasets, requirements, status, compatibility, activation)
		return cls(_content_id("workspace", cls._identity_payload(payload)), datasets, requirements, status, compatibility, activation)

	@staticmethod
	def _identity_payload(payload: dict[str, object]) -> dict[str, object]:
		return {key: value for key, value in payload.items() if key != "activation"}

	@staticmethod
	def _payload(
		datasets: tuple[DatasetBuild, ...],
		requirements: tuple[DatasetRequirement, ...],
		status: WorkspaceStatus,
		compatibility: CompatibilityDecision | None,
		activation: ActivationReceipt | None,
	) -> dict[str, object]:
		return {
			"datasets": [dataset.to_dict() for dataset in sorted(datasets, key=lambda value: value.kind)],
			"requirements": [requirement.to_dict() for requirement in sorted(requirements, key=lambda value: value.kind)],
			"status": status,
			"compatibility": compatibility.to_dict() if compatibility is not None else None,
			"activation": activation.to_dict() if activation is not None else None,
		}

	def to_dict(self) -> dict[str, object]:
		return {"snapshot_id": self.snapshot_id, **self._payload(
			self.datasets,
			self.requirements,
			self.status,
			self.compatibility,
			self.activation,
		)}

	@classmethod
	def from_dict(cls, payload: object) -> WorkspaceSnapshot:
		if not isinstance(payload, dict):
			raise ValueError("Workspace snapshot must be an object.")
		status = payload.get("status")
		if status not in ("unverified", "compatible", "incompatible"):
			raise ValueError("Workspace snapshot status is invalid.")
		datasets = payload.get("datasets")
		requirements = payload.get("requirements")
		if not isinstance(datasets, list) or not isinstance(requirements, list):
			raise ValueError("Workspace snapshot datasets and requirements must be arrays.")
		compatibility_payload = payload.get("compatibility")
		activation_payload = payload.get("activation")
		candidate = cls(
			snapshot_id=_required_string(payload, "snapshot_id"),
			datasets=tuple(DatasetBuild.from_dict(value) for value in datasets),
			requirements=tuple(DatasetRequirement.from_dict(value) for value in requirements),
			status=status,
			compatibility=CompatibilityDecision.from_dict(compatibility_payload) if compatibility_payload is not None else None,
			activation=ActivationReceipt.from_dict(activation_payload) if activation_payload is not None else None,
		)
		content = {key: value for key, value in candidate.to_dict().items() if key != "snapshot_id"}
		expected_id = _content_id("workspace", cls._identity_payload(content))
		if candidate.snapshot_id != expected_id:
			raise ValueError("Workspace snapshot id does not match its content.")
		return candidate

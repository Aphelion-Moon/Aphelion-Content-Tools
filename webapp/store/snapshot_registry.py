from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path, PurePosixPath

from tools.lore_editor.write_coordinator import repository_write_lock

from .metadata import store_root
from .snapshots import ActivationReceipt, WorkspaceSnapshot

SNAPSHOTS_DIRECTORY = "workspace-snapshots"
SNAPSHOT_MANIFEST_FILE = "workspace.json"
ACTIVATION_RECEIPT_FILE = "activation.json"
ACTIVE_SNAPSHOT_FILE = "active-workspace.json"
PREVIOUS_SNAPSHOT_FILE = "previous-workspace.json"


def snapshot_path(repo_root: Path, snapshot_id: str) -> Path:
	if not snapshot_id.startswith("workspace-") or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in snapshot_id):
		raise ValueError("Invalid workspace snapshot id.")
	return store_root(repo_root) / SNAPSHOTS_DIRECTORY / snapshot_id


def _json_bytes(payload: Mapping[str, object]) -> bytes:
	return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def _atomic_write(path: Path, data: bytes) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
	temporary_path = Path(temporary_name)
	try:
		with os.fdopen(file_descriptor, "wb") as handle:
			handle.write(data)
			handle.flush()
			os.fsync(handle.fileno())
		os.replace(temporary_path, path)
	finally:
		temporary_path.unlink(missing_ok=True)


def _artifact_path(root: Path, reference: str) -> Path:
	if "\\" in reference:
		raise ValueError(f"Artifact reference uses a non-portable separator: {reference}")
	relative = PurePosixPath(reference)
	if relative.is_absolute() or not relative.parts or ".." in relative.parts:
		raise ValueError(f"Artifact reference escapes the workspace snapshot: {reference}")
	resolved = root.joinpath(*relative.parts).resolve()
	try:
		resolved.relative_to(root.resolve())
	except ValueError as exc:
		raise ValueError(f"Artifact reference escapes the workspace snapshot: {reference}") from exc
	return resolved


def _manifest_path(repo_root: Path, snapshot_id: str) -> Path:
	return snapshot_path(repo_root, snapshot_id) / SNAPSHOT_MANIFEST_FILE


def stage_snapshot(repo_root: Path, snapshot: WorkspaceSnapshot, artifacts: Mapping[str, bytes]) -> Path:
	with repository_write_lock(repo_root):
		return _stage_snapshot_locked(repo_root, snapshot, artifacts)


def _stage_snapshot_locked(repo_root: Path, snapshot: WorkspaceSnapshot, artifacts: Mapping[str, bytes]) -> Path:
	"""Write and verify an immutable inactive snapshot before making it visible to activation."""

	WorkspaceSnapshot.from_dict(snapshot.to_dict())
	root = store_root(repo_root) / SNAPSHOTS_DIRECTORY
	root.mkdir(parents=True, exist_ok=True)
	destination = snapshot_path(repo_root, snapshot.snapshot_id)
	if destination.exists():
		verified = verify_snapshot(repo_root, snapshot.snapshot_id)
		if verified != snapshot:
			raise ValueError("Existing workspace snapshot does not match the requested snapshot.")
		return destination
	temporary = Path(tempfile.mkdtemp(prefix=".workspace-build-", dir=root))
	try:
		required_references: set[str] = set()
		for dataset in snapshot.datasets:
			for artifact in dataset.artifacts:
				if artifact.kind != "file":
					raise ValueError(f"Unsupported dataset artifact kind '{artifact.kind}'.")
				required_references.add(artifact.reference)
				data = artifacts.get(artifact.reference)
				if data is None:
					raise ValueError(f"Dataset artifact is missing: {artifact.reference}")
				if hashlib.sha256(data).hexdigest() != artifact.sha256:
					raise ValueError(f"Dataset artifact hash does not match: {artifact.reference}")
				path = _artifact_path(temporary, artifact.reference)
				path.parent.mkdir(parents=True, exist_ok=True)
				path.write_bytes(data)
		if set(artifacts) != required_references:
			raise ValueError("Provided artifacts do not exactly match the snapshot manifest.")
		_atomic_write(temporary / SNAPSHOT_MANIFEST_FILE, _json_bytes(snapshot.to_dict()))
		os.replace(temporary, destination)
	except Exception:
		shutil.rmtree(temporary, ignore_errors=True)
		raise
	verify_snapshot(repo_root, snapshot.snapshot_id)
	return destination


def _read_manifest(repo_root: Path, snapshot_id: str) -> WorkspaceSnapshot:
	manifest_path = _manifest_path(repo_root, snapshot_id)
	try:
		payload = json.loads(manifest_path.read_text(encoding="utf-8"))
	except (OSError, json.JSONDecodeError) as exc:
		raise ValueError(f"Workspace snapshot manifest is unreadable: {snapshot_id}") from exc
	snapshot = WorkspaceSnapshot.from_dict(payload)
	if snapshot.snapshot_id != snapshot_id:
		raise ValueError("Workspace snapshot directory does not match its manifest id.")
	return snapshot


def verify_snapshot(repo_root: Path, snapshot_id: str) -> WorkspaceSnapshot:
	snapshot = _read_manifest(repo_root, snapshot_id)
	root = snapshot_path(repo_root, snapshot_id)
	for dataset in snapshot.datasets:
		for artifact in dataset.artifacts:
			if artifact.kind != "file":
				raise ValueError(f"Unsupported dataset artifact kind '{artifact.kind}'.")
			path = _artifact_path(root, artifact.reference)
			try:
				with path.open('rb') as stream:
					digest = hashlib.file_digest(stream, 'sha256').hexdigest()
			except OSError as exc:
				raise ValueError(f"Dataset artifact is unreadable: {artifact.reference}") from exc
			if digest != artifact.sha256:
				raise ValueError(f"Dataset artifact hash does not match: {artifact.reference}")
	return snapshot


def _pointer_path(repo_root: Path, *, previous: bool) -> Path:
	return store_root(repo_root) / (PREVIOUS_SNAPSHOT_FILE if previous else ACTIVE_SNAPSHOT_FILE)


def _read_pointer(repo_root: Path, *, previous: bool) -> dict[str, object] | None:
	path = _pointer_path(repo_root, previous=previous)
	try:
		payload = json.loads(path.read_text(encoding="utf-8"))
	except FileNotFoundError:
		return None
	except (OSError, json.JSONDecodeError) as exc:
		raise ValueError(f"Workspace snapshot pointer is unreadable: {path.name}") from exc
	if not isinstance(payload, dict) or not isinstance(payload.get("snapshot_id"), str):
		raise ValueError(f"Workspace snapshot pointer is invalid: {path.name}")
	return payload


def _snapshot_from_pointer(repo_root: Path, *, previous: bool, verify_artifacts: bool = True) -> WorkspaceSnapshot | None:
	pointer = _read_pointer(repo_root, previous=previous)
	if pointer is None:
		return None
	snapshot_id = str(pointer["snapshot_id"])
	snapshot = verify_snapshot(repo_root, snapshot_id) if verify_artifacts else _read_manifest(repo_root, snapshot_id)
	receipt_path = snapshot_path(repo_root, snapshot_id) / ACTIVATION_RECEIPT_FILE
	try:
		receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
	except (OSError, json.JSONDecodeError) as exc:
		raise ValueError(f"Workspace activation receipt is unreadable: {snapshot_id}") from exc
	receipt = ActivationReceipt.from_dict(receipt_payload)
	digest = hashlib.sha256(_manifest_path(repo_root, snapshot_id).read_bytes()).hexdigest()
	if digest != pointer.get('manifest_sha256') or digest != receipt.manifest_sha256:
		raise ValueError('Workspace activation manifest hash does not match its receipt.')
	return replace(snapshot, activation=receipt)


def active_snapshot(repo_root: Path) -> WorkspaceSnapshot | None:
	return _snapshot_from_pointer(repo_root, previous=False)


def active_snapshot_metadata(repo_root: Path) -> WorkspaceSnapshot | None:
	"""Read revision identity only. This never substitutes for artifact verification."""
	return _snapshot_from_pointer(repo_root, previous=False, verify_artifacts=False)


def previous_snapshot(repo_root: Path) -> WorkspaceSnapshot | None:
	return _snapshot_from_pointer(repo_root, previous=True)


def activate_snapshot(repo_root: Path, snapshot_id: str, *, activated_at: str) -> WorkspaceSnapshot:
	with repository_write_lock(repo_root):
		return _activate_snapshot_locked(repo_root, snapshot_id, activated_at=activated_at)


def _activate_snapshot_locked(repo_root: Path, snapshot_id: str, *, activated_at: str) -> WorkspaceSnapshot:
	snapshot = verify_snapshot(repo_root, snapshot_id)
	if snapshot.compatibility is None or not snapshot.compatibility.compatible:
		raise ValueError("Only a verified compatible workspace snapshot can be activated.")
	manifest_bytes = _manifest_path(repo_root, snapshot_id).read_bytes()
	current_pointer = _read_pointer(repo_root, previous=False)
	previous_id = str(current_pointer["snapshot_id"]) if current_pointer is not None else None
	receipt = ActivationReceipt(
		activated_at=activated_at,
		previous_snapshot_id=previous_id,
		manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
	)
	_atomic_write(snapshot_path(repo_root, snapshot_id) / ACTIVATION_RECEIPT_FILE, _json_bytes(receipt.to_dict()))
	if current_pointer is not None and previous_id != snapshot_id:
		_atomic_write(_pointer_path(repo_root, previous=True), _json_bytes(current_pointer))
	pointer = {"snapshot_id": snapshot_id, "manifest_sha256": receipt.manifest_sha256}
	_atomic_write(_pointer_path(repo_root, previous=False), _json_bytes(pointer))
	return replace(snapshot, activation=receipt)

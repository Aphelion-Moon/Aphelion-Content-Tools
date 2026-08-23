from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

from webapp.json_storage import atomic_write, canonical_json_bytes

from .catalog import activate_catalog_targets, normalize_targets, read_current_targets, refresh_catalog

CATALOG_SEED_SCHEMA_VERSION = 1
CATALOG_SEED_GENERATOR_VERSION = "1.0.0"
DEFAULT_MANIFEST_PATH = Path("tools/lore_editor/catalog-seed.json")
DOWNLOAD_CHUNK_BYTES = 1024 * 1024


def _required_string(payload: dict[str, object], field: str) -> str:
	value = payload.get(field)
	if not isinstance(value, str) or not value:
		raise ValueError(f"Catalog seed manifest requires a non-empty {field}.")
	return value


@dataclass(frozen=True)
class CatalogSeedManifest:
	schema_version: int
	source_game_commit: str
	generator_version: str
	byte_size: int
	sha256: str
	download_url: str

	def to_dict(self) -> dict[str, object]:
		return {
			"schema_version": self.schema_version,
			"source_game_commit": self.source_game_commit,
			"generator_version": self.generator_version,
			"byte_size": self.byte_size,
			"sha256": self.sha256,
			"download_url": self.download_url,
		}

	@classmethod
	def from_dict(cls, payload: object) -> CatalogSeedManifest:
		if not isinstance(payload, dict):
			raise ValueError("Catalog seed manifest must be a JSON object.")
		if payload.get("schema_version") != CATALOG_SEED_SCHEMA_VERSION:
			raise ValueError("Unsupported catalog seed schema version.")
		byte_size = payload.get("byte_size")
		if not isinstance(byte_size, int) or byte_size < 1:
			raise ValueError("Catalog seed manifest byte_size must be a positive integer.")
		sha256 = _required_string(payload, "sha256")
		if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256):
			raise ValueError("Catalog seed manifest sha256 must be a lowercase SHA-256 digest.")
		return cls(
			schema_version=CATALOG_SEED_SCHEMA_VERSION,
			source_game_commit=_required_string(payload, "source_game_commit"),
			generator_version=_required_string(payload, "generator_version"),
			byte_size=byte_size,
			sha256=sha256,
			download_url=_required_string(payload, "download_url"),
		)


@dataclass(frozen=True)
class CatalogBootstrapResult:
	source: str
	target_count: int
	warning: str | None = None


def package_catalog_seed(
	repo_root: Path,
	*,
	seed_path: Path,
	manifest_path: Path,
	source_game_commit: str,
	download_url: str,
	generator_version: str = CATALOG_SEED_GENERATOR_VERSION,
) -> CatalogSeedManifest:
	"""Package the active catalog as a canonical release asset and its small versioned manifest."""
	targets = read_current_targets(repo_root.resolve())
	if not targets:
		raise ValueError("No catalog targets are available to package.")
	seed_bytes = canonical_json_bytes(normalize_targets(targets))
	manifest = CatalogSeedManifest(
		schema_version=CATALOG_SEED_SCHEMA_VERSION,
		source_game_commit=source_game_commit,
		generator_version=generator_version,
		byte_size=len(seed_bytes),
		sha256=hashlib.sha256(seed_bytes).hexdigest(),
		download_url=download_url,
	)
	atomic_write(seed_path.resolve(), seed_bytes)
	atomic_write(manifest_path.resolve(), canonical_json_bytes(manifest.to_dict()))
	return manifest


def load_seed_manifest(path: Path) -> CatalogSeedManifest:
	try:
		payload = json.loads(path.read_text(encoding="utf-8"))
	except (OSError, json.JSONDecodeError) as exc:
		raise ValueError(f"Catalog seed manifest could not be read: {exc}") from exc
	return CatalogSeedManifest.from_dict(payload)


def _validate_seed(path: Path, manifest: CatalogSeedManifest) -> list[dict[str, object]]:
	seed_bytes = path.read_bytes()
	if len(seed_bytes) != manifest.byte_size:
		raise ValueError("Catalog seed byte size does not match its release manifest.")
	if hashlib.sha256(seed_bytes).hexdigest() != manifest.sha256:
		raise ValueError("Catalog seed SHA-256 does not match its release manifest.")
	try:
		raw_targets = json.loads(seed_bytes)
	except json.JSONDecodeError as exc:
		raise ValueError(f"Catalog seed contains malformed JSON: {exc}") from exc
	targets = normalize_targets(raw_targets)
	if canonical_json_bytes(targets) != seed_bytes:
		raise ValueError("Catalog seed is not in the canonical JSON release format.")
	return targets


def default_cache_root() -> Path:
	local_app_data = os.environ.get("LOCALAPPDATA")
	if local_app_data:
		return Path(local_app_data) / "AphelionContentTools" / "catalog-seeds"
	return Path.home() / ".aphelion-content-tools" / "catalog-seeds"


def cached_seed_path(manifest: CatalogSeedManifest, cache_root: Path) -> Path:
	return cache_root.resolve() / f"{manifest.sha256}.json"


def download_seed(manifest: CatalogSeedManifest, cache_root: Path, *, opener=urlopen) -> Path:
	"""Download, verify, and atomically activate one release seed in the local cache."""
	resolved_cache = cache_root.resolve()
	resolved_cache.mkdir(parents=True, exist_ok=True)
	destination = cached_seed_path(manifest, resolved_cache)
	file_descriptor, temporary_name = tempfile.mkstemp(prefix=".catalog-seed.", suffix=".download", dir=resolved_cache)
	temporary_path = Path(temporary_name)
	try:
		with os.fdopen(file_descriptor, "wb") as output, opener(manifest.download_url) as response:
			while chunk := response.read(DOWNLOAD_CHUNK_BYTES):
				output.write(chunk)
			output.flush()
			os.fsync(output.fileno())
		_validate_seed(temporary_path, manifest)
		os.replace(temporary_path, destination)
		return destination
	finally:
		temporary_path.unlink(missing_ok=True)


def bootstrap_catalog(
	repo_root: Path,
	*,
	manifest_path: Path | None = None,
	cache_root: Path | None = None,
	game_repo_root: Path | None = None,
) -> CatalogBootstrapResult:
	"""Ensure a catalog exists without making release-seed availability a writer-data dependency."""
	resolved_root = repo_root.resolve()
	existing = read_current_targets(resolved_root)
	if existing:
		return CatalogBootstrapResult(source="existing", target_count=len(existing))
	resolved_manifest = (manifest_path or (resolved_root / DEFAULT_MANIFEST_PATH)).resolve()
	resolved_game_root = game_repo_root.resolve() if game_repo_root is not None else None
	try:
		manifest = load_seed_manifest(resolved_manifest)
		resolved_cache = (cache_root or default_cache_root()).resolve()
		seed_path = cached_seed_path(manifest, resolved_cache)
		source = "cached-seed"
		try:
			targets = _validate_seed(seed_path, manifest)
		except (OSError, ValueError):
			seed_path.unlink(missing_ok=True)
			seed_path = download_seed(manifest, resolved_cache)
			targets = _validate_seed(seed_path, manifest)
			source = "downloaded-seed"
		activate_catalog_targets(
			resolved_root,
			targets,
			source_game_revision=manifest.source_game_commit,
		)
		return CatalogBootstrapResult(source=source, target_count=len(targets))
	except (OSError, ValueError) as exc:
		warning = str(exc)
		if resolved_game_root is not None:
			targets = refresh_catalog(resolved_root, game_repo_root=resolved_game_root)
			return CatalogBootstrapResult(source="local-rebuild", target_count=len(targets), warning=warning)
		return CatalogBootstrapResult(source="unavailable", target_count=0, warning=warning)

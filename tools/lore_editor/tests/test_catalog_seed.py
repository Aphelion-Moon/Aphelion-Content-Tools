from __future__ import annotations

import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from tools.lore_editor import catalog_seed
from tools.lore_editor.catalog import read_current_targets
from tools.lore_editor.catalog_seed import (
	CATALOG_SEED_SCHEMA_VERSION,
	CatalogBootstrapResult,
	CatalogSeedManifest,
	bootstrap_catalog,
	download_seed,
	package_catalog_seed,
)
from tools.lore_editor.export import prepare_export
from tools.lore_editor.generate import generate_dm
from tools.lore_editor.records import CONTENT_ROOT, atomic_write_record, record_path
from tools.lore_editor.source import load_corpus
from webapp.api import create_app
from webapp.json_storage import canonical_json_bytes
from webapp.manifest_base import sha256_bytes

RADIO_TARGET = {
	"type_path": "/obj/item/radio",
	"label": "Radio",
	"editable_root": "/obj/item",
	"parent_type": "/obj/item",
	"field_profile": "atom_like",
	"base_values": {"name": "radio", "description": "A station-bound radio."},
	"icon_metadata": {},
}


class _InterruptedResponse:
	def __enter__(self):
		return self

	def __exit__(self, *_args) -> None:
		return None

	def read(self, _size: int) -> bytes:
		raise OSError("connection interrupted")


class CatalogSeedTests(unittest.TestCase):
	def setUp(self) -> None:
		self.temporary_directory = tempfile.TemporaryDirectory()
		self.addCleanup(self.temporary_directory.cleanup)
		self.root = Path(self.temporary_directory.name)
		self.repo_root = self.root / "repo"
		self.repo_root.mkdir()
		self.cache_root = self.root / "cache"
		self.seed_bytes = canonical_json_bytes([RADIO_TARGET])
		self.manifest = CatalogSeedManifest(
			schema_version=CATALOG_SEED_SCHEMA_VERSION,
			source_game_commit="game-sha",
			generator_version="1.0.0",
			byte_size=len(self.seed_bytes),
			sha256=sha256_bytes(self.seed_bytes),
			download_url="https://example.invalid/catalog-targets.json",
		)
		self.manifest_path = self.root / "catalog-seed.json"
		self.manifest_path.write_text(json.dumps(self.manifest.to_dict()), encoding="utf-8")

	def test_valid_cached_seed_is_verified_and_activated_without_downloading(self) -> None:
		cached_seed = self.cache_root / f"{self.manifest.sha256}.json"
		cached_seed.parent.mkdir(parents=True)
		cached_seed.write_bytes(self.seed_bytes)

		with patch("tools.lore_editor.catalog_seed.urlopen") as opener:
			result = bootstrap_catalog(
				self.repo_root,
				manifest_path=self.manifest_path,
				cache_root=self.cache_root,
			)

		opener.assert_not_called()
		self.assertEqual(result.source, "cached-seed")
		self.assertEqual(read_current_targets(self.repo_root), [RADIO_TARGET])

	def test_release_packaging_writes_canonical_seed_and_versioned_manifest(self) -> None:
		cached_seed = self.cache_root / f"{self.manifest.sha256}.json"
		cached_seed.parent.mkdir(parents=True)
		cached_seed.write_bytes(self.seed_bytes)
		bootstrap_catalog(self.repo_root, manifest_path=self.manifest_path, cache_root=self.cache_root)
		seed_output = self.root / "release/catalog-targets.json"
		manifest_output = self.root / "release/catalog-seed.json"

		manifest = package_catalog_seed(
			self.repo_root,
			seed_path=seed_output,
			manifest_path=manifest_output,
			source_game_commit="release-game-sha",
			download_url="https://example.invalid/releases/catalog-targets.json",
		)

		self.assertEqual(seed_output.read_bytes(), self.seed_bytes)
		self.assertEqual(CatalogSeedManifest.from_dict(json.loads(manifest_output.read_text(encoding="utf-8"))), manifest)

	def test_download_hash_mismatch_leaves_no_cached_seed(self) -> None:
		corrupt = self.root / "corrupt.json"
		corrupt.write_bytes(b"x" * len(self.seed_bytes))

		with self.assertRaisesRegex(ValueError, "SHA-256"):
			download_seed(
				self.manifest,
				self.cache_root,
				opener=lambda _url: corrupt.open("rb"),
			)

		self.assertEqual(list(self.cache_root.glob("*")), [])

	def test_interrupted_download_removes_temporary_file(self) -> None:
		with self.assertRaisesRegex(OSError, "interrupted"):
			download_seed(
				self.manifest,
				self.cache_root,
				opener=lambda _url: _InterruptedResponse(),
			)

		self.assertEqual(list(self.cache_root.glob("*")), [])

	def test_download_stops_at_the_manifest_size_and_sets_a_network_timeout(self) -> None:
		class OversizedResponse(io.BytesIO):
			consumed = 0

			def read(self, size=-1):
				chunk = super().read(size)
				self.consumed += len(chunk)
				return chunk

		response = OversizedResponse(self.seed_bytes + b"x" * 4096)
		with patch.object(catalog_seed, "urlopen", return_value=response) as opener, self.assertRaisesRegex(ValueError, "byte size"):
			download_seed(self.manifest, self.cache_root)
		self.assertLessEqual(response.consumed, self.manifest.byte_size + 1)
		self.assertGreater(opener.call_args.kwargs["timeout"], 0)
		self.assertEqual(list(self.cache_root.glob("*")), [])

	def test_oversized_cache_is_rejected_without_loading_its_contents(self) -> None:
		seed = self.root / "oversized.json"
		seed.write_bytes(self.seed_bytes + b"extra")
		with patch.object(Path, "read_bytes", side_effect=AssertionError("oversized cache must not be loaded")), self.assertRaisesRegex(ValueError, "byte size"):
			catalog_seed._validate_seed(seed, self.manifest)

	def test_offline_download_falls_back_to_local_catalog_rebuild(self) -> None:
		game_root = self.root / "game"
		game_root.mkdir()
		with (
			patch("tools.lore_editor.catalog_seed.download_seed", side_effect=OSError("offline")),
			patch("tools.lore_editor.catalog_seed.refresh_catalog", return_value=[RADIO_TARGET]) as refresh,
		):
			result = bootstrap_catalog(
				self.repo_root,
				manifest_path=self.manifest_path,
				cache_root=self.cache_root,
				game_repo_root=game_root,
			)

		self.assertEqual(result, CatalogBootstrapResult(source="local-rebuild", target_count=1, warning="offline"))
		refresh.assert_called_once_with(self.repo_root.resolve(), game_repo_root=game_root.resolve())

	def test_incompatible_schema_is_rejected_before_download(self) -> None:
		payload = self.manifest.to_dict() | {"schema_version": CATALOG_SEED_SCHEMA_VERSION + 1}
		with self.assertRaisesRegex(ValueError, "schema version"):
			CatalogSeedManifest.from_dict(payload)

	def test_missing_seed_never_blocks_or_changes_canonical_writer_records(self) -> None:
		group_path = record_path(self.repo_root, "group", "items")
		group = {
			"id": "items",
			"label": "Items",
			"color": "#ffffff",
			"keywords": [],
			"type_path_prefixes": ["/obj/item"],
		}
		atomic_write_record(group_path, group)

		result = bootstrap_catalog(self.repo_root, manifest_path=self.root / "missing.json")

		self.assertEqual(result.source, "unavailable")
		self.assertEqual(json.loads(group_path.read_text(encoding="utf-8")), group)

	def test_clean_checkout_activates_seed_reconciles_eight_groups_and_serves_review_feed(self) -> None:
		source_groups = Path(__file__).resolve().parents[1] / "content/groups"
		destination_groups = self.repo_root / CONTENT_ROOT / "groups"
		shutil.copytree(source_groups, destination_groups)
		cached_seed = self.cache_root / f"{self.manifest.sha256}.json"
		cached_seed.parent.mkdir(parents=True)
		cached_seed.write_bytes(self.seed_bytes)

		result = bootstrap_catalog(
			self.repo_root,
			manifest_path=self.manifest_path,
			cache_root=self.cache_root,
		)
		with TestClient(create_app(self.repo_root)) as client:
			groups = client.get("/api/groups")
			review = client.get("/api/review", params={"q": "/obj/item/radio"})

		self.assertEqual(result.target_count, 1)
		self.assertEqual(len(groups.json()["groups"]), 8)
		self.assertEqual(review.status_code, 200)
		self.assertEqual(review.json()["entries"][0]["type_path"], "/obj/item/radio")

	def test_recorded_commit_plus_seed_reproduces_export_bytes_in_fresh_checkout(self) -> None:
		author_root = self.root / "author"
		game_root = self.root / "game"
		for repository in (author_root, game_root):
			repository.mkdir()
			subprocess.run(["git", "-C", str(repository), "init", "--initial-branch=main"], check=True, capture_output=True)
			subprocess.run(["git", "-C", str(repository), "config", "user.name", "Lore Writer"], check=True)
			subprocess.run(["git", "-C", str(repository), "config", "user.email", "writer@example.invalid"], check=True)
		override_path = record_path(author_root, "override", "items.radio")
		atomic_write_record(override_path, {
			"id": "items.radio",
			"type_path": "/obj/item/radio",
			"name": "Frontier radio",
		})
		cached_seed = self.cache_root / f"{self.manifest.sha256}.json"
		cached_seed.parent.mkdir(parents=True)
		cached_seed.write_bytes(self.seed_bytes)
		bootstrap_catalog(author_root, manifest_path=self.manifest_path, cache_root=self.cache_root)
		subprocess.run(["git", "-C", str(author_root), "add", override_path.relative_to(author_root).as_posix()], check=True)
		subprocess.run(["git", "-C", str(author_root), "commit", "-m", "Author radio"], check=True, capture_output=True)

		(game_root / "tgstation.dme").write_text("", encoding="utf-8")
		artifact = game_root / "modular_aphelion/modules/lore_overhaul/code/generated_lore_overrides.dm"
		artifact.parent.mkdir(parents=True)
		artifact.write_text("old\n", encoding="utf-8")
		subprocess.run(["git", "-C", str(game_root), "add", "--all"], check=True)
		subprocess.run(["git", "-C", str(game_root), "commit", "-m", "Game source"], check=True, capture_output=True)

		prepared = prepare_export(author_root, game_root, self.root / "stages")
		fresh_root = self.root / "fresh"
		subprocess.run(["git", "clone", str(author_root), str(fresh_root)], check=True, capture_output=True)
		bootstrap_catalog(fresh_root, manifest_path=self.manifest_path, cache_root=self.cache_root)
		catalog_bytes = canonical_json_bytes(read_current_targets(fresh_root))
		reproduced = generate_dm(
			load_corpus(fresh_root),
			tool_repo_revision=prepared.manifest.tool_repo_revision,
			catalog_sha256=sha256_bytes(catalog_bytes),
		).encode("utf-8")

		self.assertEqual(reproduced, prepared.artifact_path.read_bytes())

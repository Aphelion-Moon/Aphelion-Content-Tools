import json
from hashlib import sha256
from pathlib import Path, PureWindowsPath

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREPARED_ROOT = PROJECT_ROOT / "webapp/frontend/src/assets/parsec/prepared"
REFERENCE_ROOT = PROJECT_ROOT / "webapp/frontend/src/assets/parsec/source/references"


def test_production_compositions_only_reference_durable_project_sources():
	composition_paths = sorted(PREPARED_ROOT.rglob("*.composition.json"))

	assert composition_paths
	for composition_path in composition_paths:
		composition = json.loads(composition_path.read_text(encoding="utf-8"))
		for frame in composition["frames"]:
			source = frame["source"]
			assert not PureWindowsPath(source).is_absolute(), (
				f"{composition_path} references a machine-local source: {source}"
			)
			assert (PROJECT_ROOT / source).is_file(), (
				f"{composition_path} references a missing project source: {source}"
			)


def test_generation_references_are_manual_verified_trims_of_project_sources():
	metadata_paths = sorted(REFERENCE_ROOT.glob("*.reference.trim.json"))

	assert metadata_paths
	for metadata_path in metadata_paths:
		metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
		assert metadata["tool"] == "manual-reference-trim-v1"
		assert min(metadata["retainedMargin"]) >= metadata["minimumMargin"] >= 8
		source_path = PROJECT_ROOT / metadata["source"]
		output_path = PROJECT_ROOT / metadata["destination"]
		assert source_path.is_file()
		assert output_path.is_file()
		assert sha256(source_path.read_bytes()).hexdigest() == metadata["sourceSha256"]
		assert sha256(output_path.read_bytes()).hexdigest() == metadata["outputSha256"]
		with Image.open(output_path) as reference:
			assert list(reference.size) == metadata["outputSize"]


def test_production_outline_manifests_reference_preserved_sources_with_matching_hashes():
	manifest_paths = sorted(PREPARED_ROOT.glob("parsec-*/outline-preparation.json"))

	assert len(manifest_paths) == 6
	for manifest_path in manifest_paths:
		manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
		assert manifest["tool"] == "generated-strip-v4"
		for frame in manifest["frames"]:
			source = frame["source"]
			output = frame["path"]
			assert not PureWindowsPath(source).is_absolute()
			assert not PureWindowsPath(output).is_absolute()
			source_path = PROJECT_ROOT / source
			output_path = PROJECT_ROOT / output
			assert source_path.is_file()
			assert output_path.is_file()
			assert sha256(source_path.read_bytes()).hexdigest() == frame["sourceSha256"]
			assert sha256(output_path.read_bytes()).hexdigest() == frame["sha256"]

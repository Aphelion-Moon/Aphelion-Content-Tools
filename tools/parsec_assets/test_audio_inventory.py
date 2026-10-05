from __future__ import annotations

import wave
from hashlib import sha256

from tools.parsec_assets.audio_inventory import check_audio_register, inventory_audio


def _wav(path):
	with wave.open(str(path), "wb") as audio:
		audio.setnchannels(1)
		audio.setsampwidth(2)
		audio.setframerate(8_000)
		audio.writeframes(b"\x00\x00" * 800)


def test_audio_inventory_records_hash_duration_channels_and_source(tmp_path):
	source = tmp_path / "bark.wav"
	_wav(source)
	entry = inventory_audio([source], source_revision="fixture-rev", repository_root=tmp_path)[0]
	assert entry.duration_ms == 100
	assert entry.channels == 1
	assert entry.sha256 == sha256(source.read_bytes()).hexdigest()
	assert entry.source_revision == "fixture-rev"
	assert entry.path == "bark.wav"


def test_audio_inventory_refuses_unknown_files(tmp_path):
	source = tmp_path / "not-audio.bin"
	source.write_bytes(b"nope")
	try:
		inventory_audio([source], source_revision="fixture-rev", repository_root=tmp_path)
	except ValueError as error:
		assert "Unsupported audio" in str(error)
	else:
		raise AssertionError("unsupported audio should fail")


def test_check_register_verifies_source_hash_and_metadata(tmp_path):
	repository = tmp_path / "Meridian-Rift"
	repository.mkdir()
	source = repository / "sound" / "bark.wav"
	source.parent.mkdir()
	_wav(source)
	entry = inventory_audio([source], source_revision="fixture-rev", repository_root=repository)[0]
	register = tmp_path / "parsec-asset-register.md"
	register.write_text(
		"| Asset ID | Status | Source path | Revision | SHA-256 | Duration ms | Channels | License | Author / attribution | Notes |\n"
		"| --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- |\n"
		f"| `bark` | `candidate` | `{entry.path}` | `{entry.source_revision}` | `{entry.sha256}` | {entry.duration_ms} | {entry.channels} | `CC0` | Fixture | Test |\n",
		encoding="utf-8",
	)
	assert check_audio_register(register, repository_root=repository) == []
	source.write_bytes(source.read_bytes() + b"changed")
	assert "bark: SHA-256 does not match" in check_audio_register(register, repository_root=repository)

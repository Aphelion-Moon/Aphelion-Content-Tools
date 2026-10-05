from hashlib import sha256
from pathlib import Path

import pytest

from tools.parsec_assets.build_audio_pack import AudioSource, build_audio_pack


def test_audio_pack_copies_exact_source_bytes_and_records_policy(tmp_path: Path) -> None:
	repository = tmp_path / "rift"
	source = repository / "sound" / "bark.ogg"
	source.parent.mkdir(parents=True)
	source.write_bytes(b"fixture-ogg")
	output = tmp_path / "audio"

	records = build_audio_pack(
		(AudioSource("voice-bark", "sound/bark.ogg", "voice", 0.75, 2_000),),
		repository,
		output,
		source_revision="fixture",
	)

	prepared = output / "voice-bark.ogg"
	assert prepared.read_bytes() == source.read_bytes()
	assert records[0]["source_sha256"] == sha256(source.read_bytes()).hexdigest()
	assert records[0]["output_sha256"] == sha256(prepared.read_bytes()).hexdigest()
	assert records[0]["transform"] == "exact-copy-v1"
	assert records[0]["authored_volume"] == 0.75
	assert records[0]["cooldown_ms"] == 2_000


def test_audio_pack_refuses_to_replace_existing_runtime_audio(tmp_path: Path) -> None:
	repository = tmp_path / "rift"
	source = repository / "sound" / "bark.ogg"
	source.parent.mkdir(parents=True)
	source.write_bytes(b"fixture-ogg")
	output = tmp_path / "audio"
	output.mkdir()
	(output / "voice-bark.ogg").write_bytes(b"existing")

	with pytest.raises(FileExistsError):
		build_audio_pack(
			(AudioSource("voice-bark", "sound/bark.ogg", "voice", 0.75, 2_000),),
			repository,
			output,
			source_revision="fixture",
		)

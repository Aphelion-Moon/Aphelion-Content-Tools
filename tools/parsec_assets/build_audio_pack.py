from __future__ import annotations

import argparse
import json
import shutil
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class AudioSource:
	id: str
	path: str
	channel: str
	authored_volume: float
	cooldown_ms: int


DEFAULT_SOURCES = (
	AudioSource("voice-bark", "modular_nova/modules/emotes/sound/voice/bark1.ogg", "voice", 0.75, 2_000),
	AudioSource("voice-growl", "sound/mobs/non-humanoids/dog/growl1.ogg", "voice", 0.6, 2_500),
	AudioSource("toy-squeak", "sound/items/toy_squeak/toysqueak1.ogg", "effect", 0.55, 900),
	AudioSource("toy-brush", "modular_nova/modules/hairbrush/sounds/brush.ogg", "effect", 0.35, 1_500),
	AudioSource("toy-whistle", "sound/items/whistle/whistle.ogg", "effect", 0.5, 3_000),
	AudioSource("toy-handling", "sound/items/handling/toolbox/toolbox_pickup.ogg", "effect", 0.35, 600),
	AudioSource("radio-alert", "sound/items/radio/radio_receive.ogg", "alert", 0.45, 800),
	AudioSource("rare-idle", "modular_nova/modules/emotes/sound/voice/dgrowl.ogg", "rare-idle", 0.35, 45_000),
)


def build_audio_pack(
	sources: Iterable[AudioSource],
	repository_root: str | Path,
	destination: str | Path,
	*,
	source_revision: str,
) -> list[dict[str, object]]:
	root = Path(repository_root).resolve()
	output = Path(destination)
	ordered = sorted(sources, key=lambda source: source.id)
	if not ordered:
		raise ValueError("At least one audio source is required")
	if len({source.id for source in ordered}) != len(ordered):
		raise ValueError("Audio source IDs must be unique")
	for source in ordered:
		if not 0 < source.authored_volume <= 1:
			raise ValueError(f"{source.id} authored_volume must be greater than 0 and at most 1")
		if source.cooldown_ms < 0:
			raise ValueError(f"{source.id} cooldown_ms must not be negative")
		input_path = root / Path(source.path)
		if not input_path.is_file():
			raise ValueError(f"Audio source does not exist: {input_path}")
		prepared_path = output / f"{source.id}{input_path.suffix.lower()}"
		if prepared_path.exists():
			raise FileExistsError(f"Refusing to replace runtime audio: {prepared_path}")
	metadata_path = output / "parsec-audio.sources.json"
	if metadata_path.exists():
		raise FileExistsError(f"Refusing to replace audio metadata: {metadata_path}")
	output.mkdir(parents=True, exist_ok=True)
	records: list[dict[str, object]] = []
	for source in ordered:
		input_path = root / Path(source.path)
		prepared_path = output / f"{source.id}{input_path.suffix.lower()}"
		shutil.copyfile(input_path, prepared_path)
		records.append({
			**asdict(source),
			"source_revision": source_revision,
			"source_sha256": sha256(input_path.read_bytes()).hexdigest(),
			"output": prepared_path.name,
			"output_sha256": sha256(prepared_path.read_bytes()).hexdigest(),
			"transform": "exact-copy-v1",
		})
	metadata_path.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
	return records


def main() -> int:
	parser = argparse.ArgumentParser(description="Build the frozen exact-copy Parsec audio pack.")
	parser.add_argument("--repository-root", required=True, type=Path)
	parser.add_argument("--output", required=True, type=Path)
	parser.add_argument("--source-revision", required=True)
	args = parser.parse_args()
	records = build_audio_pack(
		DEFAULT_SOURCES,
		args.repository_root,
		args.output,
		source_revision=args.source_revision,
	)
	print(args.output / "parsec-audio.sources.json")
	print(f"Prepared {len(records)} exact-copy cues")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from PIL import Image, PngImagePlugin


@dataclass(frozen=True)
class ComposedFrame:
	path: Path
	source: Path
	source_sha256: str
	sha256: str


@dataclass(frozen=True)
class ComposedClip:
	metadata_path: Path
	frames: tuple[ComposedFrame, ...]


def compose_prepared_clip(
	sources: list[str | Path],
	destination: str | Path,
	*,
	clip: str,
	direction: int = 0,
) -> ComposedClip:
	if not sources:
		raise ValueError("At least one prepared source frame is required")
	output = Path(destination)
	if output.exists() and any(output.iterdir()):
		raise FileExistsError(f"Refusing to overwrite non-empty destination: {output}")
	output.mkdir(parents=True, exist_ok=True)
	frames: list[ComposedFrame] = []
	for frame_index, source in enumerate(sources):
		source_path = Path(source)
		with Image.open(source_path) as image:
			if image.mode != "RGBA" or image.size != (96, 96):
				raise ValueError(f"{source_path} must be a 96x96 RGBA PNG")
			prepared = image.copy()
		source_hash = sha256(source_path.read_bytes()).hexdigest()
		frame_path = output / f"{clip}__d{direction}__f{frame_index}.png"
		metadata = PngImagePlugin.PngInfo()
		metadata.add_text("parsec_composition", "selected-prepared-frames-v1")
		metadata.add_text("parsec_source_sha256", source_hash)
		prepared.save(frame_path, format="PNG", optimize=False, pnginfo=metadata)
		frames.append(ComposedFrame(
			path=frame_path,
			source=source_path,
			source_sha256=source_hash,
			sha256=sha256(frame_path.read_bytes()).hexdigest(),
		))
	metadata_path = output / f"{clip}.composition.json"
	metadata_path.write_text(json.dumps({
		"tool": "selected-prepared-frames-v1",
		"clip": clip,
		"direction": direction,
		"frames": [{
			"path": frame.path.as_posix(),
			"source": frame.source.as_posix(),
			"sourceSha256": frame.source_sha256,
			"sha256": frame.sha256,
		} for frame in frames],
	}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
	return ComposedClip(metadata_path=metadata_path, frames=tuple(frames))


def main() -> int:
	parser = argparse.ArgumentParser(description="Compose a clip from reviewed 96x96 prepared frames.")
	parser.add_argument("--input", required=True, action="append", type=Path)
	parser.add_argument("--output", required=True, type=Path)
	parser.add_argument("--clip", required=True)
	parser.add_argument("--direction", type=int, default=0)
	args = parser.parse_args()
	result = compose_prepared_clip(args.input, args.output, clip=args.clip, direction=args.direction)
	print(result.metadata_path)
	for frame in result.frames:
		print(f"{frame.path}\t{frame.sha256}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

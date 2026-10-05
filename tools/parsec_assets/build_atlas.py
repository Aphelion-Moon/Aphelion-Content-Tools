from __future__ import annotations

import argparse
import json
import math
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, PngImagePlugin

CELL_SIZE = 96


@dataclass(frozen=True)
class AtlasFrame:
	atlas: str
	clip: str
	frame: int
	direction: int
	path: Path


@dataclass(frozen=True)
class AtlasCoordinate:
	x: int
	y: int
	width: int = CELL_SIZE
	height: int = CELL_SIZE


@dataclass(frozen=True)
class AtlasBuild:
	png: Path
	coordinates_path: Path
	coordinates: dict[str, AtlasCoordinate]


def _key(frame: AtlasFrame) -> str:
	return f"{frame.atlas}/{frame.clip}/d{frame.direction}/f{frame.frame}"


def build_atlas(frames: Iterable[AtlasFrame], destination: str | Path, *, name: str = "atlas") -> AtlasBuild:
	ordered = sorted(frames, key=lambda item: (item.atlas, item.clip, item.direction, item.frame, item.path.as_posix()))
	if not ordered:
		raise ValueError("At least one prepared frame is required")
	keys = [_key(frame) for frame in ordered]
	if len(keys) != len(set(keys)):
		raise ValueError("Prepared frame keys must be unique")
	columns = min(8, math.ceil(math.sqrt(len(ordered))))
	rows = math.ceil(len(ordered) / columns)
	atlas = Image.new("RGBA", (columns * CELL_SIZE, rows * CELL_SIZE), (0, 0, 0, 0))
	coordinates: dict[str, AtlasCoordinate] = {}
	for index, source in enumerate(ordered):
		with Image.open(source.path) as image:
			if image.mode != "RGBA" or image.size != (CELL_SIZE, CELL_SIZE):
				raise ValueError(f"{source.path} must be a 96x96 RGBA PNG")
			column = index % columns
			row = index // columns
			x = column * CELL_SIZE
			y = row * CELL_SIZE
			atlas.paste(image, (x, y))
			coordinates[_key(source)] = AtlasCoordinate(x=x, y=y)
	output = Path(destination)
	output.mkdir(parents=True, exist_ok=True)
	png_path = output / f"{name}.png"
	coordinates_path = output / f"{name}.json"
	metadata = PngImagePlugin.PngInfo()
	metadata.add_text("parsec_atlas", "deterministic-v1")
	atlas.save(png_path, format="PNG", optimize=False, pnginfo=metadata)
	coordinates_path.write_text(
		json.dumps({key: asdict(value) for key, value in coordinates.items()}, indent=2, sort_keys=True) + "\n",
		encoding="utf-8",
	)
	return AtlasBuild(png=png_path, coordinates_path=coordinates_path, coordinates=coordinates)


def main() -> int:
	parser = argparse.ArgumentParser(description="Pack prepared 96x96 PNG frames without resampling.")
	parser.add_argument("--input", required=True, type=Path)
	parser.add_argument("--output", required=True, type=Path)
	parser.add_argument("--atlas", required=True)
	parser.add_argument("--name", default="atlas")
	args = parser.parse_args()
	frames: list[AtlasFrame] = []
	for path in sorted(args.input.rglob("*.png")):
		parts = path.stem.split("__")
		if len(parts) != 3 or not parts[1].startswith("d") or not parts[2].startswith("f"):
			raise ValueError(f"Expected <clip>__d<direction>__f<frame>.png: {path}")
		frames.append(AtlasFrame(args.atlas, parts[0], int(parts[2][1:]), int(parts[1][1:]), path))
	result = build_atlas(frames, args.output, name=args.name)
	print(result.png)
	print(result.coordinates_path)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from PIL import Image, PngImagePlugin


@dataclass(frozen=True)
class PreparedObjectFrame:
	path: Path
	source_size: tuple[int, int]
	source_bounds: tuple[int, int, int, int]
	occupied_size: tuple[int, int]
	offset: tuple[int, int]
	scale: int
	baseline_y: int
	sha256: str


def prepare_object_frame(
	source: str | Path,
	destination: str | Path,
	*,
	scale: int = 3,
	baseline_y: int = 90,
) -> PreparedObjectFrame:
	if scale <= 0:
		raise ValueError("scale must be positive")
	if not 0 <= baseline_y <= 96:
		raise ValueError("baseline_y must be between 0 and 96")
	input_path = Path(source)
	output_path = Path(destination)
	with Image.open(input_path) as image:
		rgba = image.convert("RGBA")
		source_bounds = rgba.getchannel("A").getbbox()
		if source_bounds is None:
			raise ValueError(f"{input_path} has no occupied pixels")
		cropped = rgba.crop(source_bounds)
		occupied_size = (cropped.width * scale, cropped.height * scale)
		if occupied_size[0] > 96 or occupied_size[1] > 96:
			raise ValueError(f"{input_path} cannot fit in a 96x96 cell at scale {scale}")
		offset = ((96 - occupied_size[0]) // 2, baseline_y - occupied_size[1])
		if offset[1] < 0:
			raise ValueError(f"{input_path} cannot fit above baseline {baseline_y} at scale {scale}")
		scaled = cropped.resize(occupied_size, Image.Resampling.NEAREST)
		prepared = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
		prepared.alpha_composite(scaled, offset)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	metadata = PngImagePlugin.PngInfo()
	metadata.add_text("parsec_preparation", "alpha-crop-nearest-scale-baseline-v2")
	metadata.add_text("parsec_source", input_path.as_posix())
	metadata.add_text("parsec_scale", str(scale))
	metadata.add_text("parsec_baseline_y", str(baseline_y))
	prepared.save(output_path, format="PNG", optimize=False, pnginfo=metadata)
	return PreparedObjectFrame(
		path=output_path,
		source_size=rgba.size,
		source_bounds=source_bounds,
		occupied_size=occupied_size,
		offset=offset,
		scale=scale,
		baseline_y=baseline_y,
		sha256=sha256(output_path.read_bytes()).hexdigest(),
	)


def main() -> int:
	parser = argparse.ArgumentParser(description="Crop and scale an extracted SS13 object onto a 96x96 cell.")
	parser.add_argument("source", type=Path)
	parser.add_argument("destination", type=Path)
	parser.add_argument("--scale", type=int, default=3)
	parser.add_argument("--baseline-y", type=int, default=90)
	args = parser.parse_args()
	result = prepare_object_frame(args.source, args.destination, scale=args.scale, baseline_y=args.baseline_y)
	print(f"{result.path}\t{result.sha256}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

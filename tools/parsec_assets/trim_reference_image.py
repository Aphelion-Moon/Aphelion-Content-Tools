from __future__ import annotations

import argparse
import json
from collections import deque
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class TrimmedReference:
	source: Path
	destination: Path
	metadata_path: Path
	source_size: tuple[int, int]
	crop: tuple[int, int, int, int]
	occupied_bbox: tuple[int, int, int, int]
	retained_margin: tuple[int, int, int, int]
	source_sha256: str
	output_sha256: str


def _is_background_candidate(pixel: tuple[int, int, int, int]) -> bool:
	red, green, blue, alpha = pixel
	return alpha == 0 or (
		min(red, green, blue) >= 220
		and max(red, green, blue) - min(red, green, blue) <= 12
	)


def _occupied_bbox(image: Image.Image) -> tuple[int, int, int, int]:
	rgba = image.convert("RGBA")
	width, height = rgba.size
	pixels = rgba.load()
	background = bytearray(width * height)
	pending: deque[int] = deque()

	def add(x: int, y: int) -> None:
		position = y * width + x
		if background[position] or not _is_background_candidate(pixels[x, y]):
			return
		background[position] = 1
		pending.append(position)

	for x in range(width):
		add(x, 0)
		add(x, height - 1)
	for y in range(1, height - 1):
		add(0, y)
		add(width - 1, y)

	while pending:
		position = pending.popleft()
		x = position % width
		y = position // width
		if x:
			add(x - 1, y)
		if x + 1 < width:
			add(x + 1, y)
		if y:
			add(x, y - 1)
		if y + 1 < height:
			add(x, y + 1)

	occupied = Image.new("1", (width, height), 0)
	occupied.putdata([not is_background for is_background in background])
	bbox = occupied.getbbox()
	if bbox is None:
		raise ValueError("reference contains no occupied artwork")
	return bbox


def trim_reference_image(
	source: str | Path,
	destination: str | Path,
	*,
	crop: tuple[int, int, int, int],
	minimum_margin: int = 8,
) -> TrimmedReference:
	if minimum_margin < 0:
		raise ValueError("minimum_margin cannot be negative")
	source_path = Path(source)
	destination_path = Path(destination)
	metadata_path = destination_path.with_suffix(".trim.json")
	if destination_path.exists() or metadata_path.exists():
		raise FileExistsError(f"Refusing to overwrite an existing trimmed reference: {destination_path}")

	with Image.open(source_path) as source_image:
		source_image.load()
		source_size = source_image.size
		left, top, right, bottom = crop
		if not (0 <= left < right <= source_image.width and 0 <= top < bottom <= source_image.height):
			raise ValueError(f"crop {crop} is outside source bounds {source_image.size}")
		occupied_bbox = _occupied_bbox(source_image)
		occupied_left, occupied_top, occupied_right, occupied_bottom = occupied_bbox
		retained_margin = (
			occupied_left - left,
			occupied_top - top,
			right - occupied_right,
			bottom - occupied_bottom,
		)
		if min(retained_margin) < 0:
			raise ValueError(
				f"manual crop {crop} cuts occupied artwork at {occupied_bbox}",
			)
		if min(retained_margin) < minimum_margin:
			raise ValueError(
				f"manual crop retains margins {retained_margin}; each must be at least {minimum_margin} pixels",
			)
		trimmed = source_image.crop(crop)
		destination_path.parent.mkdir(parents=True, exist_ok=True)
		trimmed.save(destination_path, format="PNG", optimize=False)

	source_hash = sha256(source_path.read_bytes()).hexdigest()
	output_hash = sha256(destination_path.read_bytes()).hexdigest()
	metadata_path.write_text(json.dumps({
		"tool": "manual-reference-trim-v1",
		"source": source_path.as_posix(),
		"sourceSha256": source_hash,
		"sourceSize": list(source_size),
		"destination": destination_path.as_posix(),
		"outputSha256": output_hash,
		"outputSize": [crop[2] - crop[0], crop[3] - crop[1]],
		"crop": list(crop),
		"occupiedBounds": list(occupied_bbox),
		"retainedMargin": list(retained_margin),
		"minimumMargin": minimum_margin,
	}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
	return TrimmedReference(
		source=source_path,
		destination=destination_path,
		metadata_path=metadata_path,
		source_size=source_size,
		crop=crop,
		occupied_bbox=occupied_bbox,
		retained_margin=retained_margin,
		source_sha256=source_hash,
		output_sha256=output_hash,
	)


def main() -> int:
	parser = argparse.ArgumentParser(description="Apply a reviewed manual crop to a Parsec generation reference.")
	parser.add_argument("--input", required=True, type=Path)
	parser.add_argument("--output", required=True, type=Path)
	parser.add_argument("--crop", required=True, nargs=4, type=int, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
	parser.add_argument("--minimum-margin", type=int, default=8)
	args = parser.parse_args()
	result = trim_reference_image(
		args.input,
		args.output,
		crop=tuple(args.crop),
		minimum_margin=args.minimum_margin,
	)
	print(result.metadata_path)
	print(f"occupied={result.occupied_bbox}")
	print(f"retained-margin={result.retained_margin}")
	print(f"sha256={result.output_sha256}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

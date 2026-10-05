"""Apply reviewed pixel edits against an immutable, hash-bound source image."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

from PIL import Image, PngImagePlugin


def apply_pixel_touchup(
	source: str | Path,
	destination: str | Path,
	*,
	source_sha256: str,
	edits: list[dict[str, Any]],
	reason: str,
) -> str:
	source_path, output_path = Path(source), Path(destination)
	if output_path.exists():
		raise FileExistsError(f"Refusing to overwrite destination: {output_path}")
	if sha256(source_path.read_bytes()).hexdigest() != source_sha256:
		raise ValueError("Pixel touchup source hash does not match the reviewed image")
	if not reason.strip():
		raise ValueError("A pixel touchup reason is required")
	with Image.open(source_path) as opened:
		if opened.mode != "RGBA":
			raise ValueError("Pixel touchups require an RGBA source")
		image = opened.copy()
	seen = set()
	for edit in edits:
		point, before, after = edit["point"], edit["before"], edit["after"]
		if len(point) != 2 or any(type(value) is not int for value in point):
			raise ValueError("Pixel coordinates must be two integers")
		x, y = point
		if not (0 <= x < image.width and 0 <= y < image.height) or (x, y) in seen:
			raise ValueError("Pixel coordinates are outside the image or duplicated")
		for color in (before, after):
			if len(color) != 4 or any(type(value) is not int or not 0 <= value <= 255 for value in color):
				raise ValueError("Pixel colors must be four byte values")
		if image.getpixel((x, y)) != tuple(before):
			raise ValueError(f"Reviewed source pixel no longer matches at {(x, y)}")
		seen.add((x, y))
	# Validate every edit before writing anything.
	for edit in edits:
		image.putpixel(tuple(edit["point"]), tuple(edit["after"]))
	metadata = PngImagePlugin.PngInfo()
	metadata.add_text("parsec_transform", "reviewed-pixel-touchup-v1")
	metadata.add_text("parsec_source_sha256", source_sha256)
	metadata.add_text("parsec_transform_reason", reason.strip())
	output_path.parent.mkdir(parents=True, exist_ok=True)
	image.save(output_path, format="PNG", optimize=False, pnginfo=metadata)
	return sha256(output_path.read_bytes()).hexdigest()

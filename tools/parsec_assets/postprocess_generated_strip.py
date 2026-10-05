from __future__ import annotations

import argparse
import json
from collections import deque
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from PIL import Image, PngImagePlugin

from tools.parsec_assets.transform_prepared_frame import enforce_dark_silhouette_outline

CELL_SIZE = 96
SUPERMATTER_YELLOW = (251, 212, 54, 255)
NEON_PINK = (255, 60, 200, 255)
TONGUE_CORAL = (240, 96, 96, 255)
SCENT_CYAN = (80, 220, 235, 255)


@dataclass(frozen=True)
class PostprocessedFrame:
	path: Path
	source_bbox: tuple[int, int, int, int]
	resized_size: tuple[int, int]
	offset: tuple[int, int]
	sha256: str


@dataclass(frozen=True)
class PostprocessedStrip:
	source: Path
	source_sha256: str
	metadata_path: Path
	frames: tuple[PostprocessedFrame, ...]


def _is_background_candidate(pixel: tuple[int, int, int, int]) -> bool:
	red, green, blue, alpha = pixel
	return alpha == 0 or (min(red, green, blue) >= 220 and max(red, green, blue) - min(red, green, blue) <= 12)


def _is_identity_pink(pixel: tuple[int, int, int, int]) -> bool:
	red, green, blue, alpha = pixel
	return alpha > 0 and red >= 180 and blue >= 100 and green <= 140 and red + blue >= green * 3


def _is_identity_yellow(pixel: tuple[int, int, int, int]) -> bool:
	red, green, blue, alpha = pixel
	return alpha > 0 and red >= 180 and green >= 140 and blue <= 110 and red + green >= blue * 4


def _is_tongue_coral(pixel: tuple[int, int, int, int]) -> bool:
	red, green, blue, alpha = pixel
	return alpha > 0 and red >= 160 and 30 <= green <= 160 and blue <= 160 and red >= green + 60 and red >= blue + 50


def _is_scent_cyan(pixel: tuple[int, int, int, int]) -> bool:
	red, green, blue, alpha = pixel
	return alpha > 0 and red <= 120 and green >= 150 and blue >= 170 and blue >= red + 80


def _upper_identity_points(
	image: Image.Image,
	predicate,
) -> list[tuple[int, int]]:
	candidates = [
		(x, y)
		for y in range(image.height)
		for x in range(image.width)
		if predicate(image.getpixel((x, y)))
	]
	if not candidates:
		return []
	cutoff_y = min(y for _, y in candidates) + max(4, round(image.height * 0.12))
	return [(x, y) for x, y in candidates if y <= cutoff_y]


def _detect_frame_ranges(
	isolated: Image.Image,
	expected_frames: int,
	*,
	keep_auxiliary_components: bool,
) -> list[tuple[int, int]]:
	width, height = isolated.size
	alpha = isolated.getchannel("A").tobytes()
	column_occupancy = [
		sum(1 for y in range(height) if alpha[y * width + x])
		for x in range(width)
	]
	runs: list[tuple[int, int, int]] = []
	start: int | None = None
	for x, occupancy in enumerate(column_occupancy + [0]):
		if occupancy and start is None:
			start = x
		elif not occupancy and start is not None:
			runs.append((start, x, sum(column_occupancy[start:x])))
			start = None
	if not runs:
		raise ValueError("frame slot 0 has no foreground")
	largest_area = max(area for _, _, area in runs)
	significant = [(start, end) for start, end, area in runs if area >= max(8, largest_area * 0.02)]
	if len(significant) != expected_frames:
		raise ValueError(
			f"expected {expected_frames} separated frame silhouettes, found {len(significant)}; regenerate rather than split artwork",
		)
	if not keep_auxiliary_components:
		return significant
	panel_boundaries = [0]
	for (_, previous_end), (next_start, _) in zip(significant, significant[1:], strict=False):
		panel_boundaries.append((previous_end + next_start) // 2)
	panel_boundaries.append(width)
	return list(zip(panel_boundaries, panel_boundaries[1:], strict=False))


def _equal_panel_ranges(width: int, expected_frames: int) -> list[tuple[int, int]]:
	return [
		(round(index * width / expected_frames), round((index + 1) * width / expected_frames))
		for index in range(expected_frames)
	]


def _connected_background(image: Image.Image) -> bytearray:
	width, height = image.size
	pixels = image.load()
	background = bytearray(width * height)
	queue: deque[int] = deque()

	def add(x: int, y: int) -> None:
		position = y * width + x
		if background[position] or not _is_background_candidate(pixels[x, y]):
			return
		background[position] = 1
		queue.append(position)

	for x in range(width):
		add(x, 0)
		add(x, height - 1)
	for y in range(1, height - 1):
		add(0, y)
		add(width - 1, y)

	while queue:
		position = queue.popleft()
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
	return background


def _isolate_foreground(
	image: Image.Image,
	expected_frames: int,
	*,
	keep_auxiliary_components: bool = False,
	equal_panel_split: bool = False,
) -> tuple[Image.Image, list[tuple[int, int]]]:
	rgba = image.convert("RGBA")
	background = _connected_background(rgba)
	alpha = rgba.getchannel("A")
	alpha_data = bytearray(alpha.tobytes())
	for position, is_background in enumerate(background):
		if is_background:
			alpha_data[position] = 0
	rgba.putalpha(Image.frombytes("L", rgba.size, bytes(alpha_data)))
	frame_ranges = _equal_panel_ranges(rgba.width, expected_frames) if equal_panel_split else _detect_frame_ranges(
		rgba,
		expected_frames,
		keep_auxiliary_components=keep_auxiliary_components,
	)
	# Exterior white must stay transparent. A convex head hull cannot distinguish
	# white fur from the open space below a muzzle or behind an ear. Repair any
	# open coat outlines explicitly in the source instead of guessing a fill.
	return rgba, frame_ranges


def _normalize_palette(image: Image.Image, colors: int) -> Image.Image:
	pink_mask = [False] * (image.width * image.height)
	for x, y in _upper_identity_points(image, _is_identity_pink):
		pink_mask[y * image.width + x] = True
	yellow_mask = [False] * (image.width * image.height)
	for x, y in _upper_identity_points(image, _is_identity_yellow):
		yellow_mask[y * image.width + x] = True
	coral_mask = [_is_tongue_coral(pixel) for pixel in image.getdata()]
	scent_mask = [_is_scent_cyan(pixel) for pixel in image.getdata()]
	alpha = image.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
	backing = Image.new("RGB", image.size, (0, 0, 0))
	backing.paste(image.convert("RGB"), (0, 0), alpha)
	quantized = backing.quantize(
		colors=colors,
		method=Image.Quantize.MEDIANCUT,
		dither=Image.Dither.NONE,
	).convert("RGBA")
	quantized.putalpha(alpha)
	normalized: list[tuple[int, int, int, int]] = []
	for index, (red, green, blue, pixel_alpha) in enumerate(quantized.getdata()):
		if pixel_alpha == 0:
			normalized.append((0, 0, 0, 0))
		elif pink_mask[index]:
			normalized.append(NEON_PINK)
		elif yellow_mask[index]:
			normalized.append(SUPERMATTER_YELLOW)
		elif coral_mask[index]:
			normalized.append(TONGUE_CORAL)
		elif scent_mask[index]:
			normalized.append(SCENT_CYAN)
		elif min(red, green, blue) >= 245 and max(red, green, blue) - min(red, green, blue) <= 10:
			normalized.append((255, 255, 255, 255))
		elif max(red, green, blue) <= 12:
			normalized.append((0, 0, 0, 255))
		else:
			normalized.append((red, green, blue, 255))
	quantized.putdata(normalized)
	return quantized


def _keep_largest_alpha_component(image: Image.Image) -> Image.Image:
	alpha = image.getchannel("A")
	remaining = {
		(x, y)
		for y in range(image.height)
		for x in range(image.width)
		if alpha.getpixel((x, y))
	}
	components: list[list[tuple[int, int]]] = []
	while remaining:
		start = remaining.pop()
		component = [start]
		queue = deque([start])
		while queue:
			x, y = queue.popleft()
			for next_y in range(max(0, y - 1), min(image.height, y + 2)):
				for next_x in range(max(0, x - 1), min(image.width, x + 2)):
					point = (next_x, next_y)
					if point in remaining:
						remaining.remove(point)
						component.append(point)
						queue.append(point)
		components.append(component)
	if len(components) <= 1:
		return image
	largest = set(max(components, key=len))
	result = image.copy()
	result_alpha = result.getchannel("A")
	result_alpha.putdata([
		value if (index % image.width, index // image.width) in largest else 0
		for index, value in enumerate(result_alpha.getdata())
	])
	result.putalpha(result_alpha)
	return result


def postprocess_generated_strip(
	source: str | Path,
	destination: str | Path,
	*,
	clip: str,
	expected_frames: int,
	direction: int = 0,
	max_art_width: int = 84,
	max_art_height: int = 84,
	baseline_y: int = 88,
	palette_colors: int = 24,
	scale_override: float | None = None,
	keep_auxiliary_components: bool = False,
	equal_panel_split: bool = False,
) -> PostprocessedStrip:
	if expected_frames < 1:
		raise ValueError("expected_frames must be positive")
	if not 1 <= max_art_width <= CELL_SIZE or not 1 <= max_art_height <= CELL_SIZE:
		raise ValueError("art bounds must fit within the 96x96 logical canvas")
	if not 0 <= baseline_y < CELL_SIZE:
		raise ValueError("baseline_y must be inside the 96x96 logical canvas")
	if not 2 <= palette_colors <= 256:
		raise ValueError("palette_colors must be between 2 and 256")
	if scale_override is not None and scale_override <= 0:
		raise ValueError("scale_override must be positive")

	source_path = Path(source)
	output = Path(destination)
	if output.exists() and any(output.iterdir()):
		raise FileExistsError(f"Refusing to overwrite non-empty destination: {output}")
	output.mkdir(parents=True, exist_ok=True)
	with Image.open(source_path) as source_image:
		isolated, frame_ranges = _isolate_foreground(
			source_image,
			expected_frames,
			keep_auxiliary_components=keep_auxiliary_components,
			equal_panel_split=equal_panel_split,
		)
	width, height = isolated.size
	frame_sources: list[tuple[int, tuple[int, int, int, int], Image.Image]] = []
	for frame_index, (x_start, x_end) in enumerate(frame_ranges):
		slot = isolated.crop((x_start, 0, x_end, height))
		if not keep_auxiliary_components:
			slot = _keep_largest_alpha_component(slot)
		bbox = slot.getchannel("A").getbbox()
		if bbox is None:
			raise ValueError(f"frame slot {frame_index} has no foreground")
		frame_sources.append((x_start, bbox, slot.crop(bbox)))
	fit_scale = min(
		max_art_width / max(cropped.width for _, _, cropped in frame_sources),
		max_art_height / max(cropped.height for _, _, cropped in frame_sources),
	)
	clip_scale = scale_override if scale_override is not None else fit_scale
	if any(
		round(cropped.width * clip_scale) > max_art_width or round(cropped.height * clip_scale) > max_art_height
		for _, _, cropped in frame_sources
	):
		raise ValueError("scale_override exceeds the declared art bounds")
	frames: list[PostprocessedFrame] = []
	for frame_index, (x_start, bbox, cropped) in enumerate(frame_sources):
		resized_size = (
			max(1, round(cropped.width * clip_scale)),
			max(1, round(cropped.height * clip_scale)),
		)
		resized = cropped.resize(resized_size, resample=Image.Resampling.NEAREST)
		resized = _normalize_palette(resized, palette_colors)
		resized = enforce_dark_silhouette_outline(resized)
		offset = ((CELL_SIZE - resized.width) // 2, baseline_y - resized.height + 1)
		if offset[1] < 0:
			raise ValueError(f"frame slot {frame_index} cannot fit above baseline {baseline_y}")
		prepared = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
		prepared.alpha_composite(resized, offset)
		frame_path = output / f"{clip}__d{direction}__f{frame_index}.png"
		metadata = PngImagePlugin.PngInfo()
		metadata.add_text("parsec_postprocess", "generated-strip-v4")
		metadata.add_text("parsec_source_sha256", sha256(source_path.read_bytes()).hexdigest())
		prepared.save(frame_path, format="PNG", optimize=False, pnginfo=metadata)
		frames.append(PostprocessedFrame(
			path=frame_path,
			source_bbox=(x_start + bbox[0], bbox[1], x_start + bbox[2], bbox[3]),
			resized_size=resized_size,
			offset=offset,
			sha256=sha256(frame_path.read_bytes()).hexdigest(),
		))

	source_hash = sha256(source_path.read_bytes()).hexdigest()
	metadata_path = output / f"{clip}.postprocess.json"
	metadata_path.write_text(json.dumps({
		"tool": "generated-strip-v4",
		"source": source_path.as_posix(),
		"sourceSha256": source_hash,
		"clip": clip,
		"direction": direction,
		"logicalCanvas": [CELL_SIZE, CELL_SIZE],
		"maxArtSize": [max_art_width, max_art_height],
		"clipScale": clip_scale,
		"scaleMode": "explicit" if scale_override is not None else "fit-clip",
		"auxiliaryComponents": keep_auxiliary_components,
		"frameSplit": "equal-panels" if equal_panel_split else "separated-silhouettes",
		"baselineY": baseline_y,
		"paletteColors": palette_colors,
		"identityPalette": {
			"leftEye": f"#{SUPERMATTER_YELLOW[0]:02X}{SUPERMATTER_YELLOW[1]:02X}{SUPERMATTER_YELLOW[2]:02X}",
			"rightEye": f"#{NEON_PINK[0]:02X}{NEON_PINK[1]:02X}{NEON_PINK[2]:02X}",
			"laterality": "anatomical",
		},
		"frames": [{
			**asdict(frame),
			"path": frame.path.as_posix(),
		} for frame in frames],
	}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
	return PostprocessedStrip(
		source=source_path,
		source_sha256=source_hash,
		metadata_path=metadata_path,
		frames=tuple(frames),
	)


def main() -> int:
	parser = argparse.ArgumentParser(description="Prepare a generated horizontal sprite strip for Parsec atlases.")
	parser.add_argument("--input", required=True, type=Path)
	parser.add_argument("--output", required=True, type=Path)
	parser.add_argument("--clip", required=True)
	parser.add_argument("--expected-frames", required=True, type=int)
	parser.add_argument("--direction", type=int, default=0)
	parser.add_argument("--max-art-width", type=int, default=84)
	parser.add_argument("--max-art-height", type=int, default=84)
	parser.add_argument("--baseline-y", type=int, default=88)
	parser.add_argument("--palette-colors", type=int, default=24)
	parser.add_argument("--scale", type=float)
	parser.add_argument("--keep-auxiliary-components", action="store_true")
	parser.add_argument("--equal-panel-split", action="store_true")
	args = parser.parse_args()
	result = postprocess_generated_strip(
		args.input,
		args.output,
		clip=args.clip,
		expected_frames=args.expected_frames,
		direction=args.direction,
		max_art_width=args.max_art_width,
		max_art_height=args.max_art_height,
		baseline_y=args.baseline_y,
		palette_colors=args.palette_colors,
		scale_override=args.scale,
		keep_auxiliary_components=args.keep_auxiliary_components,
		equal_panel_split=args.equal_panel_split,
	)
	print(result.metadata_path)
	for frame in result.frames:
		print(f"{frame.path}\t{frame.sha256}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

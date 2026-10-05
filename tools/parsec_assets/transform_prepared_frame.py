from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from PIL import Image, PngImagePlugin

PRESERVED_ACCENT_COLORS = {
	(251, 212, 54, 255),
	(255, 60, 200, 255),
	(240, 96, 96, 255),
	(80, 220, 235, 255),
}


@dataclass(frozen=True)
class TransformedFrame:
	path: Path
	source: Path
	source_sha256: str
	sha256: str


def _load_prepared_frame(source_path: Path) -> Image.Image:
	with Image.open(source_path) as image:
		if image.mode != "RGBA" or image.size != (96, 96):
			raise ValueError(f"{source_path} must be a 96x96 RGBA PNG")
		return image.copy()


def enforce_dark_silhouette_outline(image: Image.Image) -> Image.Image:
	"""Return an image whose largest opaque component has one dark exterior pixel boundary."""
	if image.mode != "RGBA":
		raise ValueError("Silhouette outlining requires an RGBA image")
	pixels = image.load()
	remaining = {
		(x, y)
		for y in range(image.height)
		for x in range(image.width)
		if pixels[x, y][3]
	}
	components: list[set[tuple[int, int]]] = []
	while remaining:
		start = remaining.pop()
		component = {start}
		pending = deque([start])
		while pending:
			x, y = pending.popleft()
			for next_y in range(max(0, y - 1), min(image.height, y + 2)):
				for next_x in range(max(0, x - 1), min(image.width, x + 2)):
					point = (next_x, next_y)
					if point in remaining:
						remaining.remove(point)
						component.add(point)
						pending.append(point)
		components.append(component)
	if not components:
		return image.copy()
	main_subject = max(components, key=len)
	outlined = image.copy()
	outlined_pixels = outlined.load()
	for x, y in main_subject:
		is_boundary = x == 0 or y == 0 or x == image.width - 1 or y == image.height - 1
		if not is_boundary:
			is_boundary = any(
				(next_x, next_y) not in main_subject
				for next_y in range(y - 1, y + 2)
				for next_x in range(x - 1, x + 2)
			)
		if is_boundary and outlined_pixels[x, y] not in PRESERVED_ACCENT_COLORS:
			outlined_pixels[x, y] = (0, 0, 0, 255)
	return outlined


def outline_prepared_frame(
	source: str | Path,
	destination: str | Path,
	*,
	reason: str,
) -> TransformedFrame:
	if not reason.strip():
		raise ValueError("A repair reason is required")
	source_path = Path(source)
	output_path = Path(destination)
	if output_path.exists():
		raise FileExistsError(f"Refusing to overwrite destination: {output_path}")
	prepared = enforce_dark_silhouette_outline(_load_prepared_frame(source_path))
	output_path.parent.mkdir(parents=True, exist_ok=True)
	source_hash = sha256(source_path.read_bytes()).hexdigest()
	metadata = PngImagePlugin.PngInfo()
	metadata.add_text("parsec_transform", "dark-silhouette-outline-v1")
	metadata.add_text("parsec_source_sha256", source_hash)
	metadata.add_text("parsec_transform_reason", reason.strip())
	prepared.save(output_path, format="PNG", optimize=False, pnginfo=metadata)
	return TransformedFrame(
		path=output_path,
		source=source_path,
		source_sha256=source_hash,
		sha256=sha256(output_path.read_bytes()).hexdigest(),
	)


def flip_prepared_frame(source: str | Path, destination: str | Path) -> TransformedFrame:
	source_path = Path(source)
	output_path = Path(destination)
	if output_path.exists():
		raise FileExistsError(f"Refusing to overwrite destination: {output_path}")
	image = _load_prepared_frame(source_path)
	flipped = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	source_hash = sha256(source_path.read_bytes()).hexdigest()
	metadata = PngImagePlugin.PngInfo()
	metadata.add_text("parsec_transform", "horizontal-flip-v1")
	metadata.add_text("parsec_source_sha256", source_hash)
	flipped.save(output_path, format="PNG", optimize=False, pnginfo=metadata)
	return TransformedFrame(
		path=output_path,
		source=source_path,
		source_sha256=source_hash,
		sha256=sha256(output_path.read_bytes()).hexdigest(),
	)


def erase_prepared_frame_rectangles(
	source: str | Path,
	destination: str | Path,
	*,
	rectangles: list[tuple[int, int, int, int]],
	reason: str,
) -> TransformedFrame:
	if not rectangles:
		raise ValueError("At least one erase rectangle is required")
	if not reason.strip():
		raise ValueError("A repair reason is required")
	source_path = Path(source)
	output_path = Path(destination)
	if output_path.exists():
		raise FileExistsError(f"Refusing to overwrite destination: {output_path}")
	prepared = _load_prepared_frame(source_path)
	for left, top, right, bottom in rectangles:
		if not (0 <= left < right <= prepared.width and 0 <= top < bottom <= prepared.height):
			raise ValueError(f"Invalid erase rectangle: {(left, top, right, bottom)}")
		for y in range(top, bottom):
			for x in range(left, right):
				prepared.putpixel((x, y), (0, 0, 0, 0))
	output_path.parent.mkdir(parents=True, exist_ok=True)
	source_hash = sha256(source_path.read_bytes()).hexdigest()
	metadata = PngImagePlugin.PngInfo()
	metadata.add_text("parsec_transform", "localized-alpha-erase-v1")
	metadata.add_text("parsec_source_sha256", source_hash)
	metadata.add_text("parsec_transform_reason", reason.strip())
	metadata.add_text(
		"parsec_transform_rectangles",
		";".join(",".join(str(value) for value in rectangle) for rectangle in rectangles),
	)
	prepared.save(output_path, format="PNG", optimize=False, pnginfo=metadata)
	return TransformedFrame(
		path=output_path,
		source=source_path,
		source_sha256=source_hash,
		sha256=sha256(output_path.read_bytes()).hexdigest(),
	)


def replace_prepared_frame_color_in_rectangles(
	source: str | Path,
	destination: str | Path,
	*,
	rectangles: list[tuple[int, int, int, int]],
	source_color: tuple[int, int, int, int],
	target_color: tuple[int, int, int, int],
	reason: str,
) -> TransformedFrame:
	if not rectangles:
		raise ValueError("At least one replacement rectangle is required")
	if not reason.strip():
		raise ValueError("A repair reason is required")
	source_path = Path(source)
	output_path = Path(destination)
	if output_path.exists():
		raise FileExistsError(f"Refusing to overwrite destination: {output_path}")
	prepared = _load_prepared_frame(source_path)
	replaced = 0
	for left, top, right, bottom in rectangles:
		if not (0 <= left < right <= prepared.width and 0 <= top < bottom <= prepared.height):
			raise ValueError(f"Invalid replacement rectangle: {(left, top, right, bottom)}")
		for y in range(top, bottom):
			for x in range(left, right):
				if prepared.getpixel((x, y)) == source_color:
					prepared.putpixel((x, y), target_color)
					replaced += 1
	if replaced == 0:
		raise ValueError("No matching source-color pixels found inside replacement rectangles")
	output_path.parent.mkdir(parents=True, exist_ok=True)
	source_hash = sha256(source_path.read_bytes()).hexdigest()
	metadata = PngImagePlugin.PngInfo()
	metadata.add_text("parsec_transform", "localized-color-replacement-v1")
	metadata.add_text("parsec_source_sha256", source_hash)
	metadata.add_text("parsec_transform_reason", reason.strip())
	metadata.add_text(
		"parsec_transform_rectangles",
		";".join(",".join(str(value) for value in rectangle) for rectangle in rectangles),
	)
	metadata.add_text("parsec_transform_source_color", ",".join(str(value) for value in source_color))
	metadata.add_text("parsec_transform_target_color", ",".join(str(value) for value in target_color))
	metadata.add_text("parsec_transform_replaced_pixels", str(replaced))
	prepared.save(output_path, format="PNG", optimize=False, pnginfo=metadata)
	return TransformedFrame(
		path=output_path,
		source=source_path,
		source_sha256=source_hash,
		sha256=sha256(output_path.read_bytes()).hexdigest(),
	)


def _parse_rectangle(value: str) -> tuple[int, int, int, int]:
	parts = value.split(",")
	if len(parts) != 4:
		raise argparse.ArgumentTypeError("rectangle must be left,top,right,bottom")
	try:
		return tuple(int(part) for part in parts)  # type: ignore[return-value]
	except ValueError as error:
		raise argparse.ArgumentTypeError("rectangle values must be integers") from error


def main() -> int:
	parser = argparse.ArgumentParser(description="Apply a recorded transform to a prepared 96x96 frame.")
	parser.add_argument("source", type=Path)
	parser.add_argument("destination", type=Path)
	parser.add_argument("--erase-rectangle", action="append", type=_parse_rectangle, default=[])
	parser.add_argument("--dark-outline", action="store_true")
	parser.add_argument("--reason")
	args = parser.parse_args()
	if args.dark_outline:
		if args.reason is None:
			parser.error("--reason is required with --dark-outline")
		result = outline_prepared_frame(args.source, args.destination, reason=args.reason)
	elif args.erase_rectangle:
		if args.reason is None:
			parser.error("--reason is required with --erase-rectangle")
		result = erase_prepared_frame_rectangles(
			args.source,
			args.destination,
			rectangles=args.erase_rectangle,
			reason=args.reason,
		)
	else:
		result = flip_prepared_frame(args.source, args.destination)
	print(f"{result.path}\t{result.sha256}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

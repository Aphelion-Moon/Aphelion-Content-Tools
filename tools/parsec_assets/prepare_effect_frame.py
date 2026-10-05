from __future__ import annotations

import argparse
import json
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from PIL import Image, PngImagePlugin

CANVAS_SIZE = 96


@dataclass(frozen=True)
class PreparedEffectFrame:
	path: Path
	transform: str
	selected_pixels: int
	sha256: str


def _components(image: Image.Image) -> list[list[tuple[int, int]]]:
	remaining = {
		(x, y)
		for y in range(image.height)
		for x in range(image.width)
		if image.getpixel((x, y))[3]
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
	return components


def _load_rgba(source: str | Path) -> tuple[Path, Image.Image]:
	path = Path(source)
	with Image.open(path) as opened:
		return path, opened.convert("RGBA")


def _save(
	image: Image.Image,
	source: Path,
	destination: str | Path,
	*,
	transform: str,
	selected_pixels: int,
	parameters: dict[str, object] | None = None,
) -> PreparedEffectFrame:
	if selected_pixels <= 0:
		raise ValueError(f"{source} produced no effect pixels")
	path = Path(destination)
	path.parent.mkdir(parents=True, exist_ok=True)
	metadata = PngImagePlugin.PngInfo()
	metadata.add_text("parsec_preparation", transform)
	metadata.add_text("parsec_source", source.as_posix())
	metadata.add_text("parsec_parameters", json.dumps(parameters or {}, sort_keys=True))
	image.save(path, format="PNG", optimize=False, pnginfo=metadata)
	return PreparedEffectFrame(path, transform, selected_pixels, sha256(path.read_bytes()).hexdigest())


def prepare_centered_effect(source: str | Path, destination: str | Path) -> PreparedEffectFrame:
	path, image = _load_rgba(source)
	if image.width > CANVAS_SIZE or image.height > CANVAS_SIZE:
		raise ValueError(f"{path} cannot fit in a 96x96 cell without scaling")
	offset = ((CANVAS_SIZE - image.width) // 2, (CANVAS_SIZE - image.height) // 2)
	prepared = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
	prepared.alpha_composite(image, offset)
	selected = sum(1 for pixel in image.getdata() if pixel[3])
	return _save(
		prepared,
		path,
		destination,
		transform="centered-without-resampling-v1",
		selected_pixels=selected,
		parameters={"offset": offset, "source_size": image.size},
	)


def prepare_color_effect(
	source: str | Path,
	destination: str | Path,
	*,
	colors: Iterable[tuple[int, int, int, int]],
) -> PreparedEffectFrame:
	path, image = _load_rgba(source)
	if image.size != (CANVAS_SIZE, CANVAS_SIZE):
		raise ValueError(f"{path} must be a 96x96 source")
	selected_colors = set(colors)
	if not selected_colors:
		raise ValueError("At least one exact RGBA color is required")
	prepared = Image.new("RGBA", image.size, (0, 0, 0, 0))
	selected = 0
	for y in range(image.height):
		for x in range(image.width):
			pixel = image.getpixel((x, y))
			if pixel in selected_colors:
				prepared.putpixel((x, y), pixel)
				selected += 1
	return _save(
		prepared,
		path,
		destination,
		transform="exact-color-isolation-v1",
		selected_pixels=selected,
		parameters={"colors": sorted(selected_colors)},
	)


def prepare_detached_effect(source: str | Path, destination: str | Path) -> PreparedEffectFrame:
	path, image = _load_rgba(source)
	if image.size != (CANVAS_SIZE, CANVAS_SIZE):
		raise ValueError(f"{path} must be a 96x96 source")
	components = _components(image)
	if len(components) < 2:
		raise ValueError(f"{path} has no detached effect components")
	body = max(components, key=len)
	selected_components = [component for component in components if component is not body]
	prepared = Image.new("RGBA", image.size, (0, 0, 0, 0))
	for component in selected_components:
		for point in component:
			prepared.putpixel(point, image.getpixel(point))
	selected = sum(len(component) for component in selected_components)
	return _save(
		prepared,
		path,
		destination,
		transform="detached-component-isolation-v1",
		selected_pixels=selected,
		parameters={"removed_largest_component_pixels": len(body), "retained_components": len(selected_components)},
	)


def prepare_faded_effect(
	source: str | Path,
	destination: str | Path,
	*,
	alpha_factor: float,
) -> PreparedEffectFrame:
	path, image = _load_rgba(source)
	if image.size != (CANVAS_SIZE, CANVAS_SIZE):
		raise ValueError(f"{path} must be a 96x96 source")
	if not 0 < alpha_factor <= 1:
		raise ValueError("alpha_factor must be greater than 0 and at most 1")
	prepared = image.copy()
	selected = 0
	for y in range(image.height):
		for x in range(image.width):
			red, green, blue, alpha = image.getpixel((x, y))
			if not alpha:
				continue
			prepared.putpixel((x, y), (red, green, blue, round(alpha * alpha_factor)))
			selected += 1
	return _save(
		prepared,
		path,
		destination,
		transform="alpha-scaled-v1",
		selected_pixels=selected,
		parameters={"alpha_factor": alpha_factor},
	)


def _parse_color(value: str) -> tuple[int, int, int, int]:
	parts = tuple(int(part) for part in value.split(","))
	if len(parts) != 4 or any(part < 0 or part > 255 for part in parts):
		raise argparse.ArgumentTypeError("Colors must be R,G,B,A with values from 0 to 255")
	return parts


def main() -> int:
	parser = argparse.ArgumentParser(description="Prepare deterministic 96x96 Parsec effect frames.")
	parser.add_argument("mode", choices=("centered", "color", "detached", "faded"))
	parser.add_argument("source", type=Path)
	parser.add_argument("destination", type=Path)
	parser.add_argument("--color", action="append", type=_parse_color, default=[])
	parser.add_argument("--alpha-factor", type=float)
	args = parser.parse_args()
	if args.mode == "centered":
		result = prepare_centered_effect(args.source, args.destination)
	elif args.mode == "color":
		result = prepare_color_effect(args.source, args.destination, colors=args.color)
	elif args.mode == "detached":
		result = prepare_detached_effect(args.source, args.destination)
	else:
		if args.alpha_factor is None:
			parser.error("faded mode requires --alpha-factor")
		result = prepare_faded_effect(args.source, args.destination, alpha_factor=args.alpha_factor)
	print(f"{result.path}\t{result.sha256}\t{result.selected_pixels}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

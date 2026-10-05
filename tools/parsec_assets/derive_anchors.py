from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

from PIL import Image

IDENTITY_COLORS = {
	(255, 60, 200, 255),
	(251, 212, 54, 255),
}


def _point(x: int, y: int) -> dict[str, int]:
	return {"x": max(0, min(95, x)), "y": max(0, min(95, y))}


def _average(points: list[tuple[int, int]]) -> tuple[int, int]:
	return (
		round(sum(x for x, _ in points) / len(points)),
		round(sum(y for _, y in points) / len(points)),
	)


def _alpha_components(image: Image.Image) -> list[list[tuple[int, int]]]:
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
	return components


def derive_frame_anchors(source: str | Path) -> dict[str, dict[str, int]]:
	with Image.open(source) as opened:
		if opened.mode != "RGBA" or opened.size != (96, 96):
			raise ValueError(f"{source} must be a 96x96 RGBA PNG")
		image = opened.copy()
	components = _alpha_components(image)
	if not components:
		raise ValueError(f"{source} has no foreground")
	body = max(components, key=len)
	body_points = set(body)
	bbox = (
		min(x for x, _ in body),
		min(y for _, y in body),
		max(x for x, _ in body) + 1,
		max(y for _, y in body) + 1,
	)
	auxiliary = [point for component in components if component is not body for point in component]
	pixels = image.load()
	identity = [
		(x, y)
		for x, y in body
		if pixels[x, y] in IDENTITY_COLORS
	]
	width = bbox[2] - bbox[0]
	height = bbox[3] - bbox[1]
	face_x, face_y = _average(identity) if identity else (
		round((bbox[0] + bbox[2] - 1) / 2),
		bbox[1] + round(height * 0.3),
	)
	center_x = (bbox[0] + bbox[2] - 1) / 2
	profile_threshold = width * 0.08
	orientation = "front"
	if face_x < center_x - profile_threshold:
		orientation = "left"
	elif face_x > center_x + profile_threshold:
		orientation = "right"
	head_points = [
		(x, y)
		for y in range(max(bbox[1], face_y - 8), min(bbox[3], face_y + 13))
		for x in range(bbox[0], bbox[2])
		if (x, y) in body_points
	]
	mouth_y = face_y + round(height * 0.1)
	if orientation == "left":
		mouth_x = min(x for x, _ in head_points)
		scruff_x = face_x + round(width * 0.16)
	elif orientation == "right":
		mouth_x = max(x for x, _ in head_points)
		scruff_x = face_x - round(width * 0.16)
	else:
		mouth_x = face_x
		scruff_x = round(center_x)
	scruff_y = face_y + round(height * 0.08)
	bottom_y = bbox[3] - 1
	support = [
		(x, y)
		for y in range(max(bbox[1], bottom_y - 2), bottom_y + 1)
		for x in range(bbox[0], bbox[2])
		if (x, y) in body_points
	]
	feet_x, _ = _average(support)
	feet = _point(feet_x, bottom_y)
	mouth = _point(mouth_x, mouth_y)
	effect_x, effect_y = _average(auxiliary) if auxiliary else (face_x, bbox[1] - 4)
	return {
		"feet": feet,
		"face": _point(face_x, face_y),
		"scruff": _point(scruff_x, scruff_y),
		"mouth": mouth,
		"interaction": _point(round(center_x), round((bbox[1] + bbox[3] - 1) / 2)),
		"toy": mouth.copy(),
		"effect": _point(effect_x, effect_y),
		"shadow": feet.copy(),
	}


def _frame_key(atlas: str, path: Path) -> str:
	parts = path.stem.split("__")
	if len(parts) != 3 or not parts[1].startswith("d") or not parts[2].startswith("f"):
		raise ValueError(f"Expected <clip>__d<direction>__f<frame>.png: {path}")
	return f"{atlas}/{parts[0]}/{parts[1]}/{parts[2]}"


def main() -> int:
	parser = argparse.ArgumentParser(description="Derive stable Parsec attachment anchors from reviewed frames.")
	parser.add_argument("--input", required=True, type=Path)
	parser.add_argument("--atlas", required=True)
	parser.add_argument("--output", required=True, type=Path)
	args = parser.parse_args()
	if args.output.exists():
		raise FileExistsError(f"Refusing to overwrite destination: {args.output}")
	anchors = {
		_frame_key(args.atlas, path): derive_frame_anchors(path)
		for path in sorted(args.input.rglob("*.png"))
	}
	if not anchors:
		raise ValueError("At least one reviewed frame is required")
	args.output.parent.mkdir(parents=True, exist_ok=True)
	args.output.write_text(json.dumps(anchors, indent=2, sort_keys=True) + "\n", encoding="utf-8")
	print(args.output)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

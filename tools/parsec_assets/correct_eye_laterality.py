from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from PIL import Image, PngImagePlugin

NEON_PINK = (255, 60, 200, 255)
SUPERMATTER_YELLOW = (251, 212, 54, 255)
IDENTITY_COLORS = {NEON_PINK, SUPERMATTER_YELLOW}


@dataclass(frozen=True)
class CorrectedEyeFrame:
	path: Path
	source: Path
	source_sha256: str
	sha256: str


def _eye_components(image: Image.Image) -> list[list[tuple[int, int]]]:
	pixels = image.load()
	remaining = {
		(x, y)
		for y in range(image.height)
		for x in range(image.width)
		if pixels[x, y] in IDENTITY_COLORS
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


def _merge_components_by_x(components: list[list[tuple[int, int]]]) -> list[list[tuple[int, int]]]:
	ordered = sorted(components, key=lambda component: sum(x for x, _ in component) / len(component))
	clusters: list[list[tuple[int, int]]] = []
	for component in ordered:
		center_x = sum(x for x, _ in component) / len(component)
		if clusters:
			cluster_center_x = sum(x for x, _ in clusters[-1]) / len(clusters[-1])
			if abs(center_x - cluster_center_x) <= 4:
				clusters[-1].extend(component)
				continue
		clusters.append(component.copy())
	return clusters


def correct_eye_laterality(source: str | Path, destination: str | Path) -> CorrectedEyeFrame:
	source_path = Path(source)
	output_path = Path(destination)
	if output_path.exists():
		raise FileExistsError(f"Refusing to overwrite destination: {output_path}")
	with Image.open(source_path) as image:
		if image.mode != "RGBA" or image.size != (96, 96):
			raise ValueError(f"{source_path} must be a 96x96 RGBA PNG")
		corrected = image.copy()
	components = _merge_components_by_x(_eye_components(corrected))
	if len(components) != 2:
		raise ValueError(f"Expected exactly two identity-color eye clusters, found {len(components)}")
	components.sort(key=lambda component: sum(x for x, _ in component) / len(component))
	pixels = corrected.load()
	for point in components[0]:
		pixels[point] = NEON_PINK
	for point in components[1]:
		pixels[point] = SUPERMATTER_YELLOW
	output_path.parent.mkdir(parents=True, exist_ok=True)
	source_hash = sha256(source_path.read_bytes()).hexdigest()
	metadata = PngImagePlugin.PngInfo()
	metadata.add_text("parsec_transform", "front-eye-laterality-v3")
	metadata.add_text("parsec_source_sha256", source_hash)
	corrected.save(output_path, format="PNG", optimize=False, pnginfo=metadata)
	return CorrectedEyeFrame(
		path=output_path,
		source=source_path,
		source_sha256=source_hash,
		sha256=sha256(output_path.read_bytes()).hexdigest(),
	)


def main() -> int:
	parser = argparse.ArgumentParser(description="Apply Parsec's anatomical-left-yellow/anatomical-right-pink eye contract.")
	parser.add_argument("source", type=Path)
	parser.add_argument("destination", type=Path)
	args = parser.parse_args()
	result = correct_eye_laterality(args.source, args.destination)
	print(f"{result.path}\t{result.sha256}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class VisualRules:
	max_components: int = 16
	max_detached_component_pixels: int = 1
	max_baseline_jitter: int = 8
	max_height_discontinuity: float = 0.20
	left_eye_rgba: tuple[int, int, int, int] | None = None
	right_eye_rgba: tuple[int, int, int, int] | None = None
	require_front_eye_laterality: bool = False


def _alpha_components(image: Image.Image) -> list[list[tuple[int, int]]]:
	alpha = image.getchannel("A")
	occupied = {
		(x, y)
		for y in range(image.height)
		for x in range(image.width)
		if alpha.getpixel((x, y)) > 0
	}
	components: list[list[tuple[int, int]]] = []
	while occupied:
		pending = [occupied.pop()]
		component: list[tuple[int, int]] = []
		while pending:
			x, y = pending.pop()
			component.append((x, y))
			for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
				if neighbor in occupied:
					occupied.remove(neighbor)
					pending.append(neighbor)
		components.append(component)
	return components


def _matching_x(image: Image.Image, color: tuple[int, int, int, int]) -> list[int]:
	return [
		x
		for y in range(image.height)
		for x in range(image.width)
		if image.getpixel((x, y)) == color
	]


def lint_clip_frames(paths: Iterable[str | Path], rules: VisualRules) -> list[str]:
	errors: list[str] = []
	bounds: list[tuple[int, int, int, int]] = []
	for source in paths:
		path = Path(source)
		with Image.open(path) as opened:
			image = opened.convert("RGBA")
		alpha_bounds = image.getchannel("A").getbbox()
		if alpha_bounds is None:
			errors.append(f"{path.name}: frame has no occupied pixels")
			continue
		bounds.append(alpha_bounds)
		if alpha_bounds[0] == 0 or alpha_bounds[1] == 0 or alpha_bounds[2] == image.width or alpha_bounds[3] == image.height:
			errors.append(f"{path.name}: alpha touches the cell border")
		components = _alpha_components(image)
		if len(components) > rules.max_components:
			errors.append(
				f"{path.name}: detached alpha component count {len(components)} exceeds {rules.max_components}"
			)
		elif len(components) > 1:
			ordered_components = sorted(components, key=len, reverse=True)
			main = ordered_components[0]
			main_bounds = (
				min(x for x, _y in main),
				min(y for _x, y in main),
				max(x for x, _y in main),
				max(y for _x, y in main),
			)
			if any(
				len(component) <= rules.max_detached_component_pixels
				and any(
					x < main_bounds[0] or x > main_bounds[2] or y < main_bounds[1] or y > main_bounds[3]
					for x, y in component
				)
				for component in ordered_components[1:]
			):
				errors.append(f"{path.name}: detached alpha component at or below {rules.max_detached_component_pixels}px")
		if rules.require_front_eye_laterality:
			if rules.left_eye_rgba is None or rules.right_eye_rgba is None:
				raise ValueError("Front eye laterality requires both eye colors")
			left_eye_x = _matching_x(image, rules.left_eye_rgba)
			right_eye_x = _matching_x(image, rules.right_eye_rgba)
			if left_eye_x and right_eye_x and sum(left_eye_x) / len(left_eye_x) < sum(right_eye_x) / len(right_eye_x):
				errors.append(f"{path.name}: visible eye colors have reversed anatomical laterality")
	if len(bounds) > 1:
		baselines = [box[3] for box in bounds]
		baseline_jitter = max(baselines) - min(baselines)
		if baseline_jitter > rules.max_baseline_jitter:
			errors.append(f"clip: baseline jitter {baseline_jitter}px exceeds {rules.max_baseline_jitter}px")
		heights = [box[3] - box[1] for box in bounds]
		largest_height = max(heights)
		discontinuity = (largest_height - min(heights)) / largest_height
		if discontinuity > rules.max_height_discontinuity:
			errors.append(
				f"clip: occupied-height discontinuity {discontinuity:.0%} exceeds {rules.max_height_discontinuity:.0%}"
			)
	return errors

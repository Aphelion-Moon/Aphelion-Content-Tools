from __future__ import annotations

from PIL import Image

from tools.parsec_assets.visual_lint import VisualRules, lint_clip_frames

YELLOW = (251, 212, 54, 255)
PINK = (255, 60, 200, 255)


def _frame(path, bounds=(24, 30, 72, 80), *, eyes=True):
	image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
	for y in range(bounds[1], bounds[3]):
		for x in range(bounds[0], bounds[2]):
			image.putpixel((x, y), (40, 50, 60, 255))
	if eyes:
		image.putpixel((40, 44), PINK)
		image.putpixel((56, 44), YELLOW)
	image.save(path, format="PNG")
	return path


def test_rejects_border_residue_and_detached_pixel(tmp_path):
	path = _frame(tmp_path / "dirty.png")
	with Image.open(path) as source:
		image = source.convert("RGBA")
	image.putpixel((0, 50), (255, 255, 255, 255))
	image.putpixel((90, 90), (255, 255, 255, 255))
	image.save(path, format="PNG")
	errors = lint_clip_frames([path], VisualRules(max_components=16, max_detached_component_pixels=1))
	assert any("dirty.png: alpha touches the cell border" in error for error in errors)
	assert any("dirty.png: detached alpha component" in error for error in errors)


def test_rejects_baseline_jitter_and_occupied_height_discontinuity(tmp_path):
	first = _frame(tmp_path / "first.png", (24, 30, 72, 80), eyes=False)
	second = _frame(tmp_path / "second.png", (24, 40, 72, 90), eyes=False)
	third = _frame(tmp_path / "third.png", (24, 54, 72, 90), eyes=False)
	errors = lint_clip_frames(
		[first, second, third],
		VisualRules(max_baseline_jitter=8, max_height_discontinuity=0.20),
	)
	assert any(error == "clip: baseline jitter 10px exceeds 8px" for error in errors)
	assert any("clip: occupied-height discontinuity" in error for error in errors)


def test_rejects_swapped_front_eye_colors(tmp_path):
	path = _frame(tmp_path / "swapped.png", eyes=False)
	with Image.open(path) as source:
		image = source.convert("RGBA")
	image.putpixel((40, 44), YELLOW)
	image.putpixel((56, 44), PINK)
	image.save(path, format="PNG")
	errors = lint_clip_frames(
		[path],
		VisualRules(
			left_eye_rgba=YELLOW,
			right_eye_rgba=PINK,
			require_front_eye_laterality=True,
		),
	)
	assert errors == ["swapped.png: visible eye colors have reversed anatomical laterality"]


def test_accepts_a_consistent_clean_clip(tmp_path):
	paths = [
		_frame(tmp_path / "first.png", (24, 30, 72, 80)),
		_frame(tmp_path / "second.png", (24, 31, 72, 81)),
	]
	assert lint_clip_frames(
		paths,
		VisualRules(
			max_components=1,
			left_eye_rgba=YELLOW,
			right_eye_rgba=PINK,
			require_front_eye_laterality=True,
		),
	) == []

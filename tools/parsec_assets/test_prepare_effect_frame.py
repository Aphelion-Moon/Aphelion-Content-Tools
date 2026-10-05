from pathlib import Path

from PIL import Image

from tools.parsec_assets.prepare_effect_frame import (
	prepare_centered_effect,
	prepare_color_effect,
	prepare_detached_effect,
	prepare_faded_effect,
)


def _save(path: Path, size: tuple[int, int], pixels: dict[tuple[int, int], tuple[int, int, int, int]]) -> None:
	image = Image.new("RGBA", size, (0, 0, 0, 0))
	for point, color in pixels.items():
		image.putpixel(point, color)
	image.save(path)


def test_centered_effect_preserves_source_pixels_without_resampling(tmp_path: Path) -> None:
	source = tmp_path / "source.png"
	destination = tmp_path / "prepared.png"
	_save(source, (2, 2), {(0, 0): (255, 0, 0, 255), (1, 1): (0, 255, 0, 128)})

	result = prepare_centered_effect(source, destination)

	with Image.open(destination) as prepared:
		assert prepared.size == (96, 96)
		assert prepared.getpixel((47, 47)) == (255, 0, 0, 255)
		assert prepared.getpixel((48, 48)) == (0, 255, 0, 128)
	assert result.transform == "centered-without-resampling-v1"


def test_color_effect_keeps_only_recorded_exact_colors(tmp_path: Path) -> None:
	source = tmp_path / "source.png"
	destination = tmp_path / "prepared.png"
	cyan = (80, 220, 235, 255)
	_save(source, (96, 96), {(3, 4): cyan, (4, 4): (80, 220, 234, 255), (5, 4): (0, 0, 0, 255)})

	result = prepare_color_effect(source, destination, colors=[cyan])

	with Image.open(destination) as prepared:
		assert prepared.getpixel((3, 4)) == cyan
		assert prepared.getpixel((4, 4))[3] == 0
		assert prepared.getpixel((5, 4))[3] == 0
	assert result.selected_pixels == 1


def test_detached_effect_removes_largest_connected_component(tmp_path: Path) -> None:
	source = tmp_path / "source.png"
	destination = tmp_path / "prepared.png"
	_save(source, (96, 96), {
		(10, 10): (255, 255, 255, 255),
		(11, 10): (255, 255, 255, 255),
		(12, 10): (255, 255, 255, 255),
		(80, 80): (180, 180, 180, 255),
	})

	result = prepare_detached_effect(source, destination)

	with Image.open(destination) as prepared:
		assert prepared.getpixel((10, 10))[3] == 0
		assert prepared.getpixel((80, 80)) == (180, 180, 180, 255)
	assert result.selected_pixels == 1


def test_faded_effect_scales_alpha_without_changing_rgb(tmp_path: Path) -> None:
	source = tmp_path / "source.png"
	destination = tmp_path / "prepared.png"
	_save(source, (96, 96), {(9, 8): (12, 34, 56, 200)})

	result = prepare_faded_effect(source, destination, alpha_factor=0.25)

	with Image.open(destination) as prepared:
		assert prepared.getpixel((9, 8)) == (12, 34, 56, 50)
	assert result.transform == "alpha-scaled-v1"


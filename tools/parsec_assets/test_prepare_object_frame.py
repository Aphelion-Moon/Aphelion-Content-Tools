from __future__ import annotations

from PIL import Image

from tools.parsec_assets.prepare_object_frame import prepare_object_frame


def test_crops_scales_and_places_object_on_explicit_baseline(tmp_path):
	source = tmp_path / "source.png"
	image = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
	for y in range(8, 20):
		for x in range(6, 22):
			image.putpixel((x, y), (251, 212, 54, 255))
	image.save(source, format="PNG")
	output = tmp_path / "output.png"
	result = prepare_object_frame(source, output, scale=3, baseline_y=78)
	assert result.source_size == (32, 32)
	assert result.source_bounds == (6, 8, 22, 20)
	assert result.occupied_size == (48, 36)
	assert result.offset == (24, 42)
	assert result.scale == 3
	assert result.baseline_y == 78
	with Image.open(output) as prepared:
		assert prepared.mode == "RGBA"
		assert prepared.size == (96, 96)
		assert prepared.getchannel("A").getbbox() == (24, 42, 72, 78)
		assert prepared.info["parsec_preparation"] == "alpha-crop-nearest-scale-baseline-v2"


def test_rejects_a_scaled_object_that_cannot_fit_the_cell(tmp_path):
	source = tmp_path / "source.png"
	Image.new("RGBA", (40, 40), (255, 255, 255, 255)).save(source, format="PNG")
	output = tmp_path / "output.png"
	try:
		prepare_object_frame(source, output, scale=3, baseline_y=90)
	except ValueError as error:
		assert "cannot fit" in str(error)
	else:
		raise AssertionError("Expected oversized object preparation to fail")

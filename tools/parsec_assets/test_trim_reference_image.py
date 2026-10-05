from __future__ import annotations

import json

from PIL import Image, ImageDraw

from tools.parsec_assets.trim_reference_image import trim_reference_image


def _make_padded_reference(path):
	image = Image.new("RGB", (100, 80), (248, 248, 248))
	draw = ImageDraw.Draw(image)
	draw.rectangle((30, 20, 69, 59), fill=(0, 0, 0))
	draw.rectangle((34, 24, 65, 55), fill=(255, 255, 255))
	image.save(path, format="PNG")


def test_applies_manual_crop_without_altering_the_retained_pixels(tmp_path):
	source = tmp_path / "padded.png"
	destination = tmp_path / "references" / "trimmed.png"
	_make_padded_reference(source)

	result = trim_reference_image(
		source,
		destination,
		crop=(20, 10, 80, 70),
		minimum_margin=8,
	)

	assert result.destination == destination
	assert result.source_size == (100, 80)
	assert result.crop == (20, 10, 80, 70)
	assert result.occupied_bbox == (30, 20, 70, 60)
	assert result.retained_margin == (10, 10, 10, 10)
	with Image.open(destination) as trimmed:
		assert trimmed.mode == "RGB"
		assert trimmed.size == (60, 60)
		assert trimmed.getpixel((10, 10)) == (0, 0, 0)
		assert trimmed.getpixel((14, 14)) == (255, 255, 255)
	metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
	assert metadata["tool"] == "manual-reference-trim-v1"
	assert metadata["sourceSha256"] == result.source_sha256
	assert metadata["outputSha256"] == result.output_sha256
	assert metadata["crop"] == [20, 10, 80, 70]


def test_rejects_a_manual_crop_that_cuts_foreground(tmp_path):
	source = tmp_path / "padded.png"
	_make_padded_reference(source)

	try:
		trim_reference_image(
			source,
			tmp_path / "trimmed.png",
			crop=(40, 10, 80, 70),
		)
	except ValueError as error:
		assert "cuts occupied artwork" in str(error)
	else:
		raise AssertionError("Expected a destructive manual crop to be rejected")

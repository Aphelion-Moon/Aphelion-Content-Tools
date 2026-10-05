from __future__ import annotations

from PIL import Image

from tools.parsec_assets.correct_eye_laterality import correct_eye_laterality


def test_assigns_anatomical_left_yellow_and_right_pink(tmp_path):
	source = tmp_path / "source.png"
	image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
	for x in (30, 60):
		image.putpixel((x, 20), (251, 212, 54, 255))
		image.putpixel((x + 1, 20), (251, 212, 54, 255))
	image.putpixel((30, 22), (251, 212, 54, 255))
	image.save(source, format="PNG")
	result = correct_eye_laterality(source, tmp_path / "corrected.png")
	with Image.open(result.path) as corrected:
		assert corrected.getpixel((30, 20)) == (255, 60, 200, 255)
		assert corrected.getpixel((30, 22)) == (255, 60, 200, 255)
		assert corrected.getpixel((60, 20)) == (251, 212, 54, 255)
	assert result.source_sha256

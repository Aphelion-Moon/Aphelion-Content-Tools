from hashlib import sha256

import pytest
from PIL import Image

from tools.parsec_assets.pixel_touchup import apply_pixel_touchup


def test_edits_only_reviewed_pixels_and_preserves_white_fur(tmp_path):
	source = tmp_path / "source.png"
	image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
	image.putpixel((20, 40), (255, 255, 255, 255))
	image.putpixel((35, 40), (255, 255, 255, 255))
	image.save(source)
	original = source.read_bytes()
	output = tmp_path / "clean.png"
	apply_pixel_touchup(source, output, source_sha256=sha256(original).hexdigest(),
		edits=[{"point": [20, 40], "before": [255, 255, 255, 255], "after": [0, 0, 0, 0]}],
		reason="Remove reviewed exterior fill below muzzle")
	with Image.open(output) as clean:
		assert clean.getpixel((20, 40)) == (0, 0, 0, 0)
		assert clean.getpixel((35, 40)) == (255, 255, 255, 255)
	assert source.read_bytes() == original
	with pytest.raises(FileExistsError):
		apply_pixel_touchup(source, output, source_sha256=sha256(original).hexdigest(), edits=[], reason="again")


@pytest.mark.parametrize("edits", [
	[{"point": [96, 0], "before": [0, 0, 0, 0], "after": [255, 255, 255, 255]}],
	[{"point": [20, 40], "before": [255, 255, 255, 255], "after": [0, 0, 0, 0]}],
	[{"point": [20, 40], "before": [0, 0, 0, 0], "after": [300, 0, 0, 255]}],
])
def test_invalid_pixel_patch_writes_nothing(tmp_path, edits):
	source = tmp_path / "source.png"
	Image.new("RGBA", (96, 96), (0, 0, 0, 0)).save(source)
	output = tmp_path / "clean.png"
	with pytest.raises(ValueError):
		apply_pixel_touchup(source, output, source_sha256=sha256(source.read_bytes()).hexdigest(), edits=edits, reason="test")
	assert not output.exists()


def test_source_hash_mismatch_writes_nothing(tmp_path):
	source = tmp_path / "source.png"
	Image.new("RGBA", (96, 96), (0, 0, 0, 0)).save(source)
	output = tmp_path / "clean.png"
	with pytest.raises(ValueError, match="source hash"):
		apply_pixel_touchup(source, output, source_sha256="0" * 64, edits=[], reason="test")
	assert not output.exists()

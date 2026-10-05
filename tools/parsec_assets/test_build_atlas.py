from __future__ import annotations

from hashlib import sha256

from PIL import Image

from tools.parsec_assets.build_atlas import AtlasFrame, build_atlas


def _frame(path, color):
	Image.new("RGBA", (96, 96), color).save(path, format="PNG")


def test_atlas_is_byte_identical_for_the_same_sorted_inputs(tmp_path):
	first_frame = tmp_path / "z.png"
	second_frame = tmp_path / "a.png"
	_frame(first_frame, (255, 0, 0, 255))
	_frame(second_frame, (0, 255, 0, 255))
	frames = [
		AtlasFrame("core", "walk", 1, 0, first_frame),
		AtlasFrame("core", "idle", 0, 0, second_frame),
	]
	first = build_atlas(frames, tmp_path / "first")
	second = build_atlas(reversed(frames), tmp_path / "second")
	assert sha256(first.png.read_bytes()).hexdigest() == sha256(second.png.read_bytes()).hexdigest()
	assert first.coordinates == second.coordinates
	assert list(first.coordinates) == ["core/idle/d0/f0", "core/walk/d0/f1"]
	custom = build_atlas(reversed(frames), tmp_path / "custom", name="parsec-core")
	assert custom.png.name == "parsec-core.png"
	assert custom.coordinates_path.name == "parsec-core.json"


def test_atlas_refuses_non_96_pixel_frames(tmp_path):
	bad = tmp_path / "bad.png"
	Image.new("RGBA", (32, 32), (0, 0, 0, 0)).save(bad, format="PNG")
	try:
		build_atlas([AtlasFrame("core", "bad", 0, 0, bad)], tmp_path / "output")
	except ValueError as error:
		assert "96x96 RGBA" in str(error)
	else:
		raise AssertionError("non-96-pixel input should fail")

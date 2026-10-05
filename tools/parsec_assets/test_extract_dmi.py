from __future__ import annotations

from hashlib import sha256

from PIL import Image, PngImagePlugin

from tools.parsec_assets.extract_dmi import extract_dmi_state, read_dmi_metadata


def _fixture(path):
	image = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
	image.paste((255, 0, 0, 255), (0, 0, 32, 32))
	image.paste((0, 255, 0, 255), (32, 0, 64, 32))
	metadata = PngImagePlugin.PngInfo()
	metadata.add_text(
		"Description",
		'# BEGIN DMI\nversion = 4.0\n\twidth = 32\n\theight = 32\nstate = "dogbed"\n\tdirs = 1\n\tframes = 2\n\tdelay = 1,2\n# END DMI',
	)
	image.save(path, format="PNG", pnginfo=metadata)


def test_extracts_named_state_without_resampling(tmp_path):
	source = tmp_path / "fixture.dmi"
	_fixture(source)
	frames = extract_dmi_state(source, "dogbed", tmp_path / "frames")
	assert len(frames) == 2
	assert frames[0].image_size == (32, 32)
	assert frames[0].sha256 == sha256(frames[0].path.read_bytes()).hexdigest()
	assert Image.open(frames[0].path).getpixel((0, 0)) == (255, 0, 0, 255)
	assert Image.open(frames[1].path).getpixel((0, 0)) == (0, 255, 0, 255)


def test_reads_state_timing_and_refuses_missing_state(tmp_path):
	source = tmp_path / "fixture.dmi"
	_fixture(source)
	metadata = read_dmi_metadata(source)
	assert metadata.width == 32
	assert metadata.states[0].delays == (1.0, 2.0)
	try:
		extract_dmi_state(source, "missing", tmp_path / "frames")
	except ValueError as error:
		assert "missing" in str(error)
	else:
		raise AssertionError("missing DMI state should fail")

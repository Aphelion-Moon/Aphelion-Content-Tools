from __future__ import annotations

from PIL import Image

from tools.parsec_assets.compose_prepared_clip import compose_prepared_clip


def test_composes_selected_96_pixel_frames_without_resampling(tmp_path):
	sources = []
	for index, color in enumerate(((255, 60, 200, 255), (251, 212, 54, 255))):
		path = tmp_path / f"source-{index}.png"
		Image.new("RGBA", (96, 96), color).save(path, format="PNG")
		sources.append(path)
	result = compose_prepared_clip(sources, tmp_path / "output", clip="look", direction=2)
	assert [frame.path.name for frame in result.frames] == ["look__d2__f0.png", "look__d2__f1.png"]
	with Image.open(result.frames[0].path) as first:
		assert first.getpixel((48, 48)) == (255, 60, 200, 255)
	with Image.open(result.frames[1].path) as second:
		assert second.getpixel((48, 48)) == (251, 212, 54, 255)
	assert result.metadata_path.exists()

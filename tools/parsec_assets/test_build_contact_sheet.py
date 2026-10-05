from __future__ import annotations

from PIL import Image

from tools.parsec_assets.build_contact_sheet import (
	ContactSheetFrame,
	build_contact_sheet,
	discover_contact_sheet_frames,
)


def test_contact_sheet_contains_native_and_nearest_neighbor_4x_views(tmp_path):
	source = tmp_path / "frame.png"
	image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
	image.putpixel((0, 0), (255, 0, 0, 255))
	image.putpixel((1, 0), (0, 0, 255, 255))
	image.save(source, format="PNG")
	result = build_contact_sheet(
		[ContactSheetFrame("idle", 0, 0, source, {"feet": (48, 82)}, 150, "seated-idle", "fallback")],
		tmp_path / "review",
		title="Core",
	)
	assert result.png.is_file()
	assert result.html.is_file()
	with Image.open(result.png) as sheet:
		assert sheet.info["parsec_review_scale"] == "1x+4x-nearest"
	assert "idle" in result.html.read_text(encoding="utf-8")


def test_discovers_nested_prepared_frames_and_parses_direction(tmp_path):
	path = tmp_path / "d2" / "walk__d2__f1.png"
	path.parent.mkdir()
	Image.new("RGBA", (96, 96), (0, 0, 0, 0)).save(path, format="PNG")
	frames = discover_contact_sheet_frames(tmp_path)
	assert [(frame.clip, frame.direction, frame.frame) for frame in frames] == [("walk", 2, 1)]

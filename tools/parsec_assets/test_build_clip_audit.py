from __future__ import annotations

from PIL import Image

from tools.parsec_assets.build_clip_audit import build_clip_audit_sheets


def test_builds_one_readable_nearest_neighbor_sheet_per_clip(tmp_path):
	prepared = tmp_path / "prepared"
	for clip, frame, color in (
		("idle", 0, (255, 0, 0, 255)),
		("idle", 1, (0, 255, 0, 255)),
		("walk", 0, (0, 0, 255, 255)),
	):
		path = prepared / clip / f"{clip}__d0__f{frame}.png"
		path.parent.mkdir(parents=True, exist_ok=True)
		image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
		image.putpixel((0, 0), color)
		image.save(path, format="PNG")

	results = build_clip_audit_sheets(prepared, tmp_path / "review", columns=2)

	assert [result.stem for result in results] == ["idle", "walk"]
	with Image.open(results[0]) as sheet:
		assert sheet.size == (768, 416)
		assert sheet.info["parsec_review_scale"] == "4x-nearest-per-clip"
		assert sheet.getpixel((0, 32)) == (255, 0, 0, 255)
		assert sheet.getpixel((384, 32)) == (0, 255, 0, 255)

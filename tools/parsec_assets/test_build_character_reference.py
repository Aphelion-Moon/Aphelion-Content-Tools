from __future__ import annotations

import json

from PIL import Image

from tools.parsec_assets.build_character_reference import CHARACTER_ATLASES, build_character_reference


def _frame(path, color):
	path.parent.mkdir(parents=True, exist_ok=True)
	Image.new("RGBA", (96, 96), color).save(path, format="PNG")


def test_builds_one_deterministic_sheet_and_reference_map_from_character_atlases(tmp_path):
	prepared = tmp_path / "prepared"
	_frame(prepared / "parsec-core" / "idle" / "idle__d0__f1.png", (255, 0, 0, 255))
	_frame(prepared / "parsec-core" / "idle" / "idle__d0__f0.png", (0, 255, 0, 255))
	_frame(prepared / "parsec-touch" / "pat" / "pat__d0__f0.png", (0, 0, 255, 255))

	result = build_character_reference(prepared, tmp_path / "reference", columns=2)
	manifest = json.loads(result.reference.read_text(encoding="utf-8"))

	assert CHARACTER_ATLASES == (
		"parsec-core",
		"parsec-feedback",
		"parsec-touch",
		"parsec-toys",
		"parsec-habitat",
		"parsec-intrusive",
	)
	assert result.frame_count == 3
	assert list(manifest["frames"]) == [
		"parsec-core/idle/d0/f0",
		"parsec-core/idle/d0/f1",
		"parsec-touch/pat/d0/f0",
	]
	assert manifest["frames"]["parsec-core/idle/d0/f0"]["cell"] == {"column": 0, "row": 0}
	assert manifest["frames"]["parsec-core/idle/d0/f1"]["cell"] == {"column": 1, "row": 0}
	assert manifest["frames"]["parsec-touch/pat/d0/f0"]["cell"] == {"column": 0, "row": 1}
	assert manifest["frames"]["parsec-touch/pat/d0/f0"]["source"] == "parsec-touch/pat/pat__d0__f0.png"
	with Image.open(result.sheet) as sheet:
		assert sheet.mode == "RGBA"
		assert sheet.size == (192, 192)
		assert sheet.getpixel((0, 0)) == (0, 255, 0, 255)


def test_refuses_to_overwrite_an_existing_reference_output(tmp_path):
	prepared = tmp_path / "prepared"
	_frame(prepared / "parsec-core" / "idle" / "idle__d0__f0.png", (0, 0, 0, 255))
	output = tmp_path / "reference"
	build_character_reference(prepared, output)

	try:
		build_character_reference(prepared, output)
	except FileExistsError as error:
		assert "Refusing to overwrite" in str(error)
	else:
		raise AssertionError("Expected an existing reference output to be rejected")

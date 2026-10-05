from __future__ import annotations

import json

from PIL import Image

from tools.parsec_assets.build_character_reference import build_character_reference
from tools.parsec_assets.split_character_reference import split_character_reference


def _frame(path, color):
	path.parent.mkdir(parents=True, exist_ok=True)
	Image.new("RGBA", (96, 96), color).save(path, format="PNG")


def test_splits_an_edited_sheet_into_a_new_staging_tree(tmp_path):
	prepared = tmp_path / "prepared"
	_frame(prepared / "parsec-core" / "idle" / "idle__d0__f0.png", (255, 0, 0, 255))
	_frame(prepared / "parsec-touch" / "pat" / "pat__d0__f0.png", (0, 0, 255, 255))
	reference = build_character_reference(prepared, tmp_path / "reference", columns=2)
	with Image.open(reference.sheet) as opened:
		edited = opened.copy()
	edited.paste((0, 255, 0, 255), (0, 0, 96, 96))
	edited.save(reference.sheet)

	result = split_character_reference(reference.sheet, reference.reference, tmp_path / "staging")

	assert result.frame_count == 2
	with Image.open(tmp_path / "staging" / "parsec-core" / "idle" / "idle__d0__f0.png") as frame:
		assert frame.getpixel((0, 0)) == (0, 255, 0, 255)
	with Image.open(tmp_path / "staging" / "parsec-touch" / "pat" / "pat__d0__f0.png") as frame:
		assert frame.getpixel((0, 0)) == (0, 0, 255, 255)
	manifest = json.loads(result.manifest.read_text(encoding="utf-8"))
	assert manifest["version"] == 1
	assert manifest["frameCount"] == 2
	assert len(manifest["sourceSheetSha256"]) == 64


def test_rejects_a_resized_sheet(tmp_path):
	prepared = tmp_path / "prepared"
	_frame(prepared / "parsec-core" / "idle" / "idle__d0__f0.png", (255, 0, 0, 255))
	reference = build_character_reference(prepared, tmp_path / "reference")
	Image.new("RGBA", (95, 96), (0, 0, 0, 0)).save(reference.sheet)

	try:
		split_character_reference(reference.sheet, reference.reference, tmp_path / "staging")
	except ValueError as error:
		assert "dimensions" in str(error)
	else:
		raise AssertionError("Expected resized sheet to be rejected")


def test_refuses_to_overwrite_an_existing_staging_tree(tmp_path):
	prepared = tmp_path / "prepared"
	_frame(prepared / "parsec-core" / "idle" / "idle__d0__f0.png", (255, 0, 0, 255))
	reference = build_character_reference(prepared, tmp_path / "reference")
	staging = tmp_path / "staging"
	staging.mkdir()
	(staging / "keep.txt").write_text("keep", encoding="utf-8")

	try:
		split_character_reference(reference.sheet, reference.reference, staging)
	except FileExistsError as error:
		assert "Refusing to overwrite" in str(error)
	else:
		raise AssertionError("Expected an existing staging tree to be rejected")


def test_rejects_a_reference_destination_that_escapes_the_staging_tree(tmp_path):
	prepared = tmp_path / "prepared"
	_frame(prepared / "parsec-core" / "idle" / "idle__d0__f0.png", (255, 0, 0, 255))
	reference = build_character_reference(prepared, tmp_path / "reference")
	manifest = json.loads(reference.reference.read_text(encoding="utf-8"))
	manifest["frames"]["parsec-core/idle/d0/f0"]["source"] = "../escaped.png"
	reference.reference.write_text(json.dumps(manifest), encoding="utf-8")

	try:
		split_character_reference(reference.sheet, reference.reference, tmp_path / "staging")
	except ValueError as error:
		assert "Unsafe reference source path" in str(error)
	else:
		raise AssertionError("Expected an escaping destination to be rejected")


def test_rejects_duplicate_cell_rectangles(tmp_path):
	prepared = tmp_path / "prepared"
	_frame(prepared / "parsec-core" / "idle" / "idle__d0__f0.png", (255, 0, 0, 255))
	_frame(prepared / "parsec-touch" / "pat" / "pat__d0__f0.png", (0, 0, 255, 255))
	reference = build_character_reference(prepared, tmp_path / "reference", columns=2)
	manifest = json.loads(reference.reference.read_text(encoding="utf-8"))
	manifest["frames"]["parsec-touch/pat/d0/f0"]["rect"] = manifest["frames"]["parsec-core/idle/d0/f0"]["rect"]
	reference.reference.write_text(json.dumps(manifest), encoding="utf-8")

	try:
		split_character_reference(reference.sheet, reference.reference, tmp_path / "staging")
	except ValueError as error:
		assert "Duplicate frame rectangle" in str(error)
	else:
		raise AssertionError("Expected duplicate frame rectangles to be rejected")

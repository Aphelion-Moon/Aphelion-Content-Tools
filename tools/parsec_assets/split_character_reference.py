from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from PIL import Image

from tools.parsec_assets.build_character_reference import CELL_SIZE, CHARACTER_ATLASES


@dataclass(frozen=True)
class CharacterReferenceSplit:
	destination: Path
	manifest: Path
	frame_count: int


def _safe_source_path(raw_source: object) -> PurePosixPath:
	if not isinstance(raw_source, str):
		raise ValueError("Every reference frame must have a string source path")
	path = PurePosixPath(raw_source)
	if path.is_absolute() or ".." in path.parts or len(path.parts) < 2:
		raise ValueError(f"Unsafe reference source path: {raw_source}")
	if path.parts[0] not in CHARACTER_ATLASES or path.suffix.lower() != ".png":
		raise ValueError(f"Unsupported reference source path: {raw_source}")
	return path


def split_character_reference(
	sheet_path: str | Path,
	reference_path: str | Path,
	destination: str | Path,
) -> CharacterReferenceSplit:
	output = Path(destination)
	if output.exists() and any(output.iterdir()):
		raise FileExistsError(f"Refusing to overwrite non-empty destination: {output}")
	reference_file = Path(reference_path)
	reference = json.loads(reference_file.read_text(encoding="utf-8"))
	if reference.get("version") != 1 or reference.get("purpose") != "human-edit-character-sheet":
		raise ValueError("Unsupported character reference format")
	cell_size = reference.get("cellSize")
	if cell_size != {"width": CELL_SIZE, "height": CELL_SIZE}:
		raise ValueError("Character reference cell dimensions must remain 96x96")
	columns = reference.get("columns")
	rows = reference.get("rows")
	frames = reference.get("frames")
	if not isinstance(columns, int) or columns <= 0 or not isinstance(rows, int) or rows <= 0:
		raise ValueError("Character reference has invalid sheet dimensions")
	if not isinstance(frames, dict) or reference.get("frameCount") != len(frames):
		raise ValueError("Character reference frame count does not match its frame map")
	sheet_file = Path(sheet_path)
	with Image.open(sheet_file) as opened:
		if opened.mode != "RGBA" or opened.size != (columns * CELL_SIZE, rows * CELL_SIZE):
			raise ValueError(
				f"Edited sheet dimensions must remain {columns * CELL_SIZE}x{rows * CELL_SIZE} RGBA"
			)
		sheet = opened.copy()
	written_sources = set()
	written_rectangles = set()
	frame_exports = []
	for key, frame_reference in frames.items():
		if not isinstance(frame_reference, dict):
			raise ValueError(f"Invalid frame reference: {key}")
		atlas = frame_reference.get("atlas")
		clip = frame_reference.get("clip")
		direction = frame_reference.get("direction")
		frame_number = frame_reference.get("frame")
		if not isinstance(atlas, str) or atlas not in CHARACTER_ATLASES or not isinstance(clip, str):
			raise ValueError(f"Invalid frame identity: {key}")
		if not isinstance(direction, int) or direction < 0 or not isinstance(frame_number, int) or frame_number < 0:
			raise ValueError(f"Invalid frame identity: {key}")
		expected_key = f"{atlas}/{clip}/d{direction}/f{frame_number}"
		if key != expected_key:
			raise ValueError(f"Frame key does not match its identity: {key}")
		source = _safe_source_path(frame_reference.get("source"))
		expected_source = PurePosixPath(atlas, clip, f"{clip}__d{direction}__f{frame_number}.png")
		if source != expected_source:
			raise ValueError(f"Frame source does not match its identity: {key}")
		if source in written_sources:
			raise ValueError(f"Duplicate reference source path: {source}")
		written_sources.add(source)
		rect = frame_reference.get("rect")
		if not isinstance(rect, dict):
			raise ValueError(f"Missing frame rectangle: {key}")
		expected_size = (rect.get("width"), rect.get("height"))
		if expected_size != (CELL_SIZE, CELL_SIZE):
			raise ValueError(f"Frame rectangle must remain 96x96: {key}")
		x = rect.get("x")
		y = rect.get("y")
		if not isinstance(x, int) or not isinstance(y, int) or x < 0 or y < 0:
			raise ValueError(f"Invalid frame rectangle origin: {key}")
		if x % CELL_SIZE or y % CELL_SIZE:
			raise ValueError(f"Frame rectangle is not aligned to the 96x96 grid: {key}")
		if x + CELL_SIZE > sheet.width or y + CELL_SIZE > sheet.height:
			raise ValueError(f"Frame rectangle falls outside the edited sheet: {key}")
		rectangle = (x, y, CELL_SIZE, CELL_SIZE)
		if rectangle in written_rectangles:
			raise ValueError(f"Duplicate frame rectangle: {key}")
		written_rectangles.add(rectangle)
		cell = frame_reference.get("cell")
		if cell != {"column": x // CELL_SIZE, "row": y // CELL_SIZE}:
			raise ValueError(f"Frame cell does not match its rectangle: {key}")
		frame_exports.append((source, x, y))
	output.mkdir(parents=True, exist_ok=True)
	for source, x, y in frame_exports:
		destination_path = output.joinpath(*source.parts)
		destination_path.parent.mkdir(parents=True, exist_ok=True)
		sheet.crop((x, y, x + CELL_SIZE, y + CELL_SIZE)).save(destination_path, format="PNG", optimize=False)
	manifest_path = output / "parsec-character-sheet.import.json"
	manifest_path.write_text(json.dumps({
		"version": 1,
		"purpose": "human-edit-character-sheet-import",
		"sourceSheet": sheet_file.name,
		"sourceSheetSha256": hashlib.sha256(sheet_file.read_bytes()).hexdigest(),
		"sourceReference": reference_file.name,
		"frameCount": len(frames),
	}, indent=2) + "\n", encoding="utf-8")
	return CharacterReferenceSplit(destination=output, manifest=manifest_path, frame_count=len(frames))


def main() -> int:
	parser = argparse.ArgumentParser(description="Split an edited Parsec character sheet into a safe staging tree.")
	parser.add_argument("--sheet", required=True, type=Path)
	parser.add_argument("--reference", required=True, type=Path)
	parser.add_argument("--output", required=True, type=Path)
	args = parser.parse_args()
	result = split_character_reference(args.sheet, args.reference, args.output)
	print(result.destination)
	print(result.manifest)
	print(f"{result.frame_count} staged character frames")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

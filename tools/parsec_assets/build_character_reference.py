from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, PngImagePlugin

CELL_SIZE = 96
CHARACTER_ATLASES = (
	"parsec-core",
	"parsec-feedback",
	"parsec-touch",
	"parsec-toys",
	"parsec-habitat",
	"parsec-intrusive",
)


@dataclass(frozen=True)
class CharacterReferenceBuild:
	sheet: Path
	reference: Path
	frame_count: int


def _frame_parts(path: Path) -> tuple[str, int, int]:
	parts = path.stem.split("__")
	if len(parts) != 3 or not parts[1].startswith("d") or not parts[2].startswith("f"):
		raise ValueError(f"Expected <clip>__d<direction>__f<frame>.png: {path}")
	return parts[0], int(parts[1][1:]), int(parts[2][1:])


def build_character_reference(
	prepared_root: str | Path,
	destination: str | Path,
	*,
	columns: int = 8,
) -> CharacterReferenceBuild:
	if columns <= 0:
		raise ValueError("columns must be positive")
	output = Path(destination)
	if output.exists() and any(output.iterdir()):
		raise FileExistsError(f"Refusing to overwrite non-empty destination: {output}")
	frames = []
	root = Path(prepared_root)
	for atlas in CHARACTER_ATLASES:
		atlas_root = root / atlas
		if not atlas_root.is_dir():
			continue
		for path in sorted(atlas_root.rglob("*.png")):
			clip, direction, frame = _frame_parts(path)
			frames.append((atlas, clip, direction, frame, path))
	if not frames:
		raise ValueError(f"No production character frames found under {root}")
	frames.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4].as_posix()))
	keys = [f"{atlas}/{clip}/d{direction}/f{frame}" for atlas, clip, direction, frame, _ in frames]
	if len(keys) != len(set(keys)):
		raise ValueError("Production character frame keys must be unique")
	rows = math.ceil(len(frames) / columns)
	sheet = Image.new("RGBA", (columns * CELL_SIZE, rows * CELL_SIZE), (0, 0, 0, 0))
	reference = {}
	for index, ((atlas, clip, direction, frame, path), key) in enumerate(zip(frames, keys, strict=True)):
		with Image.open(path) as opened:
			if opened.mode != "RGBA" or opened.size != (CELL_SIZE, CELL_SIZE):
				raise ValueError(f"{path} must be a 96x96 RGBA PNG")
			column = index % columns
			row = index // columns
			sheet.paste(opened, (column * CELL_SIZE, row * CELL_SIZE))
		reference[key] = {
			"atlas": atlas,
			"clip": clip,
			"direction": direction,
			"frame": frame,
			"cell": {"column": column, "row": row},
			"rect": {"x": column * CELL_SIZE, "y": row * CELL_SIZE, "width": CELL_SIZE, "height": CELL_SIZE},
			"source": path.relative_to(root).as_posix(),
		}
	output.mkdir(parents=True, exist_ok=True)
	sheet_path = output / "parsec-character-sheet.png"
	metadata = PngImagePlugin.PngInfo()
	metadata.add_text("parsec_reference", "human-edit-character-sheet-v1")
	metadata.add_text("parsec_cell_size", "96x96")
	sheet.save(sheet_path, format="PNG", optimize=False, pnginfo=metadata)
	reference_path = output / "parsec-character-sheet.reference.json"
	reference_path.write_text(json.dumps({
		"version": 1,
		"purpose": "human-edit-character-sheet",
		"cellSize": {"width": CELL_SIZE, "height": CELL_SIZE},
		"columns": columns,
		"rows": rows,
		"frameCount": len(frames),
		"frames": reference,
	}, indent=2, sort_keys=False) + "\n", encoding="utf-8")
	return CharacterReferenceBuild(sheet=sheet_path, reference=reference_path, frame_count=len(frames))


def main() -> int:
	parser = argparse.ArgumentParser(description="Build one indexed human-edit sheet for all Parsec character frames.")
	parser.add_argument("--input", required=True, type=Path)
	parser.add_argument("--output", required=True, type=Path)
	parser.add_argument("--columns", type=int, default=8)
	args = parser.parse_args()
	result = build_character_reference(args.input, args.output, columns=args.columns)
	print(result.sheet)
	print(result.reference)
	print(f"{result.frame_count} character frames")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

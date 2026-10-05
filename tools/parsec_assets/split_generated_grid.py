from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from PIL import Image, PngImagePlugin


@dataclass(frozen=True)
class SplitGridRow:
	path: Path
	source_bbox: tuple[int, int, int, int]
	sha256: str


@dataclass(frozen=True)
class SplitGrid:
	metadata_path: Path
	rows: tuple[SplitGridRow, ...]


def split_generated_grid(
	source: str | Path,
	destination: str | Path,
	*,
	name: str,
	rows: int,
) -> SplitGrid:
	if rows < 1:
		raise ValueError("rows must be positive")
	source_path = Path(source)
	output = Path(destination)
	if output.exists() and any(output.iterdir()):
		raise FileExistsError(f"Refusing to overwrite non-empty destination: {output}")
	output.mkdir(parents=True, exist_ok=True)
	source_hash = sha256(source_path.read_bytes()).hexdigest()
	result_rows: list[SplitGridRow] = []
	with Image.open(source_path) as image:
		for row_index in range(rows):
			y_start = round(row_index * image.height / rows)
			y_end = round((row_index + 1) * image.height / rows)
			bbox = (0, y_start, image.width, y_end)
			row = image.crop(bbox)
			path = output / f"{name}__row{row_index}.png"
			metadata = PngImagePlugin.PngInfo()
			metadata.add_text("parsec_grid_split", "equal-row-crop-v1")
			metadata.add_text("parsec_source_sha256", source_hash)
			row.save(path, format="PNG", optimize=False, pnginfo=metadata)
			result_rows.append(SplitGridRow(path=path, source_bbox=bbox, sha256=sha256(path.read_bytes()).hexdigest()))
	metadata_path = output / f"{name}.grid-split.json"
	metadata_path.write_text(json.dumps({
		"tool": "equal-row-crop-v1",
		"source": source_path.as_posix(),
		"sourceSha256": source_hash,
		"rows": [{
			"path": row.path.as_posix(),
			"sourceBbox": row.source_bbox,
			"sha256": row.sha256,
		} for row in result_rows],
	}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
	return SplitGrid(metadata_path=metadata_path, rows=tuple(result_rows))


def main() -> int:
	parser = argparse.ArgumentParser(description="Split a generated sprite grid into lossless horizontal row sources.")
	parser.add_argument("--input", required=True, type=Path)
	parser.add_argument("--output", required=True, type=Path)
	parser.add_argument("--name", required=True)
	parser.add_argument("--rows", required=True, type=int)
	args = parser.parse_args()
	result = split_generated_grid(args.input, args.output, name=args.name, rows=args.rows)
	print(result.metadata_path)
	for row in result.rows:
		print(f"{row.path}\t{row.sha256}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())


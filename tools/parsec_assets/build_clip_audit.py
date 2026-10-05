from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, PngImagePlugin

from tools.parsec_assets.build_contact_sheet import discover_contact_sheet_frames

CELL_SIZE = 384
LABEL_HEIGHT = 32


def build_clip_audit_sheets(
	source: str | Path,
	destination: str | Path,
	*,
	columns: int = 4,
) -> list[Path]:
	if columns <= 0:
		raise ValueError("columns must be positive")
	grouped = defaultdict(list)
	for frame in discover_contact_sheet_frames(source):
		grouped[frame.clip].append(frame)
	output = Path(destination)
	output.mkdir(parents=True, exist_ok=True)
	results: list[Path] = []
	for clip, frames in sorted(grouped.items()):
		ordered = sorted(frames, key=lambda item: (item.direction, item.frame, item.path.as_posix()))
		rows = math.ceil(len(ordered) / columns)
		sheet = Image.new("RGBA", (columns * CELL_SIZE, rows * (CELL_SIZE + LABEL_HEIGHT)), (24, 28, 36, 255))
		draw = ImageDraw.Draw(sheet)
		for index, frame in enumerate(ordered):
			column = index % columns
			row = index // columns
			x = column * CELL_SIZE
			y = row * (CELL_SIZE + LABEL_HEIGHT)
			draw.text((x + 4, y + 8), f"{clip} d{frame.direction} f{frame.frame}", fill=(238, 241, 246, 255))
			with Image.open(frame.path) as opened:
				if opened.mode != "RGBA" or opened.size != (96, 96):
					raise ValueError(f"{frame.path} must be a 96x96 RGBA PNG")
				large = opened.resize((CELL_SIZE, CELL_SIZE), resample=Image.Resampling.NEAREST)
				sheet.alpha_composite(large, (x, y + LABEL_HEIGHT))
		result = output / f"{clip}.png"
		metadata = PngImagePlugin.PngInfo()
		metadata.add_text("parsec_review_scale", "4x-nearest-per-clip")
		metadata.add_text("parsec_review_clip", clip)
		sheet.save(result, format="PNG", optimize=False, pnginfo=metadata)
		results.append(result)
	return results


def main() -> int:
	parser = argparse.ArgumentParser(description="Build readable per-clip 4x Parsec audit sheets.")
	parser.add_argument("--input", required=True, type=Path)
	parser.add_argument("--output", required=True, type=Path)
	parser.add_argument("--columns", type=int, default=4)
	args = parser.parse_args()
	for result in build_clip_audit_sheets(args.input, args.output, columns=args.columns):
		print(result)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

from __future__ import annotations

import argparse
import html
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, PngImagePlugin


@dataclass(frozen=True)
class ContactSheetFrame:
	clip: str
	frame: int
	direction: int
	path: Path
	anchors: dict[str, tuple[int, int]]
	duration_ms: int
	fallback: str
	status: str


@dataclass(frozen=True)
class ContactSheetBuild:
	png: Path
	html: Path
	reduced_motion_html: Path


def discover_contact_sheet_frames(source: str | Path) -> list[ContactSheetFrame]:
	frames: list[ContactSheetFrame] = []
	for path in sorted(Path(source).rglob("*.png")):
		parts = path.stem.split("__")
		if len(parts) != 3 or not parts[1].startswith("d") or not parts[2].startswith("f"):
			continue
		frames.append(ContactSheetFrame(
			clip=parts[0],
			direction=int(parts[1][1:]),
			frame=int(parts[2][1:]),
			path=path,
			anchors={},
			duration_ms=150,
			fallback="unknown",
			status="unreviewed",
		))
	return frames


def _draw_anchors(image: Image.Image, anchors: dict[str, tuple[int, int]], scale: int) -> None:
	draw = ImageDraw.Draw(image)
	for x, y in anchors.values():
		center_x = x * scale + scale // 2
		center_y = y * scale + scale // 2
		radius = max(1, scale)
		draw.line((center_x - radius, center_y, center_x + radius, center_y), fill=(255, 0, 255, 255), width=max(1, scale // 2))
		draw.line((center_x, center_y - radius, center_x, center_y + radius), fill=(255, 0, 255, 255), width=max(1, scale // 2))


def build_contact_sheet(
	frames: Iterable[ContactSheetFrame],
	destination: str | Path,
	*,
	title: str,
) -> ContactSheetBuild:
	ordered = sorted(frames, key=lambda item: (item.clip, item.direction, item.frame, item.path.as_posix()))
	if not ordered:
		raise ValueError("At least one frame is required for a contact sheet")
	output = Path(destination)
	output.mkdir(parents=True, exist_ok=True)
	row_height = 404
	canvas = Image.new("RGBA", (512, row_height * len(ordered)), (24, 28, 36, 255))
	html_rows: list[str] = []
	for row, item in enumerate(ordered):
		with Image.open(item.path) as source:
			if source.mode != "RGBA" or source.size != (96, 96):
				raise ValueError(f"{item.path} must be a 96x96 RGBA PNG")
			native = source.copy()
			large = source.resize((384, 384), resample=Image.Resampling.NEAREST)
		_draw_anchors(native, item.anchors, 1)
		_draw_anchors(large, item.anchors, 4)
		y = row * row_height
		canvas.paste(native, (0, y), native)
		canvas.paste(large, (112, y), large)
		label = f"{item.clip} d{item.direction} f{item.frame} · {item.duration_ms}ms · {item.status} · fallback {item.fallback}"
		ImageDraw.Draw(canvas).text((4, y + 100), label, fill=(238, 241, 246, 255))
		html_rows.append(f"<li><code>{html.escape(label)}</code> — anchors {html.escape(str(item.anchors))}</li>")
	png_path = output / "contact-sheet.png"
	metadata = PngImagePlugin.PngInfo()
	metadata.add_text("parsec_review_scale", "1x+4x-nearest")
	metadata.add_text("parsec_review_title", title)
	canvas.save(png_path, format="PNG", optimize=False, pnginfo=metadata)
	html_path = output / "index.html"
	html_path.write_text(
		f"<!doctype html><meta charset=\"utf-8\"><title>{html.escape(title)}</title>"
		f"<h1>{html.escape(title)}</h1><p>Native and 4x nearest-neighbor review.</p>"
		f"<img src=\"contact-sheet.png\" alt=\"{html.escape(title)} contact sheet\"><ol>{''.join(html_rows)}</ol>\n",
		encoding="utf-8",
	)
	reduced_path = output / "reduced-motion.html"
	reduced_path.write_text(
		f"<!doctype html><meta charset=\"utf-8\"><title>{html.escape(title)} reduced motion</title>"
		f"<h1>{html.escape(title)} reduced-motion representatives</h1><ol>{''.join(html_rows)}</ol>\n",
		encoding="utf-8",
	)
	return ContactSheetBuild(png=png_path, html=html_path, reduced_motion_html=reduced_path)


def main() -> int:
	parser = argparse.ArgumentParser(description="Build native and 4x nearest-neighbor Parsec review output.")
	parser.add_argument("--input", required=True, type=Path)
	parser.add_argument("--output", required=True, type=Path)
	parser.add_argument("--title", default="Parsec asset review")
	args = parser.parse_args()
	frames = discover_contact_sheet_frames(args.input)
	result = build_contact_sheet(frames, args.output, title=args.title)
	print(result.html)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

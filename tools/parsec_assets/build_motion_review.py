from __future__ import annotations

import argparse
import html
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, PngImagePlugin


@dataclass(frozen=True)
class MotionReviewBuild:
	native_gif: Path
	large_gif: Path
	reduced_motion_png: Path
	html: Path


def _review_frame(source: Image.Image, size: tuple[int, int]) -> Image.Image:
	resized = source.resize(size, resample=Image.Resampling.NEAREST)
	backing = Image.new("RGB", size, (24, 28, 36))
	backing.paste(resized.convert("RGB"), (0, 0), resized.getchannel("A"))
	return backing


def build_motion_review(
	frames: Iterable[str | Path],
	destination: str | Path,
	*,
	durations_ms: list[int],
	reduced_motion_index: int,
	title: str,
) -> MotionReviewBuild:
	paths = [Path(path) for path in frames]
	if not paths:
		raise ValueError("At least one reviewed frame is required")
	if len(paths) != len(durations_ms):
		raise ValueError("durations_ms must match the frame count")
	if any(duration <= 0 for duration in durations_ms):
		raise ValueError("durations_ms must be positive")
	if not 0 <= reduced_motion_index < len(paths):
		raise ValueError("reduced_motion_index must reference a frame")
	output = Path(destination)
	if output.exists() and any(output.iterdir()):
		raise FileExistsError(f"Refusing to overwrite non-empty destination: {output}")
	output.mkdir(parents=True, exist_ok=True)
	prepared: list[Image.Image] = []
	for path in paths:
		with Image.open(path) as opened:
			if opened.mode != "RGBA" or opened.size != (96, 96):
				raise ValueError(f"{path} must be a 96x96 RGBA PNG")
			prepared.append(opened.copy())
	native = [_review_frame(frame, (96, 96)) for frame in prepared]
	large = [_review_frame(frame, (384, 384)) for frame in prepared]
	native_path = output / "motion-1x.gif"
	large_path = output / "motion-4x.gif"
	native[0].save(native_path, save_all=True, append_images=native[1:], duration=durations_ms, loop=0, disposal=2)
	large[0].save(large_path, save_all=True, append_images=large[1:], duration=durations_ms, loop=0, disposal=2)
	reduced = Image.new("RGBA", (480, 384), (24, 28, 36, 255))
	representative = prepared[reduced_motion_index]
	reduced.alpha_composite(representative, (0, 0))
	reduced.alpha_composite(representative.resize((384, 384), resample=Image.Resampling.NEAREST), (96, 0))
	reduced_path = output / "reduced-motion.png"
	metadata = PngImagePlugin.PngInfo()
	metadata.add_text("parsec_review_scale", "reduced-motion-1x+4x-nearest")
	metadata.add_text("parsec_review_frame", str(reduced_motion_index))
	reduced.save(reduced_path, format="PNG", optimize=False, pnginfo=metadata)
	html_path = output / "index.html"
	html_path.write_text(
		f"<!doctype html><meta charset=\"utf-8\"><title>{html.escape(title)}</title>"
		f"<h1>{html.escape(title)}</h1><h2>Authored motion</h2>"
		f"<p>Durations: {html.escape(', '.join(str(value) for value in durations_ms))} ms.</p>"
		"<img src=\"motion-1x.gif\" alt=\"Native-size authored motion\">"
		"<img src=\"motion-4x.gif\" alt=\"Four-times nearest-neighbor authored motion\">"
		f"<h2>Reduced motion</h2><p>Representative frame {reduced_motion_index}.</p>"
		"<img src=\"reduced-motion.png\" alt=\"Reduced-motion frame at native and four-times scale\">\n",
		encoding="utf-8",
	)
	return MotionReviewBuild(native_path, large_path, reduced_path, html_path)


def _frame_order(path: Path) -> tuple[int, int, str]:
	parts = path.stem.split("__")
	if len(parts) != 3 or not parts[1].startswith("d") or not parts[2].startswith("f"):
		raise ValueError(f"Expected <clip>__d<direction>__f<frame>.png: {path}")
	return int(parts[1][1:]), int(parts[2][1:]), path.as_posix()


def main() -> int:
	parser = argparse.ArgumentParser(description="Build exact-timing Parsec motion-review artifacts.")
	parser.add_argument("--input", required=True, type=Path)
	parser.add_argument("--output", required=True, type=Path)
	parser.add_argument("--durations", required=True)
	parser.add_argument("--reduced-motion-index", required=True, type=int)
	parser.add_argument("--direction", type=int)
	parser.add_argument("--title", required=True)
	args = parser.parse_args()
	frames = sorted(args.input.rglob("*.png"), key=_frame_order)
	if args.direction is not None:
		frames = [path for path in frames if _frame_order(path)[0] == args.direction]
	result = build_motion_review(
		frames,
		args.output,
		durations_ms=[int(value) for value in args.durations.split(",")],
		reduced_motion_index=args.reduced_motion_index,
		title=args.title,
	)
	print(result.html)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

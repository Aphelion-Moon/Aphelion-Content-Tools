from __future__ import annotations

import subprocess
import sys

from PIL import Image

from tools.parsec_assets.build_motion_review import build_motion_review


def test_builds_exact_timing_native_large_and_reduced_motion_artifacts(tmp_path):
	frames = []
	for index, color in enumerate(((255, 0, 0, 255), (0, 0, 255, 255))):
		path = tmp_path / f"idle__d0__f{index}.png"
		Image.new("RGBA", (96, 96), color).save(path, format="PNG")
		frames.append(path)

	result = build_motion_review(
		frames,
		tmp_path / "review",
		durations_ms=[100, 220],
		reduced_motion_index=1,
		title="Idle",
	)

	with Image.open(result.native_gif) as native:
		assert native.size == (96, 96)
		assert native.n_frames == 2
		native.seek(0)
		assert native.info["duration"] == 100
		native.seek(1)
		assert native.info["duration"] == 220
	with Image.open(result.large_gif) as large:
		assert large.size == (384, 384)
		assert large.n_frames == 2
	with Image.open(result.reduced_motion_png) as reduced:
		assert reduced.size == (480, 384)
		assert reduced.getpixel((0, 0))[:3] == (0, 0, 255)
	assert "Authored motion" in result.html.read_text(encoding="utf-8")


def test_cli_filters_a_directional_clip_before_applying_direction_timing(tmp_path):
	prepared = tmp_path / "prepared"
	prepared.mkdir()
	colors = {
		0: ((255, 0, 0, 255), (128, 0, 0, 255)),
		1: ((0, 255, 0, 255), (0, 128, 0, 255)),
	}
	for direction, frame_colors in colors.items():
		for frame, color in enumerate(frame_colors):
			Image.new("RGBA", (96, 96), color).save(
				prepared / f"walk__d{direction}__f{frame}.png",
				format="PNG",
			)
	output = tmp_path / "review"

	result = subprocess.run([
		sys.executable,
		"tools/parsec_assets/build_motion_review.py",
		"--input", str(prepared),
		"--output", str(output),
		"--durations", "120,120",
		"--reduced-motion-index", "0",
		"--direction", "1",
		"--title", "East walk",
	], check=False, capture_output=True, text=True)

	assert result.returncode == 0, result.stderr
	with Image.open(output / "motion-1x.gif") as motion:
		assert motion.n_frames == 2
		assert motion.convert("RGB").getpixel((0, 0)) == (0, 255, 0)

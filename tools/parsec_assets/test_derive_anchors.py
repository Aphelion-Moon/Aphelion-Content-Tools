from __future__ import annotations

import json
import subprocess
import sys

from PIL import Image, ImageDraw

from tools.parsec_assets.derive_anchors import derive_frame_anchors


def test_derives_profile_attachment_points_from_identity_eye_and_silhouette(tmp_path):
	path = tmp_path / "left-facing.png"
	image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
	draw = ImageDraw.Draw(image)
	draw.rectangle((30, 28, 72, 84), fill=(0, 0, 0, 255))
	draw.rectangle((21, 38, 40, 52), fill=(0, 0, 0, 255))
	draw.rectangle((32, 32, 68, 80), fill=(255, 255, 255, 255))
	draw.rectangle((34, 39, 36, 42), fill=(255, 60, 200, 255))
	image.save(path, format="PNG")

	anchors = derive_frame_anchors(path)

	assert anchors["face"] == {"x": 35, "y": 40}
	assert anchors["mouth"] == {"x": 21, "y": 46}
	assert anchors["scruff"]["x"] > anchors["face"]["x"]
	assert anchors["toy"] == anchors["mouth"]
	assert anchors["effect"]["y"] < anchors["face"]["y"]
	assert anchors["feet"]["y"] == 84
	assert anchors["shadow"] == anchors["feet"]


def test_derives_right_profile_mouth_on_the_right_side(tmp_path):
	path = tmp_path / "right-facing.png"
	image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
	draw = ImageDraw.Draw(image)
	draw.rectangle((24, 28, 66, 84), fill=(0, 0, 0, 255))
	draw.rectangle((56, 38, 75, 52), fill=(0, 0, 0, 255))
	draw.rectangle((28, 32, 64, 80), fill=(255, 255, 255, 255))
	draw.rectangle((60, 39, 62, 42), fill=(251, 212, 54, 255))
	image.save(path, format="PNG")

	anchors = derive_frame_anchors(path)

	assert anchors["face"] == {"x": 61, "y": 40}
	assert anchors["mouth"] == {"x": 75, "y": 46}
	assert anchors["scruff"]["x"] < anchors["face"]["x"]


def test_uses_the_largest_component_for_body_anchors_and_detached_art_for_effects(tmp_path):
	path = tmp_path / "effect-frame.png"
	image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
	draw = ImageDraw.Draw(image)
	draw.rectangle((20, 28, 70, 84), fill=(0, 0, 0, 255))
	draw.rectangle((30, 38, 32, 41), fill=(255, 60, 200, 255))
	draw.rectangle((82, 10, 84, 12), fill=(255, 180, 20, 255))
	image.save(path, format="PNG")

	anchors = derive_frame_anchors(path)

	assert anchors["effect"] == {"x": 83, "y": 11}
	assert anchors["feet"]["x"] == 45
	assert anchors["interaction"] == {"x": 45, "y": 56}


def test_writes_anchor_map_using_atlas_frame_keys(tmp_path):
	prepared = tmp_path / "prepared" / "core-idle-seated"
	prepared.mkdir(parents=True)
	frame = prepared / "core-idle-seated__d0__f0.png"
	image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
	draw = ImageDraw.Draw(image)
	draw.rectangle((20, 20, 70, 84), fill=(0, 0, 0, 255))
	draw.rectangle((30, 30, 32, 33), fill=(255, 60, 200, 255))
	image.save(frame, format="PNG")
	output = tmp_path / "anchors.json"

	result = subprocess.run([
		sys.executable,
		"tools/parsec_assets/derive_anchors.py",
		"--input", str(tmp_path / "prepared"),
		"--atlas", "parsec-core",
		"--output", str(output),
	], check=False, capture_output=True, text=True)

	assert result.returncode == 0, result.stderr
	anchors = json.loads(output.read_text(encoding="utf-8"))
	assert list(anchors) == ["parsec-core/core-idle-seated/d0/f0"]
	assert anchors["parsec-core/core-idle-seated/d0/f0"]["face"] == {"x": 31, "y": 32}

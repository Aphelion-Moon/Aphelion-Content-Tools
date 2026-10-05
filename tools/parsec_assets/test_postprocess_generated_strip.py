from __future__ import annotations

import json

from PIL import Image, ImageDraw

from tools.parsec_assets.postprocess_generated_strip import postprocess_generated_strip


def test_does_not_refill_exterior_concavities_near_identity_eyes():
	from tools.parsec_assets.postprocess_generated_strip import _isolate_foreground

	image = Image.new("RGB", (96, 96), "white")
	draw = ImageDraw.Draw(image)
	draw.rectangle((20, 10, 60, 75), fill="black")
	draw.rectangle((24, 14, 56, 71), fill="white")
	draw.rectangle((30, 25, 32, 28), fill=(255, 60, 200))
	draw.line((20, 34, 60, 34), fill="black")
	# An open notch below the muzzle is background, even inside the head's convex hull.
	draw.rectangle((18, 36, 26, 46), fill="white")
	isolate, _ = _isolate_foreground(image, 1, equal_panel_split=True)
	assert isolate.getpixel((22, 40))[3] == 0
	assert isolate.getpixel((40, 20))[3] == 255


def _alpha_component_count(image):
	pixels = image.load()
	remaining = {
		(x, y)
		for y in range(image.height)
		for x in range(image.width)
		if pixels[x, y][3]
	}
	components = 0
	while remaining:
		components += 1
		pending = [remaining.pop()]
		while pending:
			x, y = pending.pop()
			for next_y in range(max(0, y - 1), min(image.height, y + 2)):
				for next_x in range(max(0, x - 1), min(image.width, x + 2)):
					point = (next_x, next_y)
					if point in remaining:
						remaining.remove(point)
						pending.append(point)
	return components


def _opaque_boundary_pixels(image):
	pixels = image.load()
	boundary = []
	for y in range(image.height):
		for x in range(image.width):
			if not pixels[x, y][3]:
				continue
			if any(
				0 <= next_x < image.width
				and 0 <= next_y < image.height
				and not pixels[next_x, next_y][3]
				for next_y in range(y - 1, y + 2)
				for next_x in range(x - 1, x + 2)
			):
				boundary.append(pixels[x, y])
	return boundary


def _make_checkerboard_strip(path):
	image = Image.new("RGB", (400, 120), (254, 254, 254))
	draw = ImageDraw.Draw(image)
	for y in range(0, image.height, 10):
		for x in range(0, image.width, 10):
			if (x // 10 + y // 10) % 2:
				draw.rectangle((x, y, x + 9, y + 9), fill=(247, 247, 247))
	for index in range(4):
		x = index * 100 + 24
		draw.rectangle((x, 24, x + 51, 99), fill=(0, 0, 0))
		draw.rectangle((x + 5, 29, x + 46, 94), fill=(255, 255, 255))
		draw.rectangle((x, 58, x + 3, 67), fill=(255, 255, 255))
		draw.rectangle((x + 12, 43, x + 18, 49), fill=(244, 18, 182))
		draw.rectangle((x + 12, 72, x + 18, 78), fill=(240, 80, 120))
		draw.rectangle((x - 12, 48, x - 10, 50), fill=(20, 210, 235))
		if index == 2:
			draw.rectangle((x + 51, 78, x + 76, 84), fill=(0, 0, 0))
	image.save(path, format="PNG")


def test_removes_only_connected_checkerboard_and_preserves_identity_colors(tmp_path):
	source = tmp_path / "generated-strip.png"
	_make_checkerboard_strip(source)
	result = postprocess_generated_strip(
		source,
		tmp_path / "prepared",
		clip="core-idle-seated",
		expected_frames=4,
		max_art_width=72,
		max_art_height=72,
		baseline_y=88,
		keep_auxiliary_components=True,
	)
	assert len(result.frames) == 4
	assert result.source_sha256
	assert json.loads(result.metadata_path.read_text())["identityPalette"] == {
		"leftEye": "#FBD436", "rightEye": "#FF3CC8", "laterality": "anatomical",
	}
	assert len({frame.resized_size[1] for frame in result.frames}) == 1
	assert result.frames[3].resized_size[0] == result.frames[0].resized_size[0]
	for index, frame in enumerate(result.frames):
		assert frame.path.name == f"core-idle-seated__d0__f{index}.png"
		with Image.open(frame.path) as prepared:
			assert prepared.mode == "RGBA"
			assert prepared.size == (96, 96)
			assert prepared.getpixel((0, 0)) == (0, 0, 0, 0)
			assert prepared.getbbox() is not None
			assert prepared.getbbox()[3] == 89
			pixels = list(prepared.getdata())
			assert pixels.count((255, 255, 255, 255)) > 500
			assert (255, 60, 200, 255) in pixels
			assert (240, 96, 96, 255) in pixels
			assert (80, 220, 235, 255) in pixels


def test_removes_connected_checkerboard_with_dark_224_cells(tmp_path):
	source = tmp_path / "dark-checker-strip.png"
	image = Image.new("RGB", (400, 120), (235, 235, 235))
	draw = ImageDraw.Draw(image)
	for y in range(0, image.height, 20):
		for x in range(0, image.width, 20):
			if (x // 20 + y // 20) % 2:
				draw.rectangle((x, y, x + 19, y + 19), fill=(224, 224, 224))
	for index in range(4):
		x = index * 100 + 30
		draw.rectangle((x, 30, x + 39, 99), fill=(0, 0, 0))
		draw.rectangle((x + 5, 35, x + 34, 94), fill=(255, 255, 255))
		draw.rectangle((x + 12, 48, x + 17, 53), fill=(255, 60, 200))
		draw.point((x + 20, 20), fill=(216, 214, 214))
	image.save(source, format="PNG")

	result = postprocess_generated_strip(
		source,
		tmp_path / "prepared",
		clip="reconnect-pant",
		expected_frames=4,
	)

	assert len(result.frames) == 4
	for frame in result.frames:
		with Image.open(frame.path) as prepared:
			assert prepared.getpixel((0, 0)) == (0, 0, 0, 0)
			assert _alpha_component_count(prepared) == 1


def test_replaces_light_silhouette_fringe_with_one_pixel_dark_outline(tmp_path):
	source = tmp_path / "light-fringe-strip.png"
	image = Image.new("RGBA", (400, 120), (0, 0, 0, 0))
	draw = ImageDraw.Draw(image)
	for index in range(4):
		x = index * 100 + 25
		draw.rectangle((x, 24, x + 49, 99), fill=(196, 196, 196, 255))
		draw.rectangle((x + 2, 26, x + 47, 97), fill=(8, 8, 8, 255))
		draw.rectangle((x + 8, 32, x + 41, 91), fill=(255, 255, 255, 255))
		draw.rectangle((x + 12, 42, x + 17, 47), fill=(255, 60, 200, 255))
	image.save(source, format="PNG")

	result = postprocess_generated_strip(
		source,
		tmp_path / "prepared",
		clip="outlined",
		expected_frames=4,
		equal_panel_split=True,
	)

	for frame in result.frames:
		with Image.open(frame.path) as prepared:
			boundary = _opaque_boundary_pixels(prepared)
			assert boundary
			assert all(max(pixel[:3]) <= 24 for pixel in boundary)
			assert (255, 255, 255, 255) in prepared.getdata()


def test_rejects_a_strip_without_foreground_in_every_frame_slot(tmp_path):
	source = tmp_path / "empty-strip.png"
	Image.new("RGB", (400, 120), (250, 250, 250)).save(source, format="PNG")
	try:
		postprocess_generated_strip(source, tmp_path / "prepared", clip="idle", expected_frames=4)
	except ValueError as error:
		assert "frame slot 0 has no foreground" in str(error)
	else:
		raise AssertionError("Expected an empty generated strip to be rejected")


def test_uses_an_explicit_clip_scale_for_cross_direction_consistency(tmp_path):
	source = tmp_path / "generated-strip.png"
	_make_checkerboard_strip(source)
	result = postprocess_generated_strip(
		source,
		tmp_path / "prepared",
		clip="walk",
		expected_frames=4,
		max_art_width=96,
		max_art_height=96,
		baseline_y=95,
		scale_override=0.5,
	)
	assert result.frames[0].resized_size[1] == 38


def test_equal_panel_split_recovers_separate_frames_from_transparent_canvas_noise(tmp_path):
	source = tmp_path / "noisy-transparent-strip.png"
	image = Image.new("RGBA", (400, 120), (0, 0, 0, 0))
	draw = ImageDraw.Draw(image)
	for index in range(4):
		x = index * 100 + 24
		draw.rectangle((x, 24, x + 51, 99), fill=(0, 0, 0, 255))
		draw.rectangle((x + 5, 29, x + 46, 94), fill=(255, 255, 255, 255))
		draw.rectangle((x + 12, 43, x + 18, 49), fill=(255, 60, 200, 255))
	draw.line((0, 8, 399, 8), fill=(20, 20, 20, 32), width=1)
	image.save(source, format="PNG")

	try:
		postprocess_generated_strip(source, tmp_path / "automatic", clip="noisy", expected_frames=4)
	except ValueError as error:
		assert "separated frame silhouettes" in str(error)
	else:
		raise AssertionError("Expected transparent canvas noise to defeat automatic silhouette splitting")

	result = postprocess_generated_strip(
		source,
		tmp_path / "panel-split",
		clip="noisy",
		expected_frames=4,
		equal_panel_split=True,
	)

	assert len(result.frames) == 4
	for frame in result.frames:
		with Image.open(frame.path) as prepared:
			assert _alpha_component_count(prepared) == 1

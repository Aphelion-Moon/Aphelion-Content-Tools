from __future__ import annotations

from PIL import Image

from tools.parsec_assets import transform_prepared_frame

erase_prepared_frame_rectangles = transform_prepared_frame.erase_prepared_frame_rectangles
flip_prepared_frame = transform_prepared_frame.flip_prepared_frame


def test_flips_96_pixel_frame_horizontally_without_resampling(tmp_path):
	source = tmp_path / "source.png"
	image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
	image.putpixel((3, 10), (251, 212, 54, 255))
	image.save(source, format="PNG")
	result = flip_prepared_frame(source, tmp_path / "flipped.png")
	with Image.open(result.path) as flipped:
		assert flipped.getpixel((92, 10)) == (251, 212, 54, 255)
		assert flipped.getpixel((3, 10)) == (0, 0, 0, 0)
	assert result.source_sha256


def test_erases_only_recorded_rectangles_without_resampling(tmp_path):
	source = tmp_path / "source.png"
	image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
	image.putpixel((3, 10), (255, 255, 255, 255))
	image.putpixel((40, 40), (251, 212, 54, 255))
	image.save(source, format="PNG")
	result = erase_prepared_frame_rectangles(
		source,
		tmp_path / "cleaned.png",
		rectangles=[(2, 9, 5, 12)],
		reason="detached edge residue",
	)
	with Image.open(result.path) as cleaned:
		assert cleaned.getpixel((3, 10)) == (0, 0, 0, 0)
		assert cleaned.getpixel((40, 40)) == (251, 212, 54, 255)
		assert cleaned.text["parsec_transform"] == "localized-alpha-erase-v1"
		assert cleaned.text["parsec_transform_reason"] == "detached edge residue"
		assert cleaned.text["parsec_transform_rectangles"] == "2,9,5,12"
	assert result.source_sha256


def test_replaces_only_the_selected_color_inside_recorded_rectangles(tmp_path):
	source = tmp_path / "source.png"
	image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
	image.putpixel((3, 10), (255, 60, 200, 255))
	image.putpixel((4, 10), (251, 212, 54, 255))
	image.putpixel((40, 40), (255, 60, 200, 255))
	image.save(source, format="PNG")
	result = transform_prepared_frame.replace_prepared_frame_color_in_rectangles(
		source,
		tmp_path / "corrected.png",
		rectangles=[(2, 9, 6, 12)],
		source_color=(255, 60, 200, 255),
		target_color=(20, 20, 24, 255),
		reason="profile nose identity-color cleanup",
	)
	with Image.open(result.path) as corrected:
		assert corrected.getpixel((3, 10)) == (20, 20, 24, 255)
		assert corrected.getpixel((4, 10)) == (251, 212, 54, 255)
		assert corrected.getpixel((40, 40)) == (255, 60, 200, 255)
		assert corrected.text["parsec_transform"] == "localized-color-replacement-v1"
		assert corrected.text["parsec_transform_reason"] == "profile nose identity-color cleanup"
	assert result.source_sha256


def test_adds_a_dark_outline_to_the_main_subject_without_altering_detached_effects(tmp_path):
	source = tmp_path / "source.png"
	image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
	for y in range(20, 70):
		for x in range(24, 64):
			image.putpixel((x, y), (255, 255, 255, 255))
	image.putpixel((82, 20), (190, 190, 190, 255))
	image.save(source, format="PNG")

	result = transform_prepared_frame.outline_prepared_frame(
		source,
		tmp_path / "outlined.png",
		reason="remove generated white silhouette fringe",
	)

	with Image.open(result.path) as outlined:
		assert outlined.getpixel((24, 20)) == (0, 0, 0, 255)
		assert outlined.getpixel((25, 21)) == (255, 255, 255, 255)
		assert outlined.getpixel((82, 20)) == (190, 190, 190, 255)
		assert outlined.text["parsec_transform"] == "dark-silhouette-outline-v1"
		assert outlined.text["parsec_transform_reason"] == "remove generated white silhouette fringe"

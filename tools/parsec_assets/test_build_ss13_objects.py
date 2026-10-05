from __future__ import annotations

import pytest
from PIL import Image, PngImagePlugin

from tools.parsec_assets.build_ss13_objects import DEFAULT_SOURCES, ObjectSource, build_object_atlas


def test_frozen_object_roster_uses_the_ss13_cable_coil_for_tug_play():
	tug = next(source for source in DEFAULT_SOURCES if source.id == "tug-rope")
	assert tug.path == "icons/obj/stack_objects.dmi"
	assert tug.state == "coil"


def test_cage_family_uses_one_scale_and_baseline_with_locked_overlay_composition():
	cages = [source for source in DEFAULT_SOURCES if source.id.startswith("cage-")]
	assert {(source.scale, source.baseline_y) for source in cages} == {(3, 90)}
	locked = next(source for source in cages if source.id == "cage-locked")
	assert locked.base_state == "pet_carrier_closed"


def test_builds_registered_object_atlas_with_recorded_scale_and_baseline(tmp_path):
	repository = tmp_path / "rift"
	source = repository / "icons" / "fixture.dmi"
	source.parent.mkdir(parents=True)
	image = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
	for y in range(10, 14):
		for x in range(8, 13):
			image.putpixel((x, y), (255, 0, 255, 255))
	metadata = PngImagePlugin.PngInfo()
	metadata.add_text("Description", "# BEGIN DMI\nversion = 4.0\nwidth = 32\nheight = 32\nstate = \"toy\"\ndirs = 1\nframes = 1\n# END DMI")
	image.save(source, format="PNG", pnginfo=metadata)
	result = build_object_atlas(
		[ObjectSource("toy", "icons/fixture.dmi", "toy", scale=3, baseline_y=80)],
		repository,
		tmp_path / "output",
	)
	assert result.png.name == "ss13-objects.png"
	with Image.open(result.png) as atlas:
		assert atlas.getchannel("A").getbbox() == (40, 68, 55, 80)
	source_records = (tmp_path / "output" / "ss13-objects.sources.json").read_text(encoding="utf-8")
	assert '"scale": 3' in source_records
	assert '"baseline_y": 80' in source_records
	assert (tmp_path / "output" / "source" / "ss13-objects" / "toy" / "toy-f000-d00.png").is_file()
	assert (tmp_path / "output" / "prepared" / "ss13-objects" / "toy__d0__f0.png").is_file()
	assert not (tmp_path / "output" / "prepared" / "toy__d0__f0.png").exists()


def test_existing_final_atlas_leaves_destination_unchanged_on_collision(tmp_path):
	repository = tmp_path / "rift"
	source = repository / "icons" / "fixture.dmi"
	source.parent.mkdir(parents=True)
	image = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
	for y in range(10, 14):
		for x in range(8, 13):
			image.putpixel((x, y), (255, 0, 255, 255))
	metadata = PngImagePlugin.PngInfo()
	metadata.add_text("Description", "# BEGIN DMI\nversion = 4.0\nwidth = 32\nheight = 32\nstate = \"toy\"\ndirs = 1\nframes = 1\n# END DMI")
	image.save(source, format="PNG", pnginfo=metadata)

	output = tmp_path / "output"
	output.mkdir()
	sentinel = output / "ss13-objects.png"
	sentinel.write_bytes(b"existing atlas")
	before = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}

	with pytest.raises(FileExistsError, match="Refusing to replace"):
		build_object_atlas(
			[ObjectSource("toy", "icons/fixture.dmi", "toy")],
			repository,
			output,
		)

	after = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
	assert after == before

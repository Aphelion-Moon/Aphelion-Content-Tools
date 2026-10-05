import json
from functools import cache
from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "webapp/frontend/src/assets/parsec"
PINK = (255, 60, 200, 255)
YELLOW = (251, 212, 54, 255)


@cache
def _historical_records():
	manifest = json.loads((ASSETS / "source/touchups/2026-09-09/manifest.json").read_text())
	return {record["outputAtReview"]: record for record in manifest["frames"]}


def historical_image(path):
	"""Replay the September artwork for its coordinate-specific regression checks."""
	record = _historical_records()[path.relative_to(ROOT).as_posix()]
	with Image.open(ROOT / record["source"]) as source:
		image = source.copy()
	patch = json.loads((ROOT / record["patch"]).read_text())
	for edit in patch["edits"]:
		image.putpixel(tuple(edit["point"]), tuple(edit["after"]))
	return image


def test_reviewed_touchups_reproduce_exact_historical_pixels():
	manifest = json.loads((ASSETS / "source/touchups/2026-09-09/manifest.json").read_text())
	assert manifest["identityPalette"] == {"anatomicalLeft": "#FF3CC8", "anatomicalRight": "#FBD436"}
	assert len(manifest["frames"]) == 277  # 276 actor frames and the legacy fallback sheet
	assert manifest["status"] == "historical"
	for record in manifest["frames"]:
		source = ROOT / record["source"]
		assert sha256(source.read_bytes()).hexdigest() == record["sourceSha256"]
		with Image.open(source) as image:
			replayed = image.copy()
		patch = json.loads((ROOT / record["patch"]).read_text())
		for edit in patch["edits"]:
			point = tuple(edit["point"])
			assert replayed.getpixel(point) == tuple(edit["before"])
			replayed.putpixel(point, tuple(edit["after"]))
		assert sha256(replayed.tobytes()).hexdigest() == record["outputPixelSha256"]
		for eye in patch["eyes"]:
			assert replayed.getpixel(tuple(eye["point"])) == (PINK if eye["side"] == "left" else YELLOW)


def test_all_actor_atlas_crops_match_their_prepared_sources():
	count = 0
	for root in sorted((ASSETS / "prepared").glob("parsec-*")):
		if root.name == "parsec-effects":
			continue
		coordinates = json.loads((ASSETS / f"{root.name}.json").read_text())
		with Image.open(ASSETS / f"{root.name}.png") as atlas:
			for path in root.rglob("*.png"):
				clip, direction, frame = path.stem.split("__")
				box = coordinates[f"{root.name}/{clip}/{direction}/{frame}"]
				with Image.open(path) as prepared:
					crop = atlas.crop((box["x"], box["y"], box["x"] + box["width"], box["y"] + box["height"]))
					assert crop.tobytes() == prepared.tobytes(), path
				count += 1
	assert count == 276


def test_historical_seated_jaw_is_transparent_and_white_chest_is_preserved():
	path = ASSETS / "prepared/parsec-core/core-idle-seated/core-idle-seated__d0__f0.png"
	with historical_image(path) as image:
		assert image.getpixel((18, 49))[3] == 0
		assert image.getpixel((35, 60)) == (255, 255, 255, 255)


def test_cardinal_profiles_and_front_have_correct_anatomical_eyes():
	root = ASSETS / "prepared/parsec-core/core-walk-cardinal"
	for direction in (1, 2, 3):
		for path in root.rglob(f"*__d{direction}__f*.png"):
			with Image.open(path) as image:
				pink = [x for y in range(96) for x in range(96) if image.getpixel((x, y)) == PINK]
				yellow = [x for y in range(96) for x in range(96) if image.getpixel((x, y)) == YELLOW]
				if direction == 1:  # faces right: anatomical left visible
					assert yellow and not pink
				elif direction == 3:  # faces left: anatomical right visible
					assert pink and not yellow
				else:
					assert pink and yellow and max(pink) < min(yellow)


def test_historical_profile_iris_does_not_retain_old_pink_edge_pixels():
	path = ASSETS / "prepared/parsec-core/core-idle-standing/core-idle-standing__d0__f0.png"
	with historical_image(path) as image:
		assert image.getpixel((19, 37)) == YELLOW


@pytest.mark.parametrize("clip,point", [
	("core-idle-seated", (27, 14)),
	("core-idle-standing", (22, 26)),
	("core-idle-pant", (26, 11)),
])
def test_historical_marked_ear_bridges_are_open_to_the_background(clip, point):
	path = ASSETS / f"prepared/parsec-core/{clip}/{clip}__d0__f0.png"
	with historical_image(path) as image:
		# The pocket and its artificial roof must both be transparent.
		x, bottom = point
		assert all(image.getpixel((x, y))[3] == 0 for y in range(bottom + 1))


@pytest.mark.parametrize("frame,point", [
	(0, (14, 72)), (1, (15, 73)), (2, (15, 72)), (3, (15, 72)), (4, (14, 72)),
])
def test_historical_search_sniff_has_no_white_strip_outside_the_forehead(frame, point):
	path = ASSETS / f"prepared/parsec-feedback/search-sniff/search-sniff__d0__f{frame}.png"
	with historical_image(path) as image:
		assert image.getpixel(point)[3] == 0


def test_historical_diagonal_ear_cleanup_preserves_both_inner_ears():
	root = ASSETS / "prepared/parsec-core/core-walk-diagonal"
	path = next(root.rglob("*__d1__f0.png"))
	with historical_image(path) as image:
		assert image.getpixel((53, 34))[3] == 0  # exterior wedge behind the ear
		assert image.getpixel((67, 29))[3] == 0  # bridge between ears
		for point in ((60, 32), (73, 34)):
			assert image.getpixel(point)[3] == 255
			assert min(image.getpixel(point)[:3]) > 170


def test_historical_lowered_head_keeps_white_inside_the_forward_ear():
	path = ASSETS / "prepared/parsec-feedback/search-sniff/search-sniff__d0__f3.png"
	with historical_image(path) as image:
		assert image.getpixel((22, 61)) == (255, 255, 255, 255)

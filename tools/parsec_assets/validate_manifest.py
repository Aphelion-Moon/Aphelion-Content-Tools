from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image

from tools.parsec_assets.visual_lint import VisualRules, lint_clip_frames

_CLIP_PATTERN = re.compile(
	r"\{ id: '(?P<id>[^']+)', atlas: '(?P<atlas>[^']+)', plannedUniqueFrames: (?P<count>\d+), "
	r"fallback: '(?P<fallback>[^']+)', loopMode: '(?P<mode>[^']+)', requiredAnchors: \[(?P<anchors>[^]]*)] \},"
)
_TUPLE_PATTERN = re.compile(r"\['(?P<id>[^']+)', '(?P<source>[^']+)', '(?P<fallback>[^']+)'\],")
_OBJECT_TUPLE_PATTERN = re.compile(
	r"\['(?P<id>[^']+)', '(?P<source>[^']+)', '(?P<fallback>[^']+)', "
	r"'(?P<frame>[^']+)', '(?P<provenance>[^']+)'\],"
)
_ACCEPTED_CLIP_PATTERN = re.compile(
	r"^\s*\{ id: '(?P<id>[^']+)', atlas: '(?P<atlas>[^']+)', directions: (?P<directions>\d+), "
	r"framesPerDirection: (?P<frames>\d+),",
	flags=re.MULTILINE,
)


def _fallback_frame(required_anchors: list[str]) -> dict[str, Any]:
	defaults = {
		"feet": {"x": 48, "y": 82},
		"face": {"x": 48, "y": 30},
		"scruff": {"x": 48, "y": 24},
		"mouth": {"x": 56, "y": 34},
		"interaction": {"x": 48, "y": 44},
		"toy": {"x": 62, "y": 48},
		"effect": {"x": 48, "y": 12},
		"shadow": {"x": 48, "y": 84},
	}
	return {"anchors": {anchor: defaults[anchor] for anchor in required_anchors}}


def load_prepared_manifest(path: str | Path) -> dict[str, Any]:
	manifest_path = Path(path)
	text = manifest_path.read_text(encoding="utf-8")
	review_path = manifest_path.parent / "parsec-visual-reviews.v1.json"
	visual_reviews: dict[str, Any] = {}
	visual_reason_codes: dict[str, str] = {}
	review_error: str | None = None
	if review_path.is_file():
		review_inventory = json.loads(review_path.read_text(encoding="utf-8"))
		visual_reviews = review_inventory.get("clips", {})
		visual_reason_codes = review_inventory.get("reasonCodes", {})
	else:
		review_error = "production visual-review inventory is missing"
	clips: dict[str, Any] = {}
	for name in ("seated-idle", "working-patrol", "happy-reaction", "twerking-reaction"):
		clips[name] = {
			"frames": [_fallback_frame(["feet", "face"])],
			"requiredAnchors": ["feet", "face"],
			"fallback": None,
			"requiredForCreativeSprint": False,
			"creativeStatus": "accepted",
		}
	for match in _CLIP_PATTERN.finditer(text):
		anchors = re.findall(r"'([^']+)'", match.group("anchors"))
		clips[match.group("id")] = {
			"atlas": match.group("atlas"),
			"plannedUniqueFrames": int(match.group("count")),
			"loopMode": match.group("mode"),
			"frames": [_fallback_frame(anchors)],
			"requiredAnchors": anchors,
			"fallback": match.group("fallback"),
			"requiredForCreativeSprint": True,
			"creativeStatus": "fallback",
		}
	accepted_specs = [
		{
			"id": match.group("id"),
			"atlas": match.group("atlas"),
			"directions": int(match.group("directions")),
			"framesPerDirection": int(match.group("frames")),
		}
		for match in _ACCEPTED_CLIP_PATTERN.finditer(text)
	]
	artifact_errors: list[str] = [review_error] if review_error else []
	accepted_spec_ids = {spec["id"] for spec in accepted_specs}
	for unexpected_review in sorted(set(visual_reviews) - accepted_spec_ids):
		artifact_errors.append(f"visual review references unknown clip {unexpected_review}")
	sheets: dict[str, Any] = {}
	atlas_data: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
	for atlas in sorted({spec["atlas"] for spec in accepted_specs}):
		coordinates_path = manifest_path.parent / f"{atlas}.json"
		anchors_path = manifest_path.parent / f"{atlas}.anchors.json"
		atlas_path = manifest_path.parent / f"{atlas}.png"
		if not coordinates_path.is_file():
			artifact_errors.append(f"{atlas} coordinates file is missing")
			coordinates = {}
		else:
			coordinates = json.loads(coordinates_path.read_text(encoding="utf-8"))
		if not anchors_path.is_file():
			artifact_errors.append(f"{atlas} anchors file is missing")
			anchors = {}
		else:
			anchors = json.loads(anchors_path.read_text(encoding="utf-8"))
		atlas_data[atlas] = (coordinates, anchors)
		if not atlas_path.is_file():
			artifact_errors.append(f"{atlas} PNG is missing")
			continue
		with Image.open(atlas_path) as atlas_image:
			sheets[atlas] = {
				"path": atlas_path.as_posix(),
				"width": atlas_image.width,
				"height": atlas_image.height,
				"mode": atlas_image.mode,
			}
			if atlas_image.mode != "RGBA":
				artifact_errors.append(f"{atlas} PNG mode must be RGBA, got {atlas_image.mode}")
			if atlas_image.width % 96 or atlas_image.height % 96:
				artifact_errors.append(f"{atlas} PNG dimensions must be multiples of 96")
	accepted_frame_ids_by_atlas: dict[str, set[str]] = {}
	for accepted in accepted_specs:
		clip_id = accepted["id"]
		clip = clips.get(clip_id)
		if clip is None:
			artifact_errors.append(f"accepted clip {clip_id} is absent from the frozen roster")
			continue
		coordinates, anchors = atlas_data.get(accepted["atlas"], ({}, {}))
		frame_ids = [
			f"{accepted['atlas']}/{clip_id}/d{direction}/f{frame_index}"
			for direction in range(accepted["directions"])
			for frame_index in range(accepted["framesPerDirection"])
		]
		accepted_frame_ids_by_atlas.setdefault(accepted["atlas"], set()).update(frame_ids)
		frames = []
		for frame_id in frame_ids:
			coordinate = coordinates.get(frame_id)
			frame_anchors = anchors.get(frame_id)
			if coordinate is None:
				artifact_errors.append(f"{clip_id} is missing coordinate {frame_id}")
				coordinate = {}
			if frame_anchors is None:
				artifact_errors.append(f"{clip_id} is missing anchors {frame_id}")
				frame_anchors = {}
			frames.append({
				"id": frame_id,
				"sheetId": accepted["atlas"],
				**coordinate,
				"anchors": frame_anchors,
			})
		clip["frames"] = frames
		clip["creativeStatus"] = "accepted"
		clip["creativeReview"] = visual_reviews.get(clip_id)
	for atlas, accepted_frame_ids in accepted_frame_ids_by_atlas.items():
		coordinates, anchors = atlas_data[atlas]
		for unexpected in sorted(set(coordinates) - accepted_frame_ids):
			artifact_errors.append(f"{atlas} has unregistered coordinate {unexpected}")
		for unexpected in sorted(set(anchors) - accepted_frame_ids):
			artifact_errors.append(f"{atlas} has unregistered anchors {unexpected}")
	for accepted in accepted_specs:
		clip_id = accepted["id"]
		clip = clips.get(clip_id)
		if clip is None:
			continue
		review = clip.get("creativeReview")
		if not review or review.get("status") != "coherent-reuse":
			continue
		target_id = review.get("target")
		target = clips.get(target_id)
		if not target or target.get("creativeStatus") != "accepted":
			artifact_errors.append(f"{clip_id} coherent reuse target {target_id} is not an accepted clip")
			continue
		clip["atlas"] = target.get("atlas")
		clip["frames"] = target.get("frames", [])
		clip["creativeStatus"] = "coherent-reuse"
		clip["fallback"] = target_id
	for accepted in accepted_specs:
		clip_id = accepted["id"]
		review = visual_reviews.get(clip_id)
		if not review:
			continue
		reason = review.get("reason")
		if reason not in visual_reason_codes:
			artifact_errors.append(f"{clip_id} visual review uses unknown reason {reason}")
			continue
		if review.get("status") != "accepted":
			continue
		prepared = manifest_path.parent / "prepared" / accepted["atlas"] / clip_id
		paths = sorted(prepared.rglob("*.png"))
		if not paths:
			artifact_errors.append(f"{clip_id} has no prepared frames for production visual lint")
			continue
		visual_errors = lint_clip_frames(
			paths,
			VisualRules(max_components=12, max_detached_component_pixels=8),
		)
		for visual_error in visual_errors:
			is_pose_metric = visual_error.startswith("clip: baseline jitter") or visual_error.startswith("clip: occupied-height")
			is_separated_component = "detached alpha component" in visual_error
			if reason == "intentional-pose-range" and is_pose_metric:
				continue
			if reason == "intentional-separated-landing-dust" and (is_pose_metric or is_separated_component):
				continue
			if reason in {"intentional-separated-effect", "exact-ss13-effect"} and (is_pose_metric or is_separated_component):
				continue
			artifact_errors.append(f"{clip_id} visual lint: {visual_error}")
	objects: dict[str, Any] = {}
	sounds: dict[str, Any] = {}
	object_section = text.split("objects: Object.fromEntries([", 1)[1].split("].map", 1)[0]
	accepted_object_ids: set[str] = set()
	for match in _OBJECT_TUPLE_PATTERN.finditer(object_section):
		frame_id = match.group("frame")
		atlas_id = frame_id.split("/", 1)[0]
		coordinates_path = manifest_path.parent / f"{atlas_id}.json"
		atlas_path = manifest_path.parent / f"{atlas_id}.png"
		coordinates = json.loads(coordinates_path.read_text(encoding="utf-8")) if coordinates_path.is_file() else {}
		if not coordinates_path.is_file():
			artifact_errors.append(f"{atlas_id} coordinates file is missing")
		elif frame_id not in coordinates:
			artifact_errors.append(f"{match.group('id')} is missing coordinate {frame_id}")
		if not atlas_path.is_file():
			artifact_errors.append(f"{atlas_id} PNG is missing")
		else:
			with Image.open(atlas_path) as atlas_image:
				sheets[atlas_id] = {
					"path": atlas_path.as_posix(),
					"width": atlas_image.width,
					"height": atlas_image.height,
					"mode": atlas_image.mode,
				}
				if atlas_image.mode != "RGBA":
					artifact_errors.append(f"{atlas_id} PNG mode must be RGBA, got {atlas_image.mode}")
				if atlas_image.width % 96 or atlas_image.height % 96:
					artifact_errors.append(f"{atlas_id} PNG dimensions must be multiples of 96")
		objects[match.group("id")] = {
			"sourceRegisterId": match.group("source"),
			"fallbackLabel": match.group("fallback"),
			"requiredForCreativeSprint": True,
			"frameId": frame_id,
			"provenanceId": match.group("provenance"),
		}
		accepted_object_ids.add(match.group("id"))
	for match in _TUPLE_PATTERN.finditer(object_section):
		if match.group("id") in accepted_object_ids:
			continue
		objects[match.group("id")] = {
			"sourceRegisterId": match.group("source"),
			"fallbackLabel": match.group("fallback"),
			"requiredForCreativeSprint": True,
			"frameId": None,
			"provenanceId": None,
		}
	sound_section = text.split("sounds: Object.fromEntries([", 1)[1].split("].map", 1)[0]
	for match in _TUPLE_PATTERN.finditer(sound_section):
		sounds[match.group("id")] = {
			"channel": match.group("source"),
			"sourceRegisterId": match.group("fallback"),
			"requiredForCreativeSprint": True,
			"src": None,
			"fallback": "silent",
		}
	return {
		"logicalCanvas": {"width": 96, "height": 96},
		"clips": clips,
		"objects": objects,
		"sounds": sounds,
		"sheets": sheets,
		"artifactErrors": artifact_errors,
	}


def registered_asset_ids(path: str | Path) -> set[str]:
	text = Path(path).read_text(encoding="utf-8")
	return set(re.findall(r"^\|\s*`([^`]+)`\s*\|", text, flags=re.MULTILINE))


def _fallback_cycle(clip_id: str, clips: dict[str, Any]) -> bool:
	visited: set[str] = set()
	current: str | None = clip_id
	while current is not None:
		if current in visited:
			return True
		visited.add(current)
		clip = clips.get(current)
		if not clip:
			return False
		current = clip.get("fallback")
	return False


def validate_assets(manifest: dict[str, Any], register_ids: set[str], *, allow_fallbacks: bool) -> list[str]:
	errors: list[str] = list(manifest.get("artifactErrors", []))
	canvas = manifest.get("logicalCanvas", {})
	width = canvas.get("width")
	height = canvas.get("height")
	if width != 96 or height != 96:
		errors.append("logical canvas must be 96x96")
	clips = manifest.get("clips", {})
	for clip_id, clip in clips.items():
		fallback = clip.get("fallback")
		if fallback is not None and fallback not in clips:
			errors.append(f"{clip_id} fallback {fallback} does not exist")
		if _fallback_cycle(clip_id, clips):
			errors.append(f"{clip_id} has a fallback cycle")
		if clip.get("requiredForCreativeSprint") and clip.get("creativeStatus") == "fallback" and not allow_fallbacks:
			errors.append(f"{clip_id} remains on fallback {fallback}")
		if clip.get("requiredForCreativeSprint") and clip.get("creativeStatus") in {"accepted", "coherent-reuse"}:
			review = clip.get("creativeReview")
			if not review:
				errors.append(f"{clip_id} has no recorded production visual review")
			elif review.get("status") != clip.get("creativeStatus"):
				errors.append(
					f"{clip_id} visual review status {review.get('status')} does not match {clip.get('creativeStatus')}"
				)
		if clip.get("creativeStatus") == "accepted" and clip.get("requiredForCreativeSprint"):
			planned_frames = clip.get("plannedUniqueFrames")
			if len(clip.get("frames", [])) != planned_frames:
				errors.append(f"{clip_id} has {len(clip.get('frames', []))} frames; expected {planned_frames}")
		for frame_index, frame in enumerate(clip.get("frames", [])):
			anchors = frame.get("anchors", {})
			for required in clip.get("requiredAnchors", []):
				if required not in anchors:
					errors.append(f"{clip_id} frame {frame_index} is missing {required} anchor")
			for anchor_name, point in anchors.items():
				x = point.get("x")
				y = point.get("y")
				if not isinstance(x, int) or not isinstance(y, int) or not 0 <= x < 96 or not 0 <= y < 96:
					errors.append(f"{clip_id} frame {frame_index} {anchor_name} anchor is outside 96x96")
			if "width" not in frame:
				continue
			if frame.get("width") != 96 or frame.get("height") != 96:
				errors.append(f"{clip_id} frame {frame_index} must occupy one 96x96 cell")
			sheet = manifest.get("sheets", {}).get(frame.get("sheetId"))
			if sheet and (
				frame.get("x", -1) < 0
				or frame.get("y", -1) < 0
				or frame.get("x", 0) + frame.get("width", 0) > sheet["width"]
				or frame.get("y", 0) + frame.get("height", 0) > sheet["height"]
			):
				errors.append(f"{clip_id} frame {frame_index} is outside {frame.get('sheetId')} bounds")
	for family in ("objects", "sounds"):
		for asset_id, asset in manifest.get(family, {}).items():
			source_id = asset.get("sourceRegisterId")
			if source_id and source_id not in register_ids:
				errors.append(f"{family}.{asset_id} references unregistered source {source_id}")
			if asset.get("requiredForCreativeSprint") and not allow_fallbacks:
				if family == "objects" and asset.get("frameId") is None:
					errors.append(f"objects.{asset_id} remains on fallback {asset.get('fallbackLabel')}")
				if family == "sounds" and asset.get("src") is None:
					errors.append(f"sounds.{asset_id} remains on fallback silent")
	return errors


def main() -> int:
	parser = argparse.ArgumentParser(description="Validate the prepared or resolved Parsec asset manifest.")
	parser.add_argument("--manifest", required=True, type=Path)
	parser.add_argument("--register", required=True, type=Path)
	mode = parser.add_mutually_exclusive_group()
	mode.add_argument("--allow-fallbacks", action="store_true")
	mode.add_argument("--require-resolved", action="store_true")
	args = parser.parse_args()
	manifest = load_prepared_manifest(args.manifest)
	register_ids = registered_asset_ids(args.register)
	errors = validate_assets(manifest, register_ids, allow_fallbacks=not args.require_resolved)
	if errors:
		for error in errors:
			print(error)
		return 1
	required_clips = [clip for clip in manifest["clips"].values() if clip.get("requiredForCreativeSprint")]
	planned_frames = sum(clip.get("plannedUniqueFrames", 0) for clip in required_clips)
	print(f"Validated {len(required_clips)} required clips and {planned_frames} planned unique frames")
	accepted_clips = [
		clip for clip in required_clips if clip.get("creativeStatus") == "accepted"
	]
	reused_clips = [
		clip for clip in required_clips if clip.get("creativeStatus") == "coherent-reuse"
	]
	fallback_clips = [
		clip for clip in required_clips if clip.get("creativeStatus") == "fallback"
	]
	accepted_frames = sum(len(clip.get("frames", [])) for clip in accepted_clips)
	reused_frames = sum(len(clip.get("frames", [])) for clip in reused_clips)
	if args.allow_fallbacks:
		print(f"Prepared fallback slots: {len(required_clips)} clips, {len(manifest['objects'])} objects, {len(manifest['sounds'])} sounds")
	elif not args.require_resolved:
		fallback_objects = [asset for asset in manifest["objects"].values() if asset.get("frameId") is None]
		fallback_sounds = [asset for asset in manifest["sounds"].values() if asset.get("src") is None]
		print(f"Accepted production sources: {len(accepted_clips)} clips, {accepted_frames} frames")
		print(f"Coherent production reuse: {len(reused_clips)} clips, {reused_frames} resolved frames")
		print(f"Resolved production slots: {len(accepted_clips) + len(reused_clips)} clips")
		print(f"Explicit fallback slots: {len(fallback_clips)} clips, {len(fallback_objects)} objects, {len(fallback_sounds)} sounds")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

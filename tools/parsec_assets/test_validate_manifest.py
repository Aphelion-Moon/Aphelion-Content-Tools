from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tools.parsec_assets.validate_manifest import load_prepared_manifest, validate_assets

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_MANIFEST = PROJECT_ROOT / "webapp/frontend/src/assets/parsec/manifest.v1.ts"
ASSET_REGISTER = PROJECT_ROOT / "references/parsec-asset-register.md"


def _manifest():
	return {
		"logicalCanvas": {"width": 96, "height": 96},
		"clips": {
			"base": {
				"frames": [{"anchors": {"feet": {"x": 48, "y": 82}}}],
				"requiredAnchors": ["feet"],
				"fallback": None,
				"requiredForCreativeSprint": False,
				"creativeStatus": "accepted",
			},
			"pat": {
				"frames": [{"anchors": {"scruff": {"x": 48, "y": 24}}}],
				"requiredAnchors": ["scruff"],
				"fallback": "base",
				"requiredForCreativeSprint": True,
				"creativeStatus": "fallback",
			},
		},
		"objects": {},
		"sounds": {},
	}


def test_validation_rejects_anchor_outside_96_pixel_canvas():
	manifest = _manifest()
	manifest["clips"]["pat"]["frames"][0]["anchors"]["scruff"] = {"x": 97, "y": 10}
	assert "pat frame 0 scruff anchor is outside 96x96" in validate_assets(manifest, set(), allow_fallbacks=True)


def test_validation_accepts_explicit_fallback_but_require_resolved_does_not():
	manifest = _manifest()
	assert validate_assets(manifest, set(), allow_fallbacks=True) == []
	assert "pat remains on fallback base" in validate_assets(manifest, set(), allow_fallbacks=False)


def test_validation_rejects_an_accepted_production_clip_without_visual_review():
	manifest = _manifest()
	manifest["clips"]["pat"]["creativeStatus"] = "accepted"
	assert "pat has no recorded production visual review" in validate_assets(manifest, set(), allow_fallbacks=False)


def test_loader_resolves_accepted_production_clips_and_keeps_later_fallbacks():
	manifest = load_prepared_manifest(PRODUCTION_MANIFEST)

	core = manifest["clips"]["core-idle-seated"]
	assert core["creativeStatus"] == "accepted"
	assert len(core["frames"]) == 4
	assert "scruff" in core["frames"][0]["anchors"]
	touch = manifest["clips"]["touch-pat-soft"]
	assert touch["creativeStatus"] == "accepted"
	assert touch["atlas"] == "parsec-touch"
	assert len(touch["frames"]) == 4
	assert "interaction" in touch["frames"][0]["anchors"]
	toy = manifest["clips"]["toy-ball-ready"]
	assert toy["creativeStatus"] == "accepted"
	assert len(toy["frames"]) == 4
	assert "toy" in toy["frames"][0]["anchors"]
	habitat = manifest["clips"]["habitat-bed-approach"]
	assert habitat["creativeStatus"] == "accepted"
	assert len(habitat["frames"]) == 4
	assert "interaction" in habitat["frames"][0]["anchors"]
	assert manifest["objects"]["dogbed"]["frameId"] == "ss13-objects/dogbed/d0/f0"
	assert manifest["objects"]["tug-rope"]["frameId"] == "ss13-objects/tug-rope/d0/f0"
	assert manifest["objects"]["tug-rope"]["provenanceId"] == "ss13-rift-objects"
	assert manifest["clips"]["intrusive-cursor-stalk"]["creativeStatus"] == "accepted"
	assert len(manifest["clips"]["intrusive-cursor-stalk"]["frames"]) == 5
	assert manifest["clips"]["effect-radio-ping"]["creativeStatus"] == "accepted"
	assert len(manifest["clips"]["effect-radio-ping"]["frames"]) == 3


def test_cli_default_validates_a_mixed_production_manifest():
	result = subprocess.run([
		sys.executable,
		"tools/parsec_assets/validate_manifest.py",
		"--manifest", str(PRODUCTION_MANIFEST),
		"--register", str(ASSET_REGISTER),
	], cwd=PROJECT_ROOT, check=False, capture_output=True, text=True)

	assert result.returncode == 0, result.stderr or result.stdout
	assert "Accepted production sources: 60 clips, 293 frames" in result.stdout
	assert "Coherent production reuse: 0 clips, 0 resolved frames" in result.stdout
	assert "Resolved production slots: 60 clips" in result.stdout
	assert "Explicit fallback slots: 0 clips, 0 objects, 0 sounds" in result.stdout

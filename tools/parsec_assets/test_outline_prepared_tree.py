from __future__ import annotations

import json

from PIL import Image

from tools.parsec_assets.outline_prepared_tree import outline_prepared_tree


def test_outlines_a_prepared_tree_and_records_project_relative_provenance(tmp_path, monkeypatch):
	monkeypatch.chdir(tmp_path)
	source = tmp_path / "prepared" / "parsec-core" / "idle"
	source.mkdir(parents=True)
	frame = source / "idle__d0__f0.png"
	image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
	for y in range(20, 70):
		for x in range(20, 70):
			image.putpixel((x, y), (255, 255, 255, 255))
	image.save(frame, format="PNG")

	manifest_path = outline_prepared_tree("prepared/parsec-core", "outlined/parsec-core")
	manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

	assert manifest["tool"] == "dark-silhouette-outline-tree-v1"
	assert manifest["source"] == "prepared/parsec-core"
	assert manifest["frames"][0]["source"] == "prepared/parsec-core/idle/idle__d0__f0.png"
	assert manifest["frames"][0]["path"] == "outlined/parsec-core/idle/idle__d0__f0.png"
	with Image.open(tmp_path / manifest["frames"][0]["path"]) as outlined:
		assert outlined.getpixel((20, 20)) == (0, 0, 0, 255)

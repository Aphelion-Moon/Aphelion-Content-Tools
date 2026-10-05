from __future__ import annotations

from PIL import Image

from tools.parsec_assets.split_generated_grid import split_generated_grid


def test_splits_rows_without_resampling(tmp_path):
	source = tmp_path / "grid.png"
	image = Image.new("RGBA", (12, 16), (0, 0, 0, 0))
	colors = ((255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255))
	for row, color in enumerate(colors):
		for y in range(row * 4, (row + 1) * 4):
			for x in range(image.width):
				image.putpixel((x, y), color)
	image.save(source, format="PNG")
	result = split_generated_grid(source, tmp_path / "rows", name="walk", rows=4)
	assert len(result.rows) == 4
	for index, row in enumerate(result.rows):
		with Image.open(row.path) as split:
			assert split.size == (12, 4)
			assert split.getpixel((5, 2)) == colors[index]


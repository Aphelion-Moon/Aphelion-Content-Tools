from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

from tools.parsec_assets.transform_prepared_frame import outline_prepared_frame


def outline_prepared_tree(source: str | Path, destination: str | Path) -> Path:
	source_root = Path(source)
	output_root = Path(destination)
	if output_root.exists() and any(output_root.iterdir()):
		raise FileExistsError(f"Refusing to overwrite non-empty destination: {output_root}")
	frames = []
	for source_path in sorted(source_root.rglob("*.png")):
		relative = source_path.relative_to(source_root)
		result = outline_prepared_frame(
			source_path,
			output_root / relative,
			reason="remove generated white silhouette fringe",
		)
		frames.append({
			"path": result.path.as_posix(),
			"sha256": result.sha256,
			"source": result.source.as_posix(),
			"sourceSha256": result.source_sha256,
		})
	if not frames:
		raise ValueError(f"No PNG frames found under {source_root}")
	manifest_path = output_root / "outline-preparation.json"
	manifest_path.write_text(json.dumps({
		"tool": "dark-silhouette-outline-tree-v1",
		"source": source_root.as_posix(),
		"sourceSha256": sha256("".join(frame["sourceSha256"] for frame in frames).encode()).hexdigest(),
		"frames": frames,
	}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
	return manifest_path


def main() -> int:
	parser = argparse.ArgumentParser(description="Apply the reviewed dark silhouette boundary to a prepared frame tree.")
	parser.add_argument("--input", required=True, type=Path)
	parser.add_argument("--output", required=True, type=Path)
	args = parser.parse_args()
	print(outline_prepared_tree(args.input, args.output))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

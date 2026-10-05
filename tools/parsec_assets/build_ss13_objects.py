from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from PIL import Image

from tools.parsec_assets.build_atlas import AtlasBuild, AtlasFrame, build_atlas
from tools.parsec_assets.extract_dmi import extract_dmi_state, read_dmi_metadata
from tools.parsec_assets.prepare_object_frame import prepare_object_frame


@dataclass(frozen=True)
class ObjectSource:
	id: str
	path: str
	state: str
	frame: int = 0
	direction: int = 0
	scale: int = 3
	baseline_y: int = 90
	base_state: str | None = None


DEFAULT_SOURCES = (
	ObjectSource("dogbed", "icons/obj/bed.dmi", "dogbed"),
	ObjectSource("cage-open", "icons/obj/pet_carrier.dmi", "pet_carrier_open"),
	ObjectSource("cage-closed", "icons/obj/pet_carrier.dmi", "pet_carrier_closed"),
	ObjectSource("cage-locked", "icons/obj/pet_carrier.dmi", "pet_carrier_locked", base_state="pet_carrier_closed"),
	ObjectSource("cage-occupied", "icons/obj/pet_carrier.dmi", "pet_carrier_occupied"),
	ObjectSource("tennis-ball", "modular_nova/master_files/icons/obj/balls.dmi", "tennis_classic"),
	ObjectSource("hairbrush", "modular_nova/modules/hairbrush/icons/hairbrush.dmi", "brush"),
	ObjectSource("toy-mouse", "icons/obj/toys/toy.dmi", "toy_mouse"),
	ObjectSource("carp-plush", "icons/obj/toys/plushes.dmi", "map_plushie_carp"),
	ObjectSource("toolbox", "icons/obj/storage/toolbox.dmi", "red"),
	ObjectSource("tug-rope", "icons/obj/stack_objects.dmi", "coil"),
)


def build_object_atlas(
	sources: Iterable[ObjectSource],
	repository_root: str | Path,
	destination: str | Path,
	*,
	source_revision: str = "fixture",
) -> AtlasBuild:
	root = Path(repository_root).resolve()
	output = Path(destination)
	final_png = output / 'ss13-objects.png'
	final_coordinates = output / 'ss13-objects.json'
	if final_png.exists() or final_coordinates.exists() or (output / 'ss13-objects.sources.json').exists():
		raise FileExistsError('Refusing to replace an existing SS13 object atlas')
	output.mkdir(parents=True, exist_ok=True)
	atlas_frames: list[AtlasFrame] = []
	source_records: list[dict[str, object]] = []
	for source in sources:
		dmi_path = root / Path(source.path)
		metadata = read_dmi_metadata(dmi_path)
		state = next((candidate for candidate in metadata.states if candidate.name == source.state), None)
		if state is None or source.frame >= state.frames or source.direction >= state.dirs:
			raise ValueError(f"Invalid state/frame/direction for {source.id}: {source.path}:{source.state}")
		extracted = extract_dmi_state(dmi_path, source.state, output / "source" / "ss13-objects" / source.id)
		selected = extracted[source.frame * state.dirs + source.direction]
		preparation_source = selected.path
		base_record: dict[str, object] = {}
		if source.base_state is not None:
			base_state = next((candidate for candidate in metadata.states if candidate.name == source.base_state), None)
			if base_state is None or source.frame >= base_state.frames or source.direction >= base_state.dirs:
				raise ValueError(f"Invalid base state/frame/direction for {source.id}: {source.path}:{source.base_state}")
			base_frames = extract_dmi_state(dmi_path, source.base_state, output / "source" / "ss13-objects" / f"{source.id}-base")
			base = base_frames[source.frame * base_state.dirs + source.direction]
			composed_path = output / "source" / "ss13-objects" / source.id / f"{source.id}-composed.png"
			with Image.open(base.path) as base_image, Image.open(selected.path) as overlay_image:
				composed = base_image.convert("RGBA")
				composed.alpha_composite(overlay_image.convert("RGBA"))
				composed.save(composed_path, format="PNG", optimize=False)
			preparation_source = composed_path
			base_record = {
				"base_extracted_sha256": base.sha256,
				"composed_sha256": sha256(composed_path.read_bytes()).hexdigest(),
			}
		prepared_path = output / "prepared" / "ss13-objects" / f"{source.id}__d{source.direction}__f{source.frame}.png"
		prepared = prepare_object_frame(
			preparation_source,
			prepared_path,
			scale=source.scale,
			baseline_y=source.baseline_y,
		)
		atlas_frames.append(AtlasFrame("ss13-objects", source.id, source.frame, source.direction, prepared_path))
		source_records.append({
			**asdict(source),
			"source_revision": source_revision,
			"source_sha256": sha256(dmi_path.read_bytes()).hexdigest(),
			"extracted_sha256": selected.sha256,
			"prepared_sha256": prepared.sha256,
			"source_size": prepared.source_size,
			"source_bounds": prepared.source_bounds,
			"occupied_size": prepared.occupied_size,
			"offset": prepared.offset,
			**base_record,
		})
	result = build_atlas(atlas_frames, output / "build")
	if final_png.exists() or final_coordinates.exists():
		raise FileExistsError("Refusing to replace an existing SS13 object atlas")
	result.png.replace(final_png)
	result.coordinates_path.replace(final_coordinates)
	(output / "ss13-objects.sources.json").write_text(
		json.dumps(source_records, indent=2, sort_keys=True) + "\n",
		encoding="utf-8",
	)
	return AtlasBuild(final_png, final_coordinates, result.coordinates)


def main() -> int:
	parser = argparse.ArgumentParser(description="Extract and pack the frozen Meridian-Rift object roster.")
	parser.add_argument("--repository-root", required=True, type=Path)
	parser.add_argument("--output", required=True, type=Path)
	parser.add_argument("--source-revision", required=True)
	args = parser.parse_args()
	result = build_object_atlas(
		DEFAULT_SOURCES,
		args.repository_root,
		args.output,
		source_revision=args.source_revision,
	)
	print(result.png)
	print(result.coordinates_path)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

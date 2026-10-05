from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class DmiState:
	name: str
	dirs: int
	frames: int
	delays: tuple[float, ...]
	cell_offset: int


@dataclass(frozen=True)
class DmiMetadata:
	width: int
	height: int
	states: tuple[DmiState, ...]


@dataclass(frozen=True)
class ExtractedFrame:
	path: Path
	state: str
	frame: int
	direction: int
	image_size: tuple[int, int]
	sha256: str


def _unquote(value: str) -> str:
	if value.startswith('"') and value.endswith('"'):
		return value[1:-1].replace(r'\"', '"').replace(r'\\', '\\')
	return value


def read_dmi_metadata(path: str | Path) -> DmiMetadata:
	source = Path(path)
	with Image.open(source) as image:
		description = image.info.get("Description")
	if not isinstance(description, str) or "# BEGIN DMI" not in description:
		raise ValueError(f"{source} has no DMI Description metadata")
	width = 32
	height = 32
	states: list[DmiState] = []
	current: dict[str, object] | None = None
	offset = 0

	def finish_state() -> None:
		nonlocal current, offset
		if current is None:
			return
		dirs = int(current.get("dirs", 1))
		frames = int(current.get("frames", 1))
		delays = tuple(float(value) for value in current.get("delays", ()))
		states.append(DmiState(str(current["name"]), dirs, frames, delays, offset))
		offset += dirs * frames
		current = None

	for raw_line in description.splitlines():
		line = raw_line.strip()
		if not line or line.startswith("#") or "=" not in line:
			continue
		key, raw_value = (part.strip() for part in line.split("=", 1))
		if key == "width":
			width = int(raw_value)
		elif key == "height":
			height = int(raw_value)
		elif key == "state":
			finish_state()
			current = {"name": _unquote(raw_value)}
		elif current is not None and key == "dirs":
			current["dirs"] = int(raw_value)
		elif current is not None and key == "frames":
			current["frames"] = int(raw_value)
		elif current is not None and key == "delay":
			current["delays"] = tuple(part.strip() for part in raw_value.split(",") if part.strip())
	finish_state()
	if width <= 0 or height <= 0 or not states:
		raise ValueError(f"{source} has invalid DMI dimensions or no states")
	return DmiMetadata(width, height, tuple(states))


def _safe_name(value: str) -> str:
	return re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_") or "unnamed"


def extract_dmi_state(path: str | Path, state_name: str, destination: str | Path) -> list[ExtractedFrame]:
	source = Path(path)
	metadata = read_dmi_metadata(source)
	state = next((candidate for candidate in metadata.states if candidate.name == state_name), None)
	if state is None:
		raise ValueError(f"DMI state {state_name!r} does not exist in {source}")
	output = Path(destination)
	output.mkdir(parents=True, exist_ok=True)
	results: list[ExtractedFrame] = []
	with Image.open(source) as image:
		rgba = image.convert("RGBA")
		columns = rgba.width // metadata.width
		rows = rgba.height // metadata.height
		if columns <= 0 or rows <= 0 or columns * rows < state.cell_offset + state.dirs * state.frames:
			raise ValueError(f"{source} DMI metadata addresses cells outside its PNG sheet")
		for frame_index in range(state.frames):
			for direction_index in range(state.dirs):
				cell_index = state.cell_offset + frame_index * state.dirs + direction_index
				column = cell_index % columns
				row = cell_index // columns
				frame = rgba.crop((
					column * metadata.width,
					row * metadata.height,
					(column + 1) * metadata.width,
					(row + 1) * metadata.height,
				))
				frame_path = output / f"{_safe_name(state.name)}-f{frame_index:03d}-d{direction_index:02d}.png"
				frame.save(frame_path, format="PNG", optimize=False)
				results.append(ExtractedFrame(
					path=frame_path,
					state=state.name,
					frame=frame_index,
					direction=direction_index,
					image_size=frame.size,
					sha256=sha256(frame_path.read_bytes()).hexdigest(),
				))
	return results


def main() -> int:
	parser = argparse.ArgumentParser(description="Extract an exact named DMI state without resampling.")
	parser.add_argument("path", type=Path)
	parser.add_argument("state")
	parser.add_argument("destination", type=Path)
	args = parser.parse_args()
	for frame in extract_dmi_state(args.path, args.state, args.destination):
		print(f"{frame.path}\t{frame.sha256}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from mutagen import File as MutagenFile


@dataclass(frozen=True)
class AudioInventoryEntry:
	path: str
	source_revision: str
	sha256: str
	duration_ms: int
	channels: int


_REGISTER_HEADER = (
	"Asset ID",
	"Status",
	"Source path",
	"Revision",
	"SHA-256",
	"Duration ms",
	"Channels",
	"License",
	"Author / attribution",
	"Notes",
)


def _table_cells(line: str) -> tuple[str, ...]:
	return tuple(cell.strip().strip("`") for cell in line.strip().strip("|").split("|"))


def _audio_register_rows(register_path: str | Path) -> list[dict[str, str]]:
	lines = Path(register_path).read_text(encoding="utf-8").splitlines()
	rows: list[dict[str, str]] = []
	in_table = False
	for line in lines:
		if _table_cells(line) == _REGISTER_HEADER:
			in_table = True
			continue
		if not in_table:
			continue
		if not line.lstrip().startswith("|"):
			break
		cells = _table_cells(line)
		if cells and all(cell.replace(":", "").replace("-", "") == "" for cell in cells):
			continue
		if len(cells) != len(_REGISTER_HEADER):
			raise ValueError(f"Malformed audio inventory row in {register_path}: {line}")
		rows.append(dict(zip(_REGISTER_HEADER, cells, strict=True)))
	if not in_table:
		raise ValueError(f"Audio source inventory table is missing from {register_path}")
	return rows


def check_audio_register(
	register_path: str | Path,
	*,
	repository_root: str | Path | None = None,
) -> list[str]:
	register = Path(register_path).resolve()
	root = Path(repository_root).resolve() if repository_root else register.parents[2] / "Meridian-Rift"
	errors: list[str] = []
	for row in _audio_register_rows(register):
		asset_id = row["Asset ID"]
		path = root / Path(row["Source path"])
		license_name = row["License"].strip()
		if not license_name or license_name.lower() in {"unknown", "ambiguous", "tbd"}:
			errors.append(f"{asset_id}: license is ambiguous")
			continue
		if not path.is_file():
			errors.append(f"{asset_id}: source does not exist: {row['Source path']}")
			continue
		try:
			entry = inventory_audio(
				[path],
				source_revision=row["Revision"],
				repository_root=root,
			)[0]
		except ValueError as error:
			errors.append(f"{asset_id}: {error}")
			continue
		if entry.sha256 != row["SHA-256"].lower():
			errors.append(f"{asset_id}: SHA-256 does not match")
		if str(entry.duration_ms) != row["Duration ms"]:
			errors.append(f"{asset_id}: duration does not match")
		if str(entry.channels) != row["Channels"]:
			errors.append(f"{asset_id}: channel count does not match")
	return errors


def inventory_audio(
	paths: Iterable[str | Path],
	*,
	source_revision: str,
	repository_root: str | Path,
) -> list[AudioInventoryEntry]:
	root = Path(repository_root).resolve()
	entries: list[AudioInventoryEntry] = []
	for raw_path in sorted((Path(path).resolve() for path in paths), key=lambda path: path.as_posix().lower()):
		if not raw_path.is_file():
			raise ValueError(f"Audio source does not exist: {raw_path}")
		audio = MutagenFile(raw_path)
		info = getattr(audio, "info", None)
		length = getattr(info, "length", None)
		channels = getattr(info, "channels", None)
		if not isinstance(length, (float, int)) or not isinstance(channels, int):
			raise ValueError(f"Unsupported audio or unreadable metadata: {raw_path}")
		try:
			relative = raw_path.relative_to(root).as_posix()
		except ValueError as error:
			raise ValueError(f"Audio source is outside repository root: {raw_path}") from error
		entries.append(AudioInventoryEntry(
			path=relative,
			source_revision=source_revision,
			sha256=sha256(raw_path.read_bytes()).hexdigest(),
			duration_ms=round(float(length) * 1000),
			channels=channels,
		))
	return entries


def main() -> int:
	parser = argparse.ArgumentParser(description="Inventory exact audio sources without transcoding.")
	parser.add_argument("paths", nargs="*", type=Path)
	parser.add_argument("--repository-root", type=Path)
	parser.add_argument("--source-revision")
	parser.add_argument("--check-register", type=Path)
	args = parser.parse_args()
	if args.check_register:
		if args.paths or args.source_revision:
			parser.error("--check-register cannot be combined with paths or --source-revision")
		errors = check_audio_register(args.check_register, repository_root=args.repository_root)
		if errors:
			for error in errors:
				print(error)
			return 1
		print(f"Validated audio inventory in {args.check_register}")
		return 0
	if not args.paths or not args.repository_root or not args.source_revision:
		parser.error("inventory mode requires paths, --repository-root, and --source-revision")
	entries = inventory_audio(
		args.paths,
		source_revision=args.source_revision,
		repository_root=args.repository_root,
	)
	print(json.dumps([asdict(entry) for entry in entries], indent=2))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from .validation import TYPE_PATH_PATTERN, validate_entry_id

RecordKind = Literal["override", "group", "review", "assignment"]

CONTENT_ROOT = Path("tools/lore_editor/content")
GROUP_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RECORD_DIRECTORIES: dict[RecordKind, str] = {
	"override": "overrides",
	"group": "groups",
	"review": "reviews",
	"assignment": "assignments",
}


def canonical_record_bytes(payload: Mapping[str, object]) -> bytes:
	text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
	return f"{text}\n".encode()


def canonical_record_hash(payload: Mapping[str, object]) -> str:
	return hashlib.sha256(canonical_record_bytes(payload)).hexdigest()


def read_record(path: Path) -> dict[str, object]:
	try:
		payload = json.loads(path.read_text(encoding="utf-8"))
	except (OSError, json.JSONDecodeError) as exc:
		raise ValueError(f"Could not read canonical record {path}: {exc}") from exc
	if not isinstance(payload, dict):
		raise ValueError(f"Canonical record {path} must contain a JSON object.")
	return payload


def record_path(repo_root: Path, kind: RecordKind, record_id: str) -> Path:
	if kind not in RECORD_DIRECTORIES:
		raise ValueError(f"Unknown record kind '{kind}'.")
	root = repo_root.resolve() / CONTENT_ROOT / RECORD_DIRECTORIES[kind]
	if kind == "override":
		return root / f"{validate_entry_id(record_id)}.json"
	if kind == "group":
		if not GROUP_ID_PATTERN.fullmatch(record_id):
			raise ValueError(f"Invalid group id '{record_id}'.")
		return root / f"{record_id}.json"
	if not TYPE_PATH_PATTERN.fullmatch(record_id):
		raise ValueError(f"Invalid type path '{record_id}'.")
	return root.joinpath(*record_id.removeprefix("/").split("/")).with_suffix(".json")


def atomic_write_record(path: Path, payload: Mapping[str, object]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	file_descriptor, temporary_name = tempfile.mkstemp(
		prefix=f".{path.name}.",
		suffix=".tmp",
		dir=path.parent,
	)
	temporary_path = Path(temporary_name)
	try:
		with os.fdopen(file_descriptor, "wb") as temporary_file:
			temporary_file.write(canonical_record_bytes(payload))
			temporary_file.flush()
			os.fsync(temporary_file.fileno())
		os.replace(temporary_path, path)
	except Exception:
		temporary_path.unlink(missing_ok=True)
		raise

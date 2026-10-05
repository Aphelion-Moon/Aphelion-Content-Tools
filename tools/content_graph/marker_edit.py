from __future__ import annotations

from pathlib import Path

from webapp.game_changes import GameChangeSetService, PreparedGameChange
from webapp.path_safety import resolve_repo_path

from .markers import render_marker_line


def _split_line_ending(line: str) -> tuple[str, str]:
	content = line.rstrip("\r\n")
	return content, line[len(content):]


def prepare_marker_label_edit(
	service: GameChangeSetService,
	core_file: str,
	line_number: int,
	expected_line: str,
	new_label: str,
) -> PreparedGameChange:
	if line_number < 1:
		raise ValueError("line_number must be a positive integer.")
	if not new_label.strip():
		raise ValueError("New label must not be empty.")
	if any(ord(character) < 32 for character in new_label) or '*/' in new_label or '/*' in new_label:
		raise ValueError('Marker labels must be single-line text without comment delimiters.')
	resolved_root = service.root
	if not core_file.startswith('code/') or not core_file.endswith('.dm'):
		raise ValueError('Marker edits are restricted to core DM files under code/.')

	file_path = resolve_repo_path(resolved_root, Path(core_file))
	if not file_path.is_file():
		raise ValueError(f"Core file does not exist: {core_file}")

	before = file_path.read_bytes()
	text = before.decode("utf-8")
	lines = text.splitlines(keepends=True)
	if line_number > len(lines):
		raise ValueError(f"Line {line_number} is out of range for {core_file}.")

	index = line_number - 1
	current_content, line_ending = _split_line_ending(lines[index])
	if current_content != expected_line:
		raise ValueError(
			f"{core_file}:{line_number} changed since this marker was loaded; rescan and try again."
		)

	lines[index] = render_marker_line(current_content, new_label) + line_ending
	return service.prepare({core_file: (before, "".join(lines).encode("utf-8"))}, allowed_paths=frozenset({core_file}))


def apply_marker_label_edit(game_repo_root: Path, core_file: str, line_number: int, expected_line: str, new_label: str) -> None:
	"""Trusted local compatibility entry point, using the same staged validation."""
	service = GameChangeSetService(game_repo_root)
	stage = prepare_marker_label_edit(service, core_file, line_number, expected_line, new_label)
	service.apply(stage.stage_id)

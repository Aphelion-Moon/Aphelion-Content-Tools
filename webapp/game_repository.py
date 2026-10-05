from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from .git_adapter import repository_remote_url

GAME_REPOSITORY_MARKER_PATH = Path("tgstation.dme")
EXPECTED_GAME_REPOSITORY_REMOTE_HINT = "meridian-rift"


def _remote_repository_name(remote_url: str) -> str:
	value = remote_url.strip().rstrip("/")
	# Git's scp-like syntax is `user@host:owner/repository.git`.
	path = urlsplit(value).path if "://" in value else value.rsplit(":", 1)[-1]
	name = path.rsplit("/", 1)[-1].split("?", 1)[0].split("#", 1)[0]
	if name.casefold().endswith(".git"):
		name = name[:-4]
	return name.casefold()


def _public_remote_identity(remote_url: str) -> str:
	value = remote_url.strip()
	if "://" in value:
		parsed = urlsplit(value)
		if parsed.hostname:
			path = parsed.path.lstrip("/").rstrip("/")
			return f"{parsed.hostname.casefold()}/{path}" if path else parsed.hostname.casefold()
	if "@" in value and ":" in value:
		host_path = value.rsplit("@", 1)[-1]
		host, _, path = host_path.partition(":")
		if host and path:
			return f"{host.casefold()}/{path.rstrip('/')}"
	return "<configured remote>"


def validate_game_repository(game_repo_root: Path) -> None:
	"""Raise if the given path does not look like a Meridian-Rift checkout.

	Checks a content marker (tgstation.dme) that any BYOND/tgstation-family checkout must have, and,
	when the path is a Git repository with an 'origin' remote configured, that the remote URL looks
	like Meridian-Rift. A path with no Git remote configured is accepted based on the content marker
	alone, since there is nothing further to check.
	"""
	resolved_root = game_repo_root.resolve()
	if not resolved_root.is_dir():
		raise ValueError(f"Game repository does not exist: {game_repo_root}")
	if not (resolved_root / GAME_REPOSITORY_MARKER_PATH).is_file():
		raise ValueError(
			f"'{resolved_root}' does not look like a Meridian-Rift checkout "
			f"({GAME_REPOSITORY_MARKER_PATH.as_posix()} is missing)."
		)
	remote_url = repository_remote_url(resolved_root)
	if remote_url is not None and _remote_repository_name(remote_url) != EXPECTED_GAME_REPOSITORY_REMOTE_HINT:
		raise ValueError(
			f"'{resolved_root}' has a Git remote that does not look like Meridian-Rift: "
			f"{_public_remote_identity(remote_url)}"
		)

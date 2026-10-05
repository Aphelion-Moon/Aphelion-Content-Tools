from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

import uvicorn

from webapp.api import create_app


def _resolve_port(requested: int) -> int:
	"""Pick a concrete port up front so the URL can be printed before the server starts.

	Port 0 means "any free port", but uvicorn only reveals the chosen one after binding -- and the
	launcher needs the URL on stdout to open a browser. Binding a throwaway socket first resolves it.
	"""
	if requested:
		return requested
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
		probe.bind(("127.0.0.1", 0))
		return int(probe.getsockname()[1])


def main(argv: list[str] | None = None) -> int:
	arguments = list(sys.argv[1:] if argv is None else argv)
	if arguments and arguments[0] == "--store-worker":
		from webapp.store_worker import main as store_worker_main

		return store_worker_main(arguments[1:])
	parser = argparse.ArgumentParser(description="Run the local Aphelion Content Tools API.")
	parser.add_argument("--repo-root", type=Path, required=True)
	parser.add_argument("--game-repo", type=Path)
	parser.add_argument("--port", type=int, default=0)
	parser.add_argument("--reload", action="store_true", help="Restart on source changes (development only).")
	args = parser.parse_args(arguments)

	port = _resolve_port(args.port)
	try:
		app = create_app(args.repo_root, args.game_repo, trusted_origin=f'http://127.0.0.1:{port}')
	except (OSError, ValueError) as exc:
		print(f"error: {exc}", file=sys.stderr)
		return 1

	# Kept byte-identical to the old server's line: the Windows launcher greps for this prefix.
	print(f"LORE_EDITOR_URL=http://127.0.0.1:{port}", flush=True)

	uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning", ws_max_size=4096)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

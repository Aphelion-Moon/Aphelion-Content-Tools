from __future__ import annotations

import contextlib
import threading
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from webapp.tool_registry import load_tool_registry
from webapp.tooling import shut_down_worker, start_tool

from .deps import AppContext
from .errors import ApiError, handle_api_error, handle_os_error, handle_value_error
from .live import Broadcaster
from .live import router as live_router
from .routes import export, git, graph, lore, references, store, tools

# How long after startup to queue "Optimize database" once, so LanceDB's fragment/version housekeeping
# happens without the user remembering to click it. Long enough never to fire during a short-lived test
# server; short enough to matter within a working session.
STARTUP_OPTIMIZE_DELAY_SECONDS = 60.0

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


def _run_startup_optimize(repo_root: Path) -> None:
	with contextlib.suppress(OSError, ValueError, RuntimeError):
		# Best-effort: a manual "Optimize database" click remains available regardless.
		start_tool(repo_root, load_tool_registry(), "optimize-store")


def create_app(repo_root: Path, game_repo_root: Path | None = None) -> FastAPI:
	"""Build the API application for one pair of repository roots.

	Roots are bound per-app rather than read from module globals so tests can run several apps against
	separate temporary directories concurrently.
	"""
	resolved_root = repo_root.resolve()
	context = AppContext(
		repo_root=resolved_root,
		game_repo_root=(game_repo_root or repo_root).resolve(),
	)

	@contextlib.asynccontextmanager
	async def lifespan(app: FastAPI) -> AsyncIterator[None]:
		optimize_timer = threading.Timer(STARTUP_OPTIMIZE_DELAY_SECONDS, _run_startup_optimize, args=(resolved_root,))
		optimize_timer.daemon = True
		optimize_timer.start()
		try:
			yield
		finally:
			optimize_timer.cancel()
			await app.state.broadcaster.shutdown()
			# The store worker is spawned lazily on the first tool run and outlives individual requests.
			# Windows does not reap child processes when the parent exits, so it must be told to stop
			# here or it is left running after shutdown -- the orphaned-process failure this project has
			# hit before.
			shut_down_worker(resolved_root)

	app = FastAPI(
		title="Aphelion Content Tools",
		version="0.1.0",
		summary="Local API for authoring and maintaining Meridian-Rift's modular content.",
		lifespan=lifespan,
	)
	app.state.context = context
	app.state.broadcaster = Broadcaster(resolved_root)

	app.add_exception_handler(ApiError, handle_api_error)
	app.add_exception_handler(ValueError, handle_value_error)
	app.add_exception_handler(OSError, handle_os_error)

	app.include_router(store.router)
	app.include_router(tools.router)
	app.include_router(git.router)
	app.include_router(graph.router)
	app.include_router(lore.router)
	app.include_router(references.router)
	app.include_router(export.router)
	app.include_router(live_router)

	@app.get("/api/health", tags=["store"])
	def health() -> dict[str, object]:
		return {"ok": True, "service": "aphelion-content-tools"}

	_mount_frontend(app)
	return app


def _mount_frontend(app: FastAPI) -> None:
	"""Serve the built frontend, if it has been built.

	One mount replaces the ~25 hand-written `if parsed.path == "/some-file.js"` branches the old server
	needed, one per asset. Missing dist/ is not an error: the API is useful on its own, and in
	development Vite serves the UI and proxies here.
	"""
	if not FRONTEND_DIST.is_dir():
		return

	assets = FRONTEND_DIST / "assets"
	if assets.is_dir():
		app.mount("/assets", StaticFiles(directory=assets), name="assets")

	@app.get("/{full_path:path}", include_in_schema=False)
	def spa_fallback(full_path: str) -> FileResponse:
		# Client-side routing means /lore-editor is not a file on disk; every non-API path resolves to
		# index.html and the router takes it from there. A real static file still wins when it exists.
		candidate = (FRONTEND_DIST / full_path).resolve()
		if full_path and candidate.is_file() and candidate.is_relative_to(FRONTEND_DIST):
			return FileResponse(candidate)
		return FileResponse(FRONTEND_DIST / "index.html")

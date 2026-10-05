from __future__ import annotations

import asyncio
import contextlib
import os
import secrets
import threading
from collections.abc import AsyncIterator
from http import HTTPStatus
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tools.definition_editor.service import EditorService
from tools.lore_editor.reconcile import reconcile_projection
from tools.lore_editor.write_coordinator import RecordConflict
from webapp.tool_registry import load_tool_registry
from webapp.tooling import shut_down_worker, start_tool
from webapp.workspace_lock import WorkspaceLease

from .deps import AppContext
from .errors import ApiError, handle_api_error, handle_os_error, handle_record_conflict, handle_value_error
from .live import Broadcaster
from .live import router as live_router
from .local_security import LocalSessionMiddleware
from .routes import collaboration, definitions, export, git, graph, lore, references, store, tools

# How long after startup to queue "Optimize database" once, so LanceDB's fragment/version housekeeping
# happens without the user remembering to click it. Long enough never to fire during a short-lived test
# server; short enough to matter within a working session.
STARTUP_OPTIMIZE_DELAY_SECONDS = 60.0

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


def _run_startup_optimize(repo_root: Path, shutdown_requested: threading.Event) -> None:
	if shutdown_requested.is_set():
		return
	with contextlib.suppress(OSError, ValueError, RuntimeError):
		# Best-effort: a manual "Optimize database" click remains available regardless.
		start_tool(repo_root, load_tool_registry(), "optimize-store")


def create_app(
	repo_root: Path,
	game_repo_root: Path | None = None,
	*,
	collaboration_base_url: str | None = None,
	collaboration_service_token: str | None = None,
	trusted_origin: str | None = None,
) -> FastAPI:
	"""Build the API application for one pair of repository roots.

	Roots are bound per-app rather than read from module globals so tests can run several apps against
	separate temporary directories concurrently.
	"""
	resolved_root = repo_root.resolve()
	if collaboration_base_url is None:
		collaboration_base_url = os.environ.get("APHELION_COLLABORATION_URL")
	if collaboration_service_token is None and collaboration_base_url:
		collaboration_service_token = os.environ.get("APHELION_COLLABORATION_SERVICE_TOKEN")
	context = AppContext(
		repo_root=resolved_root,
		game_repo_root=(game_repo_root or repo_root).resolve(),
	)
	workspace_lease = WorkspaceLease(resolved_root)
	definition_editors = EditorService(resolved_root, context.game_repo_root, context.game_changes)

	@contextlib.asynccontextmanager
	async def lifespan(app: FastAPI) -> AsyncIterator[None]:
		workspace_lease.acquire()
		optimize_timer: threading.Timer | None = None
		optimize_timer_started = False
		shutdown_requested = threading.Event()
		try:
			reconcile_projection(resolved_root)
			optimize_timer = threading.Timer(
				STARTUP_OPTIMIZE_DELAY_SECONDS,
				_run_startup_optimize,
				args=(resolved_root, shutdown_requested),
			)
			optimize_timer.daemon = True
			optimize_timer.start()
			optimize_timer_started = True
			yield
		finally:
			try:
				shutdown_requested.set()
				if optimize_timer is not None and optimize_timer_started:
					optimize_timer.cancel()
					await asyncio.to_thread(optimize_timer.join)
				await app.state.broadcaster.shutdown()
				await asyncio.to_thread(definition_editors.shutdown)
				# The store worker is spawned lazily on the first tool run and outlives individual requests.
				# Windows does not reap child processes when the parent exits, so it must be told to stop
				# here or it is left running after shutdown -- the orphaned-process failure this project has
				# hit before.
				shut_down_worker(resolved_root)
			finally:
				workspace_lease.release()

	app = FastAPI(
		title="Aphelion Content Tools",
		version="0.1.0",
		summary="Local API for authoring and maintaining Meridian-Rift's modular content.",
		lifespan=lifespan,
	)
	app.state.context = context
	app.state.definition_editors = definition_editors
	app.state.broadcaster = Broadcaster(resolved_root, context.game_repo_root, editor_runs=lambda: [run.model_dump() for run in definition_editors.runs()])
	app.state.workspace_lease = workspace_lease
	app.state.collaboration_client = (
		collaboration.CollaborationClient(collaboration_base_url, collaboration_service_token)
		if collaboration_base_url
		else None
	)
	app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
	app.add_middleware(LocalSessionMiddleware, token=secrets.token_urlsafe(32), trusted_origin=trusted_origin)

	app.add_exception_handler(ApiError, handle_api_error)
	app.add_exception_handler(RecordConflict, handle_record_conflict)
	app.add_exception_handler(ValueError, handle_value_error)
	app.add_exception_handler(OSError, handle_os_error)

	app.include_router(store.router)
	app.include_router(tools.router)
	app.include_router(git.router)
	app.include_router(graph.router)
	app.include_router(lore.router)
	app.include_router(definitions.router)
	app.include_router(references.router)
	app.include_router(export.router)
	app.include_router(collaboration.router)
	app.include_router(live_router)

	@app.get("/api/health", tags=["store"])
	def health() -> dict[str, object]:
		return {"ok": True, "service": "aphelion-content-tools"}

	@app.get('/api/session', include_in_schema=False)
	def local_session() -> dict[str, bool]:
		return {'ready': True}

	@app.get("/api/workspace/lease", tags=["store"])
	def workspace_lease_status() -> dict[str, object]:
		return {
			"workspace": str(resolved_root),
			"acquired": workspace_lease.acquired,
			"owner": workspace_lease.owner if workspace_lease.acquired else None,
		}

	_mount_frontend(app, resolved_root)
	return app


def _mount_frontend(app: FastAPI, repo_root: Path) -> None:
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

	@app.get("/references/parsec-asset-register.md", include_in_schema=False)
	def parsec_asset_register() -> FileResponse:
		register = repo_root / "references/parsec-asset-register.md"
		if not register.is_file():
			raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
		return FileResponse(register, media_type="text/markdown; charset=utf-8")

	@app.get("/{full_path:path}", include_in_schema=False)
	def spa_fallback(full_path: str) -> FileResponse:
		if full_path == 'api' or full_path.startswith('api/'):
			raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
		# Client-side routing means /lore-editor is not a file on disk; every non-API path resolves to
		# index.html and the router takes it from there. A real static file still wins when it exists.
		candidate = (FRONTEND_DIST / full_path).resolve()
		if full_path and candidate.is_file() and candidate.is_relative_to(FRONTEND_DIST):
			return FileResponse(candidate)
		return FileResponse(FRONTEND_DIST / "index.html")

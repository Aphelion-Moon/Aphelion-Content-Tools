from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from webapp.store.health import store_health
from webapp.tool_registry import load_tool_registry
from webapp.tooling import list_active_runs, list_tools

# Live updates.
#
# Pre-rewrite, every widget on every open page ran its own 5-second setInterval against
# /api/store/health and /api/tools/active. This replaces all of that with one connection per client.
#
# On the backend side, the source of truth for job status lives in a separate process (store_worker.py),
# reached over an AF_PIPE connection that speaks strict request/response -- it cannot push. Rather than
# redesign that IPC channel (and risk the warm-worker behaviour that makes jobs fast), the server polls
# it centrally and fans the result out to every connected client. The client-side win -- no per-widget
# timers, no N-times-duplicated requests, one shared state -- is fully realised either way; adding a real
# push channel later changes only this file.

router = APIRouter()

POLL_INTERVAL_SECONDS = 2.0


class Broadcaster:
	"""Fans one poll of backend state out to every connected client."""

	def __init__(self, repo_root: Path) -> None:
		self._repo_root = repo_root
		self._clients: set[WebSocket] = set()
		self._lock = asyncio.Lock()
		self._task: asyncio.Task[None] | None = None
		self._last: dict[str, object] = {}

	async def register(self, socket: WebSocket) -> None:
		async with self._lock:
			self._clients.add(socket)
			if self._task is None:
				self._task = asyncio.create_task(self._run())
		# Send the latest known state immediately so a newly-opened page renders without waiting a
		# full poll interval.
		for message_type, payload in self._last.items():
			with contextlib.suppress(Exception):
				await socket.send_text(json.dumps({"type": message_type, "data": payload}))

	async def unregister(self, socket: WebSocket) -> None:
		async with self._lock:
			self._clients.discard(socket)
			if not self._clients and self._task is not None:
				self._task.cancel()
				self._task = None

	async def shutdown(self) -> None:
		async with self._lock:
			if self._task is not None:
				self._task.cancel()
				self._task = None
			clients = list(self._clients)
			self._clients.clear()
		for socket in clients:
			with contextlib.suppress(Exception):
				await socket.close()

	def _collect(self) -> dict[str, object]:
		labels = {tool["id"]: tool["label"] for tool in list_tools(load_tool_registry())}
		runs = [
			{**run, "tool_label": labels.get(run["tool_id"], run["tool_id"])}
			for run in list_active_runs(self._repo_root)
		]
		return {"health": store_health(self._repo_root), "active_runs": runs}

	async def _broadcast(self, message_type: str, payload: object) -> None:
		frame = json.dumps({"type": message_type, "data": payload})
		async with self._lock:
			clients = list(self._clients)
		for socket in clients:
			try:
				await socket.send_text(frame)
			except Exception:
				# A send failure means the peer is gone; the socket's own handler will unregister it.
				continue

	async def _run(self) -> None:
		while True:
			try:
				# store_health walks the store directory and list_active_runs makes a blocking pipe call,
				# so both go to a thread rather than stalling the event loop for every connected client.
				snapshot = await asyncio.to_thread(self._collect)
				for message_type, payload in snapshot.items():
					if self._last.get(message_type) != payload:
						self._last[message_type] = payload
						await self._broadcast(message_type, payload)
			except asyncio.CancelledError:
				raise
			except Exception:
				# A failed poll (store mid-write, worker restarting) must not kill the broadcaster --
				# clients would silently stop updating. Skip this tick and try again.
				pass
			await asyncio.sleep(POLL_INTERVAL_SECONDS)


@router.websocket("/ws")
async def live_updates(websocket: WebSocket) -> None:
	broadcaster: Broadcaster = websocket.app.state.broadcaster
	await websocket.accept()
	await broadcaster.register(websocket)
	try:
		while True:
			# No client->server protocol yet; this receive exists to notice disconnects.
			await websocket.receive_text()
	except WebSocketDisconnect:
		pass
	finally:
		await broadcaster.unregister(websocket)

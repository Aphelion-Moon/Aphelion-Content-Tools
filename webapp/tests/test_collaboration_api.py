from __future__ import annotations

import io
import json
import os
import threading
import unittest
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError

from pydantic import ValidationError

from webapp.api import create_app
from webapp.api.errors import CollaborationUnavailable
from webapp.api.models import CollaborationCheckpointRequest, CollaborationCheckpointResponse
from webapp.api.routes.collaboration import CollaborationClient
from webapp.tests.http_client import TestClient


class _CollaborationHandler(BaseHTTPRequestHandler):
	protocol_version = "HTTP/1.0"
	mode = "normal"
	requests: list[tuple[str, str | None]] = []

	def do_GET(self) -> None:
		self.requests.append((self.path, self.headers.get("Authorization")))
		if self.mode == "secret-error":
			self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"message": "service_token=super-secret-token"})
			return
		if self.path == "/v1/version":
			versions = [2] if self.mode == "incompatible" else [1]
			self._json(HTTPStatus.OK, {
				"build": "fixture", "revision": "abc123", "protocol_versions": versions, "schema_versions": [1],
			})
			return
		if self.path == "/v1/sessions/session-1":
			self._json(HTTPStatus.OK, {
				"session_id": "session-1", "document_id": "11111111-1111-1111-1111-111111111111",
				"protocol_version": 1, "schema_version": 1, "revision": 9, "map_hash": "a" * 64,
			})
			return
		self._json(HTTPStatus.NOT_FOUND, {"code": "not_found", "message": "missing"})

	def do_POST(self) -> None:
		self.requests.append((self.path, self.headers.get("Authorization")))
		length = int(self.headers.get("Content-Length", "0"))
		body = json.loads(self.rfile.read(length)) if length else {}
		if self.mode == "secret-error":
			self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {
				"code": "internal", "message": "service_token=super-secret-token",
			})
			return
		if self.path == "/v1/sessions/session-1/join-tokens":
			assert body == {"role": "viewer", "display_name": "Lore Writer"}
			self._json(HTTPStatus.CREATED, {
				"token": "short-lived-join-token", "actor_id": "22222222-2222-2222-2222-222222222222",
				"role": "viewer", "expires_at": "2026-08-25T12:00:00Z",
			})
			return
		if self.path == "/v1/sessions/session-1/exports":
			assert body == {"revision": 9, "map_hash": "a" * 64}
			self._json(HTTPStatus.ACCEPTED, {
				"checkpoint_id": "checkpoint-1", "revision": 9, "map_hash": "a" * 64, "status": "accepted",
			})
			return
		self._json(HTTPStatus.NOT_FOUND, {"code": "not_found", "message": "missing"})

	def log_message(self, _format: str, *args: object) -> None:
		return

	def _json(self, status: HTTPStatus, body: dict[str, object]) -> None:
		encoded = json.dumps(body).encode("utf-8")
		self.send_response(status)
		self.send_header("Content-Type", "application/json")
		self.send_header("Content-Length", str(len(encoded)))
		self.end_headers()
		self.wfile.write(encoded)


class CollaborationApiTests(unittest.TestCase):
	def test_upstream_http_error_response_is_closed(self) -> None:
		body = io.BytesIO(b"upstream error")
		error = HTTPError(self.base_url, 500, "failed", {}, body)
		with patch("webapp.api.routes.collaboration.urlopen", side_effect=error), self.assertRaises(CollaborationUnavailable):
			CollaborationClient(self.base_url).version()
		self.assertTrue(body.closed)

	def test_service_credential_cannot_authorize_browser_session_actions(self) -> None:
		client = CollaborationClient(self.base_url, "service-secret")
		from webapp.api.models import CollaborationJoinRequest
		with patch.object(client, "_request") as upstream:
			for action in (
				lambda: client.session("session-1"),
				lambda: client.create_join_token("session-1", CollaborationJoinRequest(role="viewer", display_name="Writer")),
				lambda: client.create_checkpoint("session-1", CollaborationCheckpointRequest(revision=9, map_hash="a" * 64, idempotency_key="request-1")),
			):
				with self.subTest(action=action), self.assertRaisesRegex(CollaborationUnavailable, "user authorization"):
					action()
		upstream.assert_not_called()

	def test_checkpoint_schema_matches_server_states_and_utf8_key_limit(self) -> None:
		payload = {"revision": 9, "map_hash": "a" * 64, "idempotency_key": "checkpoint-1"}
		request = CollaborationCheckpointRequest.model_validate(payload)
		self.assertEqual(request.idempotency_key, "checkpoint-1")
		for key in ("", " \t", "é" * 65):
			with self.subTest(key=key), self.assertRaises(ValidationError):
				CollaborationCheckpointRequest.model_validate({**payload, "idempotency_key": key})
		for status in ("pending", "accepted", "rejected"):
			response = CollaborationCheckpointResponse.model_validate({"checkpoint_id": "checkpoint-1", "revision": 9, "map_hash": "a" * 64, "status": status})
			self.assertEqual(response.status, status)
	def setUp(self) -> None:
		self._temp = TemporaryDirectory()
		self.addCleanup(self._temp.cleanup)
		self.server = ThreadingHTTPServer(("127.0.0.1", 0), _CollaborationHandler)
		self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
		self.thread.start()
		self.addCleanup(self._stop_server)
		self.base_url = f"http://127.0.0.1:{self.server.server_port}"
		_CollaborationHandler.mode = "normal"
		_CollaborationHandler.requests = []

	def _stop_server(self) -> None:
		self.server.shutdown()
		self.thread.join(timeout=2)
		self.server.server_close()

	def app(self):
		return create_app(Path(self._temp.name), Path(self._temp.name), collaboration_base_url=self.base_url)

	def test_version_and_session_metadata(self) -> None:
		with TestClient(self.app()) as client:
			version = client.get("/api/collaboration/version")
			session = client.get("/api/collaboration/sessions/session-1")
		self.assertEqual(version.status_code, HTTPStatus.OK)
		self.assertTrue(version.json()["compatible"])
		self.assertEqual(session.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
		self.assertIn("user authorization", session.json()["error"])
		self.assertEqual(_CollaborationHandler.requests, [("/v1/version", None)])

	def test_shipped_app_reads_immutable_service_configuration_from_environment(self) -> None:
		with patch.dict(os.environ, {"APHELION_COLLABORATION_URL": self.base_url}, clear=False):
			app = create_app(Path(self._temp.name), Path(self._temp.name))
		with TestClient(app) as client:
			response = client.get("/api/collaboration/version")
		self.assertEqual(response.status_code, HTTPStatus.OK)
		self.assertTrue(response.json()["compatible"])

	def test_join_and_checkpoint_are_unavailable_without_user_authority(self) -> None:
		with TestClient(self.app()) as client:
			joined = client.post("/api/collaboration/sessions/session-1/join-tokens", json={
				"role": "viewer", "display_name": "Lore Writer",
			})
			checkpoint = client.post("/api/collaboration/sessions/session-1/checkpoints", json={
				"revision": 9, "map_hash": "a" * 64, "idempotency_key": "request-1",
			})
		self.assertEqual(joined.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
		self.assertEqual(checkpoint.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
		self.assertEqual(_CollaborationHandler.requests, [])

	def test_anonymous_version_probe_does_not_forward_service_credential(self) -> None:
		CollaborationClient(self.base_url, "service-secret").version()
		self.assertEqual(_CollaborationHandler.requests, [("/v1/version", None)])

	def test_local_capabilities_do_not_probe_an_unconfigured_service(self) -> None:
		app = create_app(Path(self._temp.name), Path(self._temp.name), collaboration_base_url="")
		with TestClient(app) as client:
			response = client.get("/api/collaboration/capabilities")
		self.assertEqual(response.status_code, HTTPStatus.OK)
		self.assertFalse(response.json()["configured"])
		self.assertFalse(response.json()["join"])
		self.assertFalse(response.json()["checkpoint"])
		self.assertEqual(_CollaborationHandler.requests, [])

	def test_unavailable_and_incompatible_services_are_distinct(self) -> None:
		unconfigured = create_app(Path(self._temp.name), Path(self._temp.name))
		with TestClient(unconfigured) as client:
			unavailable = client.get("/api/collaboration/version")
		self.assertEqual(unavailable.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
		self.assertEqual(unavailable.json()["code"], "collaboration_unavailable")

		_CollaborationHandler.mode = "incompatible"
		with TestClient(self.app()) as client:
			incompatible = client.get("/api/collaboration/version")
		self.assertEqual(incompatible.status_code, HTTPStatus.OK)
		self.assertFalse(incompatible.json()["compatible"])

	def test_invalid_identifier_is_rejected_before_forwarding(self) -> None:
		with TestClient(self.app()) as client:
			response = client.get("/api/collaboration/sessions/bad*identifier")
		self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

	def test_upstream_credentials_are_redacted(self) -> None:
		_CollaborationHandler.mode = "secret-error"
		with TestClient(self.app()) as client:
			response = client.get("/api/collaboration/version")
		self.assertEqual(response.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
		self.assertNotIn("super-secret-token", response.text)
		self.assertEqual(_CollaborationHandler.requests, [("/v1/version", None)])


if __name__ == "__main__":
	unittest.main()

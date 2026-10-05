from __future__ import annotations

import ipaddress
import json
from http import HTTPStatus
from typing import Annotated, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, Path, Response
from fastapi import Request as FastAPIRequest
from pydantic import BaseModel, ValidationError

from ..errors import CollaborationUnavailable
from ..models import (
	CollaborationCapabilitiesResponse,
	CollaborationCheckpointRequest,
	CollaborationCheckpointResponse,
	CollaborationJoinRequest,
	CollaborationJoinResponse,
	CollaborationSessionResponse,
	CollaborationVersionResponse,
)

router = APIRouter(prefix="/api/collaboration", tags=["collaboration"])
SUPPORTED_PROTOCOL = 1
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_MAX_RESPONSE_BYTES = 1 << 20
USER_AUTHORIZATION_UNAVAILABLE = "Map session actions require user authorization, which is not configured in Content Tools."
SessionID = Annotated[str, Path(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class CollaborationClient:
	"""Fixed lifecycle client for one trusted AphelionDMM service origin."""

	def __init__(
		self,
		base_url: str,
		service_token: str | None = None,
		*,
		timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
		max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
	) -> None:
		parsed = urlsplit(base_url)
		if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
			raise ValueError("Collaboration URL must be an HTTP(S) service origin without credentials.")
		if parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
			raise ValueError("Collaboration URL must not contain a path, query, or fragment.")
		if parsed.scheme == "http" and not _is_loopback(parsed.hostname):
			raise ValueError("Unencrypted collaboration URLs must use loopback.")
		if timeout_seconds <= 0 or max_response_bytes <= 0:
			raise ValueError("Collaboration client limits must be positive.")
		self._base_url = base_url.rstrip("/")
		# Retain the constructor argument for existing launch configurations, but never retain or
		# forward a service credential as authority for a browser user's remote actions.
		self._timeout_seconds = timeout_seconds
		self._max_response_bytes = max_response_bytes

	def version(self) -> CollaborationVersionResponse:
		payload = self._request("GET", "/v1/version")
		try:
			version = CollaborationVersionResponse.model_validate(payload | {"compatible": False})
		except ValidationError as exc:
			raise CollaborationUnavailable("AphelionDMM returned invalid version metadata.") from exc
		return version.model_copy(update={"compatible": SUPPORTED_PROTOCOL in version.protocol_versions})

	def session(self, session_id: str) -> CollaborationSessionResponse:
		raise CollaborationUnavailable(USER_AUTHORIZATION_UNAVAILABLE)

	def create_join_token(self, session_id: str, payload: CollaborationJoinRequest) -> CollaborationJoinResponse:
		raise CollaborationUnavailable(USER_AUTHORIZATION_UNAVAILABLE)

	def create_checkpoint(self, session_id: str, payload: CollaborationCheckpointRequest) -> CollaborationCheckpointResponse:
		raise CollaborationUnavailable(USER_AUTHORIZATION_UNAVAILABLE)

	def _request(self, method: str, path: str, body: dict[str, object] | None = None) -> dict[str, object]:
		encoded = None if body is None else json.dumps(body, separators=(",", ":")).encode()
		headers = {"Accept": "application/json"}
		if encoded is not None:
			headers["Content-Type"] = "application/json"
		request = Request(self._base_url + path, data=encoded, headers=headers, method=method)
		try:
			with urlopen(request, timeout=self._timeout_seconds) as response:
				data = response.read(self._max_response_bytes + 1)
		except HTTPError as exc:
			exc.close()
			raise CollaborationUnavailable("AphelionDMM is unavailable; no Content Tools data changed.") from exc
		except (URLError, TimeoutError, OSError) as exc:
			raise CollaborationUnavailable("AphelionDMM is unavailable; no Content Tools data changed.") from exc
		if len(data) > self._max_response_bytes:
			raise CollaborationUnavailable("AphelionDMM response exceeded the configured safety limit.")
		try:
			payload = json.loads(data)
		except (UnicodeDecodeError, json.JSONDecodeError) as exc:
			raise CollaborationUnavailable("AphelionDMM returned an invalid response.") from exc
		if not isinstance(payload, dict):
			raise CollaborationUnavailable("AphelionDMM returned an invalid response.")
		return payload

	@staticmethod
	def _validated(model: type[ResponseModel], payload: dict[str, object], label: str) -> ResponseModel:
		try:
			return model.model_validate(payload)
		except ValidationError as exc:
			raise CollaborationUnavailable(f"AphelionDMM returned invalid {label}.") from exc


def _is_loopback(hostname: str) -> bool:
	if hostname.casefold() == "localhost":
		return True
	try:
		return ipaddress.ip_address(hostname).is_loopback
	except ValueError:
		return False


def _client(request: FastAPIRequest) -> CollaborationClient:
	client = getattr(request.app.state, "collaboration_client", None)
	if not isinstance(client, CollaborationClient):
		raise CollaborationUnavailable("AphelionDMM collaboration is not configured.")
	return client


Client = Annotated[CollaborationClient, Depends(_client)]


@router.get("/capabilities", response_model=CollaborationCapabilitiesResponse)
def get_capabilities(request: FastAPIRequest) -> CollaborationCapabilitiesResponse:
	configured = isinstance(getattr(request.app.state, "collaboration_client", None), CollaborationClient)
	return CollaborationCapabilitiesResponse(
		configured=configured,
		version=configured,
		reason=USER_AUTHORIZATION_UNAVAILABLE if configured else "Map collaboration is not configured.",
	)


@router.get("/version", response_model=CollaborationVersionResponse)
def get_version(client: Client) -> CollaborationVersionResponse:
	return client.version()


@router.get("/sessions/{session_id}", response_model=CollaborationSessionResponse)
def get_session(session_id: SessionID, client: Client) -> CollaborationSessionResponse:
	return client.session(session_id)


@router.post("/sessions/{session_id}/join-tokens", response_model=CollaborationJoinResponse)
def post_join_token(session_id: SessionID, payload: CollaborationJoinRequest, client: Client, response: Response) -> CollaborationJoinResponse:
	response.status_code = HTTPStatus.CREATED
	return client.create_join_token(session_id, payload)


@router.post("/sessions/{session_id}/checkpoints", response_model=CollaborationCheckpointResponse)
def post_checkpoint(session_id: SessionID, payload: CollaborationCheckpointRequest, client: Client, response: Response) -> CollaborationCheckpointResponse:
	response.status_code = HTTPStatus.ACCEPTED
	return client.create_checkpoint(session_id, payload)

from __future__ import annotations

from http import HTTPStatus

from fastapi import Request
from fastapi.responses import JSONResponse

from tools.lore_editor.write_coordinator import RecordConflict

# A real error taxonomy.
#
# The pre-rewrite server answered every failure with the same handler, repeated 56 times:
#     except (OSError, ValueError) as exc: send_error_json(BAD_REQUEST, str(exc))
# so a malformed request, a missing game checkout, and an unreadable store were indistinguishable to the
# UI and to anyone reading a bug report. Each class below carries a status and a stable machine-readable
# `code`, so the frontend can react differently (retry, prompt for a path, show a validation message)
# without pattern-matching on human-readable prose.


class ApiError(Exception):
	"""Base for every deliberately-raised API failure."""

	status: HTTPStatus = HTTPStatus.BAD_REQUEST
	code: str = "error"

	def __init__(self, message: str) -> None:
		super().__init__(message)
		self.message = message


class BadRequest(ApiError):
	"""The caller sent something invalid. Retrying unchanged will fail the same way."""

	status = HTTPStatus.BAD_REQUEST
	code = "bad_request"


class NotFound(ApiError):
	"""The addressed resource does not exist."""

	status = HTTPStatus.NOT_FOUND
	code = "not_found"


class Conflict(ApiError):
	"""The request was well-formed but the target's current state forbids it.

	The export flow is the motivating case: a dirty game checkout, a changed revision, or an unexpected
	artifact hash is a stop condition the user must resolve, not a malformed request.
	"""

	status = HTTPStatus.CONFLICT
	code = "conflict"


class GameRepositoryUnavailable(ApiError):
	"""The configured Meridian-Rift checkout is missing, unreadable, or not a valid game repository.

	Distinct from BadRequest because the fix is environmental (point the app at a real checkout), not a
	correction to the request.
	"""

	status = HTTPStatus.SERVICE_UNAVAILABLE
	code = "game_repository_unavailable"


class StoreUnavailable(ApiError):
	"""The local data store could not be read or written."""

	status = HTTPStatus.SERVICE_UNAVAILABLE
	code = "store_unavailable"


def error_body(code: str, message: str) -> dict[str, str]:
	# `error` is kept as the message field for compatibility with the existing frontend, which reads
	# payload.error; `code` is the new machine-readable half.
	return {"error": message, "code": code}


async def handle_api_error(_request: Request, exc: Exception) -> JSONResponse:
	assert isinstance(exc, ApiError)
	return JSONResponse(status_code=exc.status, content=error_body(exc.code, exc.message))


async def handle_value_error(_request: Request, exc: Exception) -> JSONResponse:
	"""Domain modules signal invalid input with ValueError; that maps to 400.

	This is the one blanket handler, and it exists so domain code stays free of HTTP concerns -- not so
	that every failure collapses to the same status. Anything needing a different status raises the
	matching ApiError subclass above.
	"""
	return JSONResponse(
		status_code=HTTPStatus.BAD_REQUEST,
		content=error_body("bad_request", str(exc)),
	)


async def handle_record_conflict(_request: Request, exc: Exception) -> JSONResponse:
	assert isinstance(exc, RecordConflict)
	return JSONResponse(
		status_code=HTTPStatus.CONFLICT,
		content={
			"error": str(exc),
			"code": "record_conflict",
			"record_id": exc.record_id,
			"expected_hash": exc.expected_hash,
			"current_hash": exc.current_hash,
			"base": exc.base,
			"current": exc.current,
			"proposed": exc.proposed,
		},
	)


async def handle_os_error(_request: Request, exc: Exception) -> JSONResponse:
	"""Filesystem and subprocess failures. Environmental, so 503 rather than 400."""
	return JSONResponse(
		status_code=HTTPStatus.SERVICE_UNAVAILABLE,
		content=error_body("io_error", str(exc)),
	)

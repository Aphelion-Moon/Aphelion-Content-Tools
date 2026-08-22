from __future__ import annotations

import unittest
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from webapp.api import create_app
from webapp.api.errors import (
	ApiError,
	BadRequest,
	Conflict,
	GameRepositoryUnavailable,
	NotFound,
	StoreUnavailable,
)


class ErrorTaxonomyTests(unittest.TestCase):
	"""The taxonomy exists so failures are distinguishable.

	Pre-rewrite every failure was `400` with a bare message, repeated 56 times, so the UI could not tell
	bad input from a missing game checkout from an unreadable store.
	"""

	def test_each_error_class_carries_a_distinct_status_and_stable_code(self) -> None:
		cases = [
			(BadRequest, HTTPStatus.BAD_REQUEST, "bad_request"),
			(NotFound, HTTPStatus.NOT_FOUND, "not_found"),
			(Conflict, HTTPStatus.CONFLICT, "conflict"),
			(GameRepositoryUnavailable, HTTPStatus.SERVICE_UNAVAILABLE, "game_repository_unavailable"),
			(StoreUnavailable, HTTPStatus.SERVICE_UNAVAILABLE, "store_unavailable"),
		]
		for error_class, status, code in cases:
			with self.subTest(error=error_class.__name__):
				error = error_class("boom")
				self.assertEqual(error.status, status)
				self.assertEqual(error.code, code)
				self.assertEqual(error.message, "boom")
				self.assertIsInstance(error, ApiError)

	def test_codes_are_unique_so_the_frontend_can_branch_on_them(self) -> None:
		classes = [BadRequest, NotFound, Conflict, GameRepositoryUnavailable, StoreUnavailable]
		codes = [cls.code for cls in classes]
		self.assertEqual(len(codes), len(set(codes)))


class ApiContractTests(unittest.TestCase):
	"""Contract-level checks against a real app over a temporary repository root."""

	def setUp(self) -> None:
		self._temp = TemporaryDirectory()
		self.addCleanup(self._temp.cleanup)
		root = Path(self._temp.name)
		(root / "tools/lore_editor/stages").mkdir(parents=True, exist_ok=True)
		self.app = create_app(root, root)

	def test_health_reports_the_service(self) -> None:
		with TestClient(self.app) as client:
			response = client.get("/api/health")
		self.assertEqual(response.status_code, HTTPStatus.OK)
		self.assertEqual(response.json(), {"ok": True, "service": "aphelion-content-tools"})

	def test_openapi_schema_generates_and_documents_every_router(self) -> None:
		schema = self.app.openapi()
		paths = schema["paths"]
		# This schema is what `npm run gen:api` turns into the frontend's TypeScript types, so its
		# completeness is the whole Python -> OpenAPI -> TS contract.
		for expected in [
			"/api/health",
			"/api/store/health",
			"/api/search",
			"/api/tools",
			"/api/tools/active",
			"/api/git/status",
			"/api/graph",
			"/api/review",
			"/api/references",
			"/api/export/stages",
		]:
			self.assertIn(expected, paths, f"{expected} missing from the OpenAPI schema")

	def test_unknown_tool_run_is_404_not_400(self) -> None:
		with TestClient(self.app) as client:
			response = client.get("/api/tools/runs/does-not-exist")
		self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
		self.assertEqual(response.json()["code"], "not_found")

	def test_validation_failure_reports_the_offending_field(self) -> None:
		"""Pydantic replaces hand-rolled isinstance ladders, so errors name the field."""
		with TestClient(self.app) as client:
			response = client.post("/api/git/commit", json={"paths": [], "repository": "tool"})
		self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
		body = response.json()
		self.assertTrue(any("message" in str(detail.get("loc", ())) for detail in body["detail"]))

	def test_repository_name_is_constrained_to_tool_or_game(self) -> None:
		with TestClient(self.app) as client:
			response = client.get("/api/git/status", params={"repository": "somewhere-else"})
		self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

	def test_error_responses_carry_both_a_message_and_a_machine_code(self) -> None:
		with TestClient(self.app) as client:
			response = client.get("/api/tools/runs/nope")
		body = response.json()
		self.assertIn("error", body)
		self.assertIn("code", body)
		self.assertIsInstance(body["error"], str)


class ExportStagePathTests(unittest.TestCase):
	"""Stage names arrive from the client, so containment is enforced rather than assumed."""

	def setUp(self) -> None:
		self._temp = TemporaryDirectory()
		self.addCleanup(self._temp.cleanup)
		self.root = Path(self._temp.name)
		(self.root / "tools/lore_editor/stages").mkdir(parents=True, exist_ok=True)
		self.app = create_app(self.root, self.root)

	def test_apply_rejects_a_traversal_stage_name(self) -> None:
		with TestClient(self.app) as client:
			response = client.post("/api/export/apply", json={"stage": "../../../etc"})
		self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
		self.assertEqual(response.json()["code"], "bad_request")

	def test_apply_rejects_an_absolute_stage_name(self) -> None:
		with TestClient(self.app) as client:
			response = client.post("/api/export/apply", json={"stage": "C:/Windows"})
		self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

	def test_apply_rejects_an_empty_stage_name(self) -> None:
		with TestClient(self.app) as client:
			response = client.post("/api/export/apply", json={"stage": ""})
		self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

	def test_stages_listing_is_empty_rather_than_failing_when_nothing_is_prepared(self) -> None:
		with TestClient(self.app) as client:
			response = client.get("/api/export/stages")
		self.assertEqual(response.status_code, HTTPStatus.OK)
		self.assertEqual(response.json(), {"stages": []})


if __name__ == "__main__":
	unittest.main()

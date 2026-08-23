from __future__ import annotations

import unittest
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from tools.lore_editor.records import atomic_write_record, canonical_record_hash, record_path
from tools.lore_editor.tests.store_helpers import seed_override, seed_targets
from webapp.api import create_app
from webapp.api.errors import (
	ApiError,
	BadRequest,
	Conflict,
	GameRepositoryUnavailable,
	NotFound,
	StoreUnavailable,
)
from webapp.api.models import CommitInfo, GraphResponse
from webapp.store import db
from webapp.store.schema import encode, table
from webapp.store.search import SearchReport


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
		self.root = root
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

	def test_graph_response_omits_absent_fields_and_uses_transport_compression(self) -> None:
		graph = {
			"nodes": [{"id": "dir:.", "kind": "directory", "path": ".", "name": "r" * 2048}],
			"edges": [],
			"unresolved_markers": [],
			"counts": {
				"module_count": 0, "master_files_count": 0, "core_file_count": 0, "marker_count": 0,
				"unresolved_marker_count": 0, "file_count": 0, "directory_count": 1, "reference_count": 0,
			},
		}
		manifest = {
			"format_version": 1, "snapshot_sha256": "b" * 64, "game_repo_revision": "c" * 40,
			"generated_at": "2026-08-22T10:00:00+00:00", "node_count": 1, "edge_count": 0,
			"module_count": 0, "master_files_count": 0, "marker_count": 0, "file_count": 0,
			"directory_count": 1, "reference_count": 0,
		}
		with TestClient(self.app) as client:
			db.upsert_rows(table(self.root, "manifests"), "id", [{
				"id": "graph", "raw_json": encode({"manifest": manifest, "counts": graph["counts"], "graph": graph}), "text": "",
			}])
			response = client.get("/api/graph", headers={"Accept-Encoding": "gzip"})

		self.assertEqual(response.status_code, HTTPStatus.OK)
		self.assertNotIn('"owner":null', response.text)
		self.assertEqual(response.headers.get("content-encoding"), "gzip")

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

	def test_contextual_search_accepts_selected_context_and_reports_semantic_mode(self) -> None:
		report = SearchReport(
			results=({
				"table": "catalog_targets",
				"score": 0.02,
				"id": "/obj/item/radio",
				"record": {"label": "Radio", "type_path": "/obj/item/radio"},
				"scores": {"keyword_rrf": 0.016, "semantic_rrf": 0.0, "context_boost": 0.004, "final": 0.02},
				"context_reason": "related type path",
				"navigation": {
					"tool": "lore-editor",
					"route": "/lore-editor",
					"record_kind": "catalog_target",
					"record_id": "/obj/item/radio",
					"type_path": "/obj/item/radio",
				},
			},),
			semantic_mode="keyword-only",
			semantic_model_id="test-model",
			semantic_reason="offline",
		)
		with (
			TestClient(self.app) as client,
			patch("webapp.api.routes.store.search", return_value=report) as search_spy,
		):
			response = client.post("/api/search", json={
				"query": "radio",
				"limit": 6,
				"selected_context": {
					"tool": "lore-editor",
					"record_kind": "catalog_target",
					"record_id": "/obj/item/radio/headset",
					"type_path": "/obj/item/radio/headset",
					"groups": ["items"],
				},
				"scope": {"tables": ["catalog_targets"]},
			})

		self.assertEqual(response.status_code, HTTPStatus.OK)
		self.assertEqual(response.json()["semantic_search"]["mode"], "keyword-only")
		self.assertEqual(response.json()["results"][0]["navigation"]["record_id"], "/obj/item/radio")
		arguments = search_spy.call_args
		self.assertEqual(arguments.kwargs["tables"], ["catalog_targets"])
		self.assertEqual(arguments.kwargs["context"].type_path, "/obj/item/radio/headset")

	def test_commit_rejects_paths_outside_the_authoring_workflow(self) -> None:
		with TestClient(self.app) as client:
			response = client.post(
				"/api/git/commit",
				json={"paths": ["README.md"], "repository": "tool", "message": "Do not stage this"},
			)
		self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
		self.assertIn("not owned", response.json()["error"])

	def test_error_responses_carry_both_a_message_and_a_machine_code(self) -> None:
		with TestClient(self.app) as client:
			response = client.get("/api/tools/runs/nope")
		body = response.json()
		self.assertIn("error", body)
		self.assertIn("code", body)
		self.assertIsInstance(body["error"], str)

	def test_stale_lore_update_returns_a_structured_conflict(self) -> None:
		root = self.app.state.context.repo_root
		seed_targets(root, [{"type_path": "/obj/item/radio", "label": "Radio", "field_profile": "atom_like"}])
		original = {"id": "items.radio", "type_path": "/obj/item/radio", "name": "Original"}
		seed_override(root, "items", original)
		first_update = {"id": "items.radio", "type_path": "/obj/item/radio", "name": "First writer"}
		stale_update = {"id": "items.radio", "type_path": "/obj/item/radio", "name": "Stale writer"}
		payload = {
			"source_file": "tools/lore_editor/content/overrides/items.json",
			"entry": first_update,
			"expected_record_hash": canonical_record_hash(original),
		}
		with TestClient(self.app) as client:
			first = client.put("/api/entries/items.radio", json=payload)
			stale = client.put("/api/entries/items.radio", json={**payload, "entry": stale_update})

		self.assertEqual(first.status_code, HTTPStatus.OK)
		self.assertEqual(first.json()["record_hash"], canonical_record_hash(first_update))
		self.assertTrue(first.json()["projection"]["current"])
		self.assertEqual(stale.status_code, HTTPStatus.CONFLICT)
		self.assertEqual(stale.json()["code"], "record_conflict")
		self.assertEqual(stale.json()["record_id"], "items.radio")
		self.assertEqual(stale.json()["current"], first_update)
		self.assertEqual(stale.json()["proposed"], stale_update)

	def test_duplicate_lore_and_group_creates_return_conflicts_without_overwriting(self) -> None:
		root = self.app.state.context.repo_root
		seed_targets(root, [{"type_path": "/obj/item/radio", "label": "Radio", "field_profile": "atom_like"}])
		entry = {"id": "items.radio", "type_path": "/obj/item/radio", "name": "Original"}
		group = {"id": "items", "label": "Items", "color": "#ffffff"}
		with TestClient(self.app) as client:
			first_entry = client.post("/api/entries", json={
				"source_file": "tools/lore_editor/content/overrides/items.json",
				"entry": entry,
			})
			duplicate_entry = client.post("/api/entries", json={
				"source_file": "tools/lore_editor/content/overrides/items.json",
				"entry": {**entry, "name": "Second writer"},
			})
			first_group = client.post("/api/groups", json=group)
			duplicate_group = client.post("/api/groups", json={**group, "label": "Second writer"})

		self.assertEqual(first_entry.status_code, HTTPStatus.OK)
		self.assertEqual(duplicate_entry.status_code, HTTPStatus.CONFLICT)
		self.assertEqual(duplicate_entry.json()["code"], "record_conflict")
		self.assertEqual(duplicate_entry.json()["current"], entry)
		self.assertEqual(first_group.status_code, HTTPStatus.OK)
		self.assertEqual(duplicate_group.status_code, HTTPStatus.CONFLICT)
		self.assertEqual(duplicate_group.json()["code"], "record_conflict")
		self.assertEqual(duplicate_group.json()["current"]["label"], "Items")

	def test_openapi_documents_record_conflict_responses(self) -> None:
		schema = self.app.openapi()
		for path, method in (
			("/api/entries", "post"),
			("/api/entries/{entry_id}", "put"),
			("/api/groups", "post"),
			("/api/groups/{group_id}", "delete"),
			("/api/reviews/{type_path}", "put"),
			("/api/group-assignments/{type_path}", "put"),
		):
			response = schema["paths"][path][method]["responses"]["409"]
			self.assertEqual(
				response["content"]["application/json"]["schema"]["$ref"],
				"#/components/schemas/RecordConflictResponse",
			)

	def test_group_update_requires_and_checks_the_record_hash(self) -> None:
		create_payload = {
			"id": "items",
			"label": "Items",
			"color": "#ffffff",
			"keywords": [],
			"type_path_prefixes": ["/obj/item"],
		}
		with TestClient(self.app) as client:
			created = client.post("/api/groups", json=create_payload)
			missing = client.put("/api/groups/items", json={**create_payload, "label": "Missing hash"})
			updated = client.put("/api/groups/items", json={
				**create_payload,
				"label": "Updated",
				"expected_record_hash": created.json()["group"]["record_hash"],
			})
			stale = client.put("/api/groups/items", json={
				**create_payload,
				"label": "Stale",
				"expected_record_hash": created.json()["group"]["record_hash"],
			})

		self.assertEqual(created.status_code, HTTPStatus.OK)
		self.assertEqual(missing.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
		self.assertEqual(updated.status_code, HTTPStatus.OK)
		self.assertEqual(stale.status_code, HTTPStatus.CONFLICT)
		self.assertEqual(stale.json()["record_id"], "items")

	def test_review_write_uses_null_for_create_and_hash_for_update(self) -> None:
		path = "/api/reviews/%2Fobj%2Fitem%2Fradio"
		with TestClient(self.app) as client:
			missing = client.put(path, json={"status": "reviewed", "reviewed_by": "Zoe"})
			created = client.put(path, json={
				"status": "reviewed",
				"reviewed_by": "Zoe",
				"notes": "Initial",
				"expected_record_hash": None,
			})
			updated = client.put(path, json={
				"status": "needs-attention",
				"reviewed_by": "Zoe",
				"notes": "Changed",
				"expected_record_hash": created.json()["review"]["record_hash"],
			})
			stale = client.put(path, json={
				"status": "reviewed",
				"reviewed_by": "Zoe",
				"notes": "Stale",
				"expected_record_hash": created.json()["review"]["record_hash"],
			})

		self.assertEqual(missing.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
		self.assertEqual(created.status_code, HTTPStatus.OK)
		self.assertEqual(updated.status_code, HTTPStatus.OK)
		self.assertEqual(stale.status_code, HTTPStatus.CONFLICT)
		self.assertEqual(stale.json()["record_id"], "/obj/item/radio")

	def test_assignment_write_uses_an_independent_record_hash(self) -> None:
		with TestClient(self.app) as client:
			client.post("/api/groups", json={"id": "items", "label": "Items", "color": "#fff"})
			client.post("/api/groups", json={"id": "devices", "label": "Devices", "color": "#000"})
			path = "/api/group-assignments/%2Fobj%2Fitem%2Fradio"
			created = client.put(path, json={
				"group_ids": ["items"],
				"expected_record_hash": None,
			})
			updated = client.put(path, json={
				"group_ids": ["items", "devices"],
				"expected_record_hash": created.json()["record_hash"],
			})
			stale = client.put(path, json={
				"group_ids": ["devices"],
				"expected_record_hash": created.json()["record_hash"],
			})

		self.assertEqual(created.status_code, HTTPStatus.OK)
		self.assertEqual(created.json()["assignment"]["group_ids"], ["items"])
		self.assertEqual(updated.status_code, HTTPStatus.OK)
		self.assertNotEqual(updated.json()["record_hash"], created.json()["record_hash"])
		self.assertEqual(stale.status_code, HTTPStatus.CONFLICT)
		self.assertEqual(stale.json()["record_id"], "/obj/item/radio")

	def test_external_canonical_change_blocks_authoring_until_reconciled(self) -> None:
		root = self.app.state.context.repo_root
		create_payload = {"id": "items", "label": "Items", "color": "#fff"}
		with TestClient(self.app) as client:
			created = client.post("/api/groups", json=create_payload)
			atomic_write_record(record_path(root, "group", "external"), {
				"id": "external",
				"label": "External",
				"color": "#000",
				"keywords": [],
				"type_path_prefixes": [],
				"keyword_scope": ["name", "description", "label"],
			})
			blocked = client.put("/api/groups/items", json={
				**create_payload,
				"label": "Blocked",
				"expected_record_hash": created.json()["group"]["record_hash"],
			})
			reconciled = client.post("/api/store/reconcile")
			updated = client.put("/api/groups/items", json={
				**create_payload,
				"label": "Allowed",
				"expected_record_hash": created.json()["group"]["record_hash"],
			})

		self.assertEqual(blocked.status_code, HTTPStatus.CONFLICT)
		self.assertEqual(blocked.json()["code"], "conflict")
		self.assertIn("reconcile", blocked.json()["error"].casefold())
		self.assertEqual(reconciled.status_code, HTTPStatus.OK)
		self.assertEqual(updated.status_code, HTTPStatus.OK)


class ResponseModelMatchesDomainTests(unittest.TestCase):
	"""Response models must match what the domain layer actually returns.

	Added after RepositoryStatus was written with a guessed shape -- `changed_files` as a list of
	{path, status} objects -- when git_adapter really returns plain path strings, and omitted `dirty`,
	`upstream`, and `conflict_files` entirely. Nothing caught it, because no test exercised the endpoint
	against a real repository. These tests compare the model against the dataclass directly.
	"""

	def test_repository_status_model_covers_every_dataclass_field(self) -> None:
		from dataclasses import fields

		from webapp.api.models import RepositoryStatus as StatusModel
		from webapp.git_adapter import RepositoryStatus as StatusDataclass

		dataclass_fields = {field.name for field in fields(StatusDataclass)}
		model_fields = set(StatusModel.model_fields)
		missing = dataclass_fields - model_fields
		self.assertFalse(missing, f"RepositoryStatus model is missing: {sorted(missing)}")

	def test_repository_status_accepts_a_real_adapter_payload(self) -> None:
		from dataclasses import asdict

		from webapp.api.models import RepositoryStatus as StatusModel
		from webapp.git_adapter import RepositoryStatus as StatusDataclass

		status = StatusDataclass(
			branch="main",
			upstream="origin/main",
			ahead=1,
			behind=2,
			dirty=True,
			changed_files=("webapp/server.py", "README.md"),
			conflict_files=(),
		)
		parsed = StatusModel.model_validate(asdict(status) | {"conflicted": status.conflicted})
		self.assertEqual(parsed.changed_files, ["webapp/server.py", "README.md"])
		self.assertTrue(parsed.dirty)
		self.assertFalse(parsed.conflicted)

	def test_marker_history_model_matches_the_git_adapter_payload(self) -> None:
		parsed = CommitInfo.model_validate({
			"commit": "a" * 40,
			"short_commit": "a" * 12,
			"author": "Zoe",
			"date": "2026-08-22",
			"subject": "Explain the marker (#123)",
			"diff": "+// APHELION EDIT",
			"pr_url": "https://github.com/example/repo/pull/123",
		})
		self.assertEqual(parsed.short_commit, "a" * 12)
		self.assertEqual(parsed.subject, "Explain the marker (#123)")

	def test_graph_response_validates_the_explicit_wire_document(self) -> None:
		parsed = GraphResponse.model_validate({
			"scanned": True,
			"graph": {
				"nodes": [{"id": "dir:.", "kind": "directory", "path": ".", "name": "root"}],
				"edges": [],
				"unresolved_markers": [],
				"counts": {
					"module_count": 0,
					"master_files_count": 0,
					"core_file_count": 0,
					"marker_count": 0,
					"unresolved_marker_count": 0,
					"file_count": 0,
					"directory_count": 1,
					"reference_count": 0,
				},
			},
			"manifest": {
				"format_version": 1,
				"snapshot_sha256": "b" * 64,
				"game_repo_revision": "c" * 40,
				"generated_at": "2026-08-22T10:00:00+00:00",
				"node_count": 1,
				"edge_count": 0,
				"module_count": 0,
				"master_files_count": 0,
				"marker_count": 0,
				"file_count": 0,
				"directory_count": 1,
				"reference_count": 0,
			},
		})
		self.assertEqual(parsed.graph.nodes[0].kind, "directory")


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

	def test_apply_rejects_the_removed_dirty_checkout_force_field(self) -> None:
		with TestClient(self.app) as client:
			response = client.post("/api/export/apply", json={"stage": "example", "force": True})
		self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

	def test_stages_listing_is_empty_rather_than_failing_when_nothing_is_prepared(self) -> None:
		with TestClient(self.app) as client:
			response = client.get("/api/export/stages")
		self.assertEqual(response.status_code, HTTPStatus.OK)
		self.assertEqual(response.json(), {"stages": []})


if __name__ == "__main__":
	unittest.main()

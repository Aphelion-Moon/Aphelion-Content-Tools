from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.definition_editor.tests.test_authoring import draft
from webapp.api import create_app
from webapp.tests.http_client import TestClient


class DefinitionEditorApiTests(unittest.TestCase):
	def test_capability_catalog_matches_generated_frontend_routes(self) -> None:
		from webapp.capabilities import CAPABILITIES
		root = Path(__file__).resolve().parents[2]
		generated = json.loads((root / 'webapp/frontend/src/lib/tool-capabilities.json').read_text())
		self.assertEqual(generated, [item.model_dump() for item in CAPABILITIES])
		for kind in ('job', 'outfit'):
			capability = next(item for item in CAPABILITIES if item.id == f'{kind}-editor')
			self.assertIn('job-outfit-definitions', capability.datasets)
			self.assertIn('staged-game-apply', capability.mutations)
			self.assertNotIn('semantic', capability.search)
	def test_offline_drafts_save_reload_and_conflict(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			client = TestClient(create_app(root, root / 'game'))
			try:
				payload = {'draft': draft().model_dump(), 'expected_record_hash': None}
				response = client.post('/api/definitions/drafts', json=payload)
				self.assertEqual(response.status_code, 200, response.text)
				self.assertEqual(client.post('/api/definitions/drafts', json=payload).status_code, 409)
				loaded = client.get('/api/definitions/drafts?kind=outfit')
				self.assertEqual(loaded.status_code, 200, loaded.text)
				self.assertEqual(loaded.json()['drafts'][0]['record_hash'], response.json()['record_hash'])
			finally:
				client.close()

	def test_catalog_unavailable_does_not_claim_current(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			client = TestClient(create_app(root, root / 'game'))
			try:
				response = client.get('/api/definitions/status')
				self.assertEqual(response.status_code, 200, response.text)
				self.assertFalse(response.json()['current'])
				self.assertIsNotNone(response.json()['reason'])
			finally:
				client.close()

	def test_application_without_validated_server_stage_is_refused(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			client = TestClient(create_app(root, root / 'game'))
			try:
				saved = client.post('/api/definitions/drafts', json={'draft': draft().model_dump()})
				self.assertEqual(saved.status_code, 200, saved.text)
				response = client.post('/api/definitions/apply', json={'kind': 'outfit', 'id': 'test-outfit', 'record_hash': saved.json()['record_hash'], 'stage_id': 'invented'})
				self.assertEqual(response.status_code, 400, response.text)
			finally:
				client.close()

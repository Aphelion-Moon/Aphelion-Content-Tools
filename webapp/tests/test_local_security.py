from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from webapp.api import create_app


class LocalSecurityTests(unittest.TestCase):
	def setUp(self) -> None:
		self.temporary = tempfile.TemporaryDirectory()
		self.addCleanup(self.temporary.cleanup)
		self.app = create_app(Path(self.temporary.name))
		self.app.post('/api/probe')(lambda: {'saved': True})
		self.client = TestClient(self.app, base_url='http://127.0.0.1:8765')
		self.addCleanup(self.client.close)

	def test_mutations_require_the_current_launch_session(self) -> None:
		self.assertEqual(self.client.post('/api/probe').status_code, 401)
		response = self.client.get('/api/session')
		self.assertEqual(response.status_code, 200)
		self.assertIn('httponly', response.headers['set-cookie'].lower())
		self.assertIn('samesite=strict', response.headers['set-cookie'].lower())
		self.assertEqual(self.client.post('/api/probe').status_code, 200)

	def test_host_and_origin_are_checked_before_session_bootstrap_or_mutation(self) -> None:
		self.assertEqual(self.client.get('/api/session', headers={'host': 'attacker.invalid:8765'}).status_code, 403)
		self.client.get('/api/session')
		for origin in ('https://attacker.invalid', 'http://127.0.0.1:8766', 'null'):
			with self.subTest(origin=origin):
				self.assertEqual(self.client.post('/api/probe', headers={'origin': origin}).status_code, 403)
		self.assertEqual(self.client.post('/api/probe', headers={'origin': 'http://127.0.0.1:8765'}).status_code, 200)

	def test_websocket_requires_session_and_exact_origin(self) -> None:
		with self.assertRaises(WebSocketDisconnect), self.client.websocket_connect('/ws', headers={'origin': 'http://127.0.0.1:8765'}):
			pass
		self.client.get('/api/session')
		with self.assertRaises(WebSocketDisconnect), self.client.websocket_connect('/ws', headers={'origin': 'https://attacker.invalid'}):
			pass

	def test_large_request_is_rejected_before_dispatch(self) -> None:
		self.client.get('/api/session')
		self.assertEqual(self.client.post('/api/probe', content=b'x' * (5 * 1024 * 1024)).status_code, 413)

	def test_unknown_api_path_is_not_a_successful_html_page(self) -> None:
		self.client.get('/api/session')
		self.assertEqual(self.client.get('/api/does-not-exist').status_code, 404)

	def test_future_mutations_and_session_post_are_not_public(self) -> None:
		self.app.post('/probe')(lambda: {'saved': True})
		self.assertEqual(self.client.post('/probe').status_code, 401)
		self.assertEqual(self.client.post('/api/session').status_code, 401)


if __name__ == '__main__':
	unittest.main()

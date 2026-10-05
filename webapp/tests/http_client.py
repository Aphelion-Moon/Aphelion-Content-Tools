"""Explicit same-origin session setup for authorized API contract tests.

Security boundary tests use FastAPI's raw TestClient instead of this helper.
"""
from fastapi.testclient import TestClient as FastAPITestClient


class TestClient(FastAPITestClient):
	def __init__(self, app, **kwargs):
		kwargs.setdefault('base_url', 'http://127.0.0.1')
		super().__init__(app, **kwargs)
		response = self.get('/api/session')
		response.raise_for_status()

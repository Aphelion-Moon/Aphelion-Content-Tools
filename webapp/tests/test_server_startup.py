from __future__ import annotations

import json
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVE_PATH = REPO_ROOT / "webapp" / "serve.py"


class ServerStartupTests(unittest.TestCase):
	def setUp(self) -> None:
		self.process = subprocess.Popen(
			[
				sys.executable,
				str(SERVE_PATH),
				"--repo-root",
				str(REPO_ROOT),
				"--port",
				"0",
			],
			cwd=REPO_ROOT,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			text=True,
		)
		assert self.process.stdout is not None
		deadline = time.time() + 10
		line = ""
		while time.time() < deadline:
			line = self.process.stdout.readline().strip()
			if line.startswith("LORE_EDITOR_URL="):
				break
			if self.process.poll() is not None:
				break
		if not line.startswith("LORE_EDITOR_URL="):
			self.fail(f"Editor did not announce a URL: {line!r}")
		self.base_url = line.split("=", 1)[1]

	def tearDown(self) -> None:
		if self.process.poll() is None:
			self.process.terminate()
			self.process.wait(timeout=5)
		if self.process.stdout is not None:
			self.process.stdout.close()
		if self.process.stderr is not None:
			self.process.stderr.close()

	def fetch(self, path: str) -> tuple[int, str, str]:
		try:
			with urllib.request.urlopen(self.base_url + path, timeout=5) as response:
				return response.status, response.headers.get_content_type(), response.read().decode("utf-8")
		except urllib.error.HTTPError as exc:
			return exc.code, exc.headers.get_content_type(), exc.read().decode("utf-8")

	def test_health_endpoint(self) -> None:
		status, content_type, body = self.fetch("/api/health")

		self.assertEqual(status, 200)
		self.assertEqual(content_type, "application/json")
		self.assertEqual(json.loads(body), {"ok": True, "service": "aphelion-content-tools"})

	def test_store_health_endpoint_reports_table_row_counts_and_disk_usage(self) -> None:
		status, content_type, body = self.fetch("/api/store/health")

		self.assertEqual(status, 200)
		self.assertEqual(content_type, "application/json")
		payload = json.loads(body)
		self.assertIsInstance(payload.get("tables"), dict)
		self.assertIsInstance(payload.get("total_rows"), int)
		self.assertIsInstance(payload.get("disk_bytes"), int)

	def test_tools_active_endpoint_reports_no_active_runs_when_idle(self) -> None:
		# The real repo root's store worker (if one exists from other tests/manual use) may or may not be
		# alive, but either way, nothing here has started a run against it -- so the honest answer is an
		# empty list, without this endpoint spawning a worker just to answer.
		status, content_type, body = self.fetch("/api/tools/active")

		self.assertEqual(status, 200)
		self.assertEqual(content_type, "application/json")
		self.assertEqual(json.loads(body), {"active_runs": []})

	def test_root_serves_home_and_missing_path_is_404(self) -> None:
		status, content_type, body = self.fetch("/")

		self.assertEqual(status, 200)
		self.assertEqual(content_type, "text/html")
		self.assertIn("Aphelion Content Tools", body)
		self.assertIn("About", body)
		self.assertIn('href="/file-management"', body)
		self.assertIn('href="/lore-editor"', body)
		self.assertIn('href="/graph"', body)

		missing_status, _missing_type, _missing_body = self.fetch("/missing")
		self.assertEqual(missing_status, 404)

		favicon_status, favicon_type, _favicon_body = self.fetch("/favicon.ico")
		self.assertEqual(favicon_status, 200)
		self.assertEqual(favicon_type, "image/svg+xml")

	def test_file_management_page_and_its_assets_are_served(self) -> None:
		html_status, html_type, html_body = self.fetch("/file-management")
		self.assertEqual(html_status, 200)
		self.assertEqual(html_type, "text/html")
		self.assertIn("Database and Git", html_body)
		self.assertIn('id="tool-status"', html_body)
		self.assertIn('id="export-stage-select"', html_body)
		self.assertIn('href="/"', html_body)

		js_status, js_type, _js_body = self.fetch("/file-management.js")
		self.assertEqual(js_status, 200)
		self.assertEqual(js_type, "text/javascript")

	def test_lore_editor_page_and_its_assets_are_served(self) -> None:
		html_status, html_type, html_body = self.fetch("/lore-editor")
		self.assertEqual(html_status, 200)
		self.assertEqual(html_type, "text/html")
		self.assertIn("Lore Editor", html_body)
		self.assertIn('id="entry-form"', html_body)
		self.assertIn('href="/"', html_body)

		js_status, js_type, _js_body = self.fetch("/lore-editor.js")
		self.assertEqual(js_status, 200)
		self.assertEqual(js_type, "text/javascript")

	def test_graph_page_and_its_assets_are_served(self) -> None:
		html_status, html_type, html_body = self.fetch("/graph")
		self.assertEqual(html_status, 200)
		self.assertEqual(html_type, "text/html")
		self.assertIn("Content Graph", html_body)
		self.assertIn('href="/"', html_body)
		self.assertIn('href="/lore-editor"', html_body)
		self.assertIn('href="/modular-debug"', html_body)
		self.assertIn('id="explorer-tree"', html_body)
		self.assertIn('id="physics-stats"', html_body)
		self.assertIn('id="graph-container"', html_body)

		js_status, js_type, _js_body = self.fetch("/graph.js")
		self.assertEqual(js_status, 200)
		self.assertEqual(js_type, "text/javascript")

	def test_parsec_page_and_its_assets_are_served(self) -> None:
		html_status, html_type, html_body = self.fetch("/parsec")
		self.assertEqual(html_status, 200)
		self.assertEqual(html_type, "text/html")
		self.assertIn("About Parsec", html_body)
		self.assertIn('id="parsec-motion-select"', html_body)
		self.assertIn('id="parsec-announcement-log"', html_body)

		engine_status, engine_type, _engine_body = self.fetch("/parsec.js")
		self.assertEqual(engine_status, 200)
		self.assertEqual(engine_type, "text/javascript")

		page_status, page_type, _page_body = self.fetch("/parsec-page.js")
		self.assertEqual(page_status, 200)
		self.assertEqual(page_type, "text/javascript")

		# Not using self.fetch() here -- it decodes the body as UTF-8, which a real PNG's binary
		# content isn't guaranteed to be valid as.
		with urllib.request.urlopen(self.base_url + "/parsec.png", timeout=5) as response:
			self.assertEqual(response.status, 200)
			self.assertEqual(response.headers.get_content_type(), "image/png")
			self.assertTrue(response.read().startswith(b"\x89PNG"))

		css_status, css_type, _css_body = self.fetch("/graph.css")
		self.assertEqual(css_status, 200)
		self.assertEqual(css_type, "text/css")

		for vendor_file in (
			"graphology.umd.min.js",
			"sigma.min.js",
			"d3-quadtree.v3.js",
			"d3-dispatch.v3.js",
			"d3-timer.v3.js",
			"d3-force.v3.js",
		):
			vendor_status, vendor_type, _vendor_body = self.fetch("/vendor/" + vendor_file)
			self.assertEqual(vendor_status, 200, vendor_file)
			self.assertEqual(vendor_type, "text/javascript", vendor_file)

	def test_modular_debug_page_and_its_assets_are_served(self) -> None:
		html_status, html_type, html_body = self.fetch("/modular-debug")
		self.assertEqual(html_status, 200)
		self.assertEqual(html_type, "text/html")
		self.assertIn("Modular Debug", html_body)
		self.assertIn('href="/graph"', html_body)
		self.assertIn('id="debug-core-file"', html_body)
		self.assertIn('id="unresolved-list"', html_body)

		js_status, js_type, _js_body = self.fetch("/modular-debug.js")
		self.assertEqual(js_status, 200)
		self.assertEqual(js_type, "text/javascript")

		css_status, css_type, _css_body = self.fetch("/modular-debug.css")
		self.assertEqual(css_status, 200)
		self.assertEqual(css_type, "text/css")

	def test_shared_open_in_menu_and_floating_ui_are_served(self) -> None:
		js_status, js_type, js_body = self.fetch("/open-in-menu.js")
		self.assertEqual(js_status, 200)
		self.assertEqual(js_type, "text/javascript")
		self.assertIn("AphelionOpenInMenu", js_body)

		for vendor_file in ("floating-ui-core.umd.min.js", "floating-ui-dom.umd.min.js"):
			vendor_status, vendor_type, _vendor_body = self.fetch("/" + vendor_file)
			self.assertEqual(vendor_status, 200, vendor_file)
			self.assertEqual(vendor_type, "text/javascript", vendor_file)

	def test_shared_references_panel_and_api_are_served(self) -> None:
		js_status, js_type, js_body = self.fetch("/references-panel.js")
		self.assertEqual(js_status, 200)
		self.assertEqual(js_type, "text/javascript")
		self.assertIn("AphelionReferences", js_body)

		# These routes run against the real repo's store (see REPO_ROOT above), which accumulates
		# genuine data as the tools are used -- so this only checks response shape, not emptiness.
		list_status, list_type, list_body = self.fetch("/api/references")
		self.assertEqual(list_status, 200)
		self.assertEqual(list_type, "application/json")
		list_payload = json.loads(list_body)
		self.assertIsInstance(list_payload.get("references"), list)

		search_status, search_type, search_body = self.fetch("/api/search?q=radio")
		self.assertEqual(search_status, 200)
		self.assertEqual(search_type, "application/json")
		search_payload = json.loads(search_body)
		self.assertIsInstance(search_payload.get("results"), list)


if __name__ == "__main__":
	unittest.main()

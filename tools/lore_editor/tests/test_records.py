from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.lore_editor.records import (
	atomic_write_record,
	canonical_record_bytes,
	canonical_record_hash,
	read_record,
	record_path,
)
from tools.lore_editor.taxonomy import _group_from_raw


class CanonicalRecordTests(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp_dir.cleanup)
		self.repo_root = Path(self.temp_dir.name)

	def test_canonical_record_bytes_are_stable_utf8_json(self) -> None:
		payload = {"label": "Freyja — Ice Moon", "id": "celestial-bodies", "keywords": ["freyja"]}
		expected = (
			'{\n'
			'  "id": "celestial-bodies",\n'
			'  "keywords": [\n'
			'    "freyja"\n'
			'  ],\n'
			'  "label": "Freyja — Ice Moon"\n'
			'}\n'
		).encode()

		self.assertEqual(canonical_record_bytes(payload), expected)
		self.assertEqual(canonical_record_hash(payload), hashlib.sha256(expected).hexdigest())

	def test_record_paths_are_collision_free_and_readable(self) -> None:
		self.assertEqual(
			record_path(self.repo_root, "override", "items.radio"),
			self.repo_root / "tools/lore_editor/content/overrides/items.radio.json",
		)
		self.assertEqual(
			record_path(self.repo_root, "group", "nanotrasen"),
			self.repo_root / "tools/lore_editor/content/groups/nanotrasen.json",
		)
		self.assertEqual(
			record_path(self.repo_root, "review", "/obj/a_b"),
			self.repo_root / "tools/lore_editor/content/reviews/obj/a_b.json",
		)
		self.assertEqual(
			record_path(self.repo_root, "review", "/obj/a/b"),
			self.repo_root / "tools/lore_editor/content/reviews/obj/a/b.json",
		)
		self.assertEqual(
			record_path(self.repo_root, "assignment", "/datum/language/common"),
			self.repo_root / "tools/lore_editor/content/assignments/datum/language/common.json",
		)

	def test_record_paths_reject_invalid_ids_and_traversal(self) -> None:
		for kind, record_id in (
			("override", "../items.radio"),
			("group", "Not A Group"),
			("review", "/obj/../secret"),
			("assignment", "obj/item/radio"),
		):
			with self.subTest(kind=kind, record_id=record_id), self.assertRaises(ValueError):
				record_path(self.repo_root, kind, record_id)

	def test_atomic_write_record_replaces_the_complete_file(self) -> None:
		path = record_path(self.repo_root, "group", "nanotrasen")
		atomic_write_record(path, {"id": "nanotrasen", "label": "Old"})
		atomic_write_record(path, {"id": "nanotrasen", "label": "New"})

		self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["label"], "New")
		self.assertEqual(read_record(path), {"id": "nanotrasen", "label": "New"})
		self.assertEqual(path.read_bytes(), canonical_record_bytes({"id": "nanotrasen", "label": "New"}))
		self.assertEqual(list(path.parent.glob("*.tmp")), [])

	def test_repository_restores_the_approved_groups_without_the_deleted_review(self) -> None:
		content_root = Path(__file__).resolve().parents[1] / "content"
		group_payloads = [
			json.loads(path.read_text(encoding="utf-8"))
			for path in sorted((content_root / "groups").glob("*.json"))
		]

		self.assertEqual(
			{payload["id"] for payload in group_payloads},
			{
				"celestial-bodies",
				"groups-of-interest",
				"interdyne",
				"languages",
				"manufacturing-companies",
				"nanotrasen",
				"nova-sector",
				"races",
			},
		)
		for payload in group_payloads:
			self.assertEqual(_group_from_raw(payload).id, payload["id"])
		self.assertEqual(list((content_root / "reviews").rglob("*.json")), [])


if __name__ == "__main__":
	unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.lore_editor.tests.store_helpers import seed_override, seed_targets
from webapp.store import db
from webapp.store.schema import table


class LoreEditorRoundTripTests(unittest.TestCase):
	def test_serialized_entry_round_trips_without_determinism_drift(self) -> None:
		from tools.lore_editor.api import list_entries, save_entry

		with tempfile.TemporaryDirectory() as temp_dir:
			repo_root = Path(temp_dir)
			seed_targets(repo_root, [{"type_path": "/obj/item/radio", "label": "Radio", "field_profile": "atom_like"}])
			seed_override(repo_root, "items", {
				"id": "items.radio",
				"type_path": "/obj/item/radio",
				"name": "Station handset",
				"description": "A durable communications device.",
			})

			serialized_entry = list_entries(repo_root)[0]
			first = save_entry(
				repo_root,
				entry_id=serialized_entry["id"],
				source_file=serialized_entry["source_file"],
				entry=serialized_entry["raw"],
			)
			generated_path = repo_root / "tools/lore_editor/stages/current/generated_lore_overrides.dm"
			first_row = db.get_row(table(repo_root, "overrides"), "id = 'items.radio'")
			first_generated_bytes = generated_path.read_bytes()

			second = save_entry(
				repo_root,
				entry_id=serialized_entry["id"],
				source_file=serialized_entry["source_file"],
				entry=first["raw"],
			)

			self.assertEqual(second["raw"], serialized_entry["raw"])
			self.assertEqual(db.get_row(table(repo_root, "overrides"), "id = 'items.radio'"), first_row)
			self.assertEqual(generated_path.read_bytes(), first_generated_bytes)


if __name__ == "__main__":
	unittest.main()

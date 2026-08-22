from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.lore_editor.source import make_catalog_target
from tools.lore_editor.taxonomy import (
	GroupRecord,
	ReviewRecord,
	classify_target,
	classify_target_details,
	load_groups,
	load_reviews,
	save_group,
	save_group_assignments,
	save_review,
)
from tools.lore_editor.tests.store_helpers import seed_assignment, seed_group, seed_review


class TaxonomyTests(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.repo_root = Path(self.temp_dir.name)

	def tearDown(self) -> None:
		self.temp_dir.cleanup()

	def test_groups_reviews_and_assignments_round_trip_through_the_store(self) -> None:
		seed_group(self.repo_root, {
			"id": "items",
			"label": "Items",
			"color": "#fff",
			"keywords": ["item"],
			"type_path_prefixes": ["/obj/item"],
		})
		seed_assignment(self.repo_root, "/obj/item/radio", ["items"])
		seed_review(self.repo_root, "/obj/item/radio", {
			"status": "reviewed",
			"reviewed_by": "Writer",
			"reviewed_at": "2026-08-20T12:00:00+00:00",
			"notes": "Approved",
		})

		groups = load_groups(self.repo_root)
		reviews = load_reviews(self.repo_root)

		self.assertEqual(("items",), groups.assignments["/obj/item/radio"])
		self.assertEqual("reviewed", reviews["/obj/item/radio"].status)

		save_group(self.repo_root, GroupRecord("items", "Updated Items", "#000", ("radio",), ("/obj/item",)))
		save_group_assignments(self.repo_root, "/obj/item/radio", ())
		save_review(self.repo_root, "/obj/item/radio", None)

		self.assertEqual(load_groups(self.repo_root).groups[0].label, "Updated Items")
		self.assertEqual(load_groups(self.repo_root).assignments.get("/obj/item/radio", ()), ())
		self.assertEqual(load_reviews(self.repo_root), {})

	def test_default_groups_are_available_for_a_new_repository(self) -> None:
		seed_group(self.repo_root, {
			"id": "languages",
			"label": "Languages",
			"color": "#60a5fa",
			"type_path_prefixes": ["/datum/language"],
		})
		groups = load_groups(self.repo_root)
		self.assertEqual([group.id for group in groups.groups], ["languages"])
		self.assertEqual(groups.groups[0].color, "#60a5fa")

	def test_classification_uses_type_prefixes_and_keywords(self) -> None:
		seed_group(self.repo_root, {
			"id": "languages",
			"label": "Languages",
			"color": "#60a5fa",
			"type_path_prefixes": ["/datum/language"],
		})
		seed_group(self.repo_root, {
			"id": "nanotrasen",
			"label": "Nanotrasen",
			"color": "#34d399",
			"keywords": ["nanotrasen"],
		})
		groups = load_groups(self.repo_root)
		target = make_catalog_target({
			"type_path": "/datum/language/common",
			"label": "Nanotrasen Common",
			"base_values": {"description": "A language used by Nanotrasen crews."},
		})
		self.assertEqual(classify_target(target, groups), ("languages", "nanotrasen"))

	def test_keyword_matching_uses_word_boundaries_and_excludes_icon_metadata(self) -> None:
		seed_group(self.repo_root, {
			"id": "nanotrasen",
			"label": "Nanotrasen",
			"color": "#34d399",
			"keywords": ["nt", "nanotrasen"],
			"type_path_prefixes": [],
		})
		groups = load_groups(self.repo_root)
		unrelated_target = make_catalog_target({
			"type_path": "/obj/item/radio/intercom",
			"label": "Intercom",
			"base_values": {"name": "Intercom", "description": "A station communications device."},
			"icon_metadata": {
				"icon": {
					"file": "icons/obj/intercom.dmi",
					"state": "intercom",
					"available_states": ["nanotrasen"],
				},
			},
		})
		company_target = make_catalog_target({
			"type_path": "/obj/item/radio/headset/nanotrasen",
			"label": "Nanotrasen headset",
			"base_values": {"name": "Nanotrasen headset", "description": "A headset issued by Nanotrasen."},
		})

		self.assertEqual(classify_target(unrelated_target, groups), ())
		self.assertEqual(classify_target(company_target, groups), ("nanotrasen",))

	def test_classification_explains_prefix_and_keyword_matches(self) -> None:
		seed_group(self.repo_root, {
			"id": "nanotrasen",
			"label": "Nanotrasen",
			"color": "#34d399",
			"keywords": ["nanotrasen"],
			"type_path_prefixes": ["/obj/item"],
		})
		groups = load_groups(self.repo_root)
		target = make_catalog_target({
			"type_path": "/obj/item/clothing/head/helmet/nanotrasen",
			"label": "SWAT helmet",
			"base_values": {
				"name": "SWAT helmet",
				"description": "An official Nanotrasen helmet.",
			},
		})

		# "nanotrasen" also appears in the type path, but keyword matching defaults to name/description/label
		# only (type_path_prefixes is the dedicated, explicit way to match by path) -- see
		# test_keyword_scope_excludes_type_path_by_default for the regression this guards against.
		self.assertEqual(classify_target_details(target, groups), {
			"nanotrasen": (
				"type path prefix '/obj/item'",
				"keyword 'nanotrasen' in description",
			),
		})

	def test_keyword_scope_excludes_type_path_by_default(self) -> None:
		seed_group(self.repo_root, {
			"id": "nova-sector",
			"label": "Nova Sector",
			"color": "#a853d0",
			"keywords": ["nova"],
			"type_path_prefixes": [],
		})
		groups = load_groups(self.repo_root)
		unrelated_target = make_catalog_target({
			"type_path": "/obj/item/clothing/head/nova_helmet",
			"label": "Helmet",
			"base_values": {"name": "Helmet", "description": "A standard-issue helmet."},
		})

		self.assertEqual(classify_target(unrelated_target, groups), ())

	def test_keyword_scope_can_be_widened_to_include_type_path(self) -> None:
		seed_group(self.repo_root, {
			"id": "nova-sector",
			"label": "Nova Sector",
			"color": "#a853d0",
			"keywords": ["nova"],
			"type_path_prefixes": [],
			"keyword_scope": ["type_path"],
		})
		groups = load_groups(self.repo_root)
		target = make_catalog_target({
			"type_path": "/obj/item/clothing/head/nova_helmet",
			"label": "Helmet",
			"base_values": {"name": "Helmet", "description": "A standard-issue helmet."},
		})

		self.assertEqual(classify_target_details(target, groups), {
			"nova-sector": ("keyword 'nova' in type path",),
		})

	def test_keyword_scope_rejects_unknown_fields(self) -> None:
		with self.assertRaises(ValueError):
			save_group(self.repo_root, GroupRecord(
				id="bogus",
				label="Bogus",
				color="#fff",
				keywords=("x",),
				type_path_prefixes=(),
				keyword_scope=("not_a_real_field",),
			))

	def test_reviews_are_independent_from_overrides_and_can_be_cleared(self) -> None:
		reviews = load_reviews(self.repo_root)
		self.assertEqual(reviews, {})
		record = ReviewRecord(
			status="reviewed",
			reviewed_by="Zoe",
			reviewed_at="2026-08-20T12:00:00+00:00",
			notes="Base text is acceptable.",
		)
		save_review(self.repo_root, "/datum/language/common", record)
		self.assertEqual(load_reviews(self.repo_root)["/datum/language/common"], record)
		save_review(self.repo_root, "/datum/language/common", None)
		self.assertEqual(load_reviews(self.repo_root), {})

	def test_needs_attention_reviews_are_persisted(self) -> None:
		record = ReviewRecord(
			status="needs-attention",
			reviewed_by="Zoe",
			reviewed_at="2026-08-20T12:00:00+00:00",
			notes="The company reference needs a lore decision.",
		)
		save_review(self.repo_root, "/obj/item/radio", record)
		self.assertEqual(load_reviews(self.repo_root)["/obj/item/radio"], record)

	def test_group_creation_and_assignments_are_persisted(self) -> None:
		group = GroupRecord(
			id="frontier-cults",
			label="Frontier Cults",
			color="#f59e0b",
			keywords=("cult",),
			type_path_prefixes=(),
		)
		save_group(self.repo_root, group)
		save_group_assignments(self.repo_root, "/obj/item/relic", ("frontier-cults",))
		groups = load_groups(self.repo_root)
		self.assertEqual(groups.groups[-1], group)
		self.assertEqual(groups.assignments["/obj/item/relic"], ("frontier-cults",))

	def test_invalid_group_ids_are_rejected(self) -> None:
		with self.assertRaises(ValueError):
			save_group(self.repo_root, GroupRecord(
				id="Not A Slug",
				label="Invalid",
				color="#fff",
				keywords=(),
				type_path_prefixes=(),
			))


if __name__ == "__main__":
	unittest.main()

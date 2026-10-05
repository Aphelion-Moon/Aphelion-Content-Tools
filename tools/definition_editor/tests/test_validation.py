from __future__ import annotations

import unittest

from tools.definition_editor.models import AuthoringCatalog
from tools.definition_editor.validation import validate_candidate


def jobs(*titles: str) -> AuthoringCatalog:
	return AuthoringCatalog.model_validate({'schema_version': 1, 'analyzer_version': 'test', 'input_files': [], 'definitions': [
		{'kind': 'job', 'type_path': f'/datum/job/job_{index}', 'parent_type': '/datum/job', 'fields': [
			{'name': 'title', 'expression': f'"{title}"', 'value': title, 'owner_type': f'/datum/job/job_{index}'},
			{'name': 'config_tag', 'expression': f'"JOB_{index}"', 'value': f'JOB_{index}', 'owner_type': f'/datum/job/job_{index}'}
		]} for index, title in enumerate(titles)
	]})


class CandidateValidationTests(unittest.TestCase):
	def test_new_duplicate_title_is_blocking_even_for_retired_job(self) -> None:
		with self.assertRaisesRegex(ValueError, 'title'):
			validate_candidate(jobs('Engineer'), jobs('Engineer', 'Engineer'), {'/datum/job/job_1'})

	def test_unrelated_existing_duplicate_is_reported_not_new_failure(self) -> None:
		self.assertIsInstance(validate_candidate(jobs('Engineer', 'Engineer'), jobs('Engineer', 'Engineer', 'Medic'), {'/datum/job/job_2'}), list)

	def test_replacement_checks_aliases_against_other_titles(self) -> None:
		from tools.definition_editor.models import DefinitionField
		candidate = jobs('Engineer', 'Medic')
		candidate.definitions[1].fields.append(DefinitionField(name='alt_titles', owner_type='/datum/job/job_1', value=['Engineer']))
		with self.assertRaisesRegex(ValueError, 'alias|title'):
			validate_candidate(jobs('Engineer'), candidate, {'/datum/job/job_1'})

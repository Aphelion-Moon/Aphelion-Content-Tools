from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.definition_editor.models import DraftAction, EditorApplyRequest, EditorRun, SaveDraftRequest
from tools.definition_editor.service import EditorService, ValidatedCandidate
from tools.definition_editor.tests.test_authoring import catalog, draft
from webapp.game_changes import GameChangeSetService


class ReconciliationTests(unittest.TestCase):
	def test_browser_cannot_remove_an_applied_identity_or_clear_its_receipts(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			service = EditorService(root, root, GameChangeSetService(root))
			try:
				record = draft()
				record.applied_stage_ids = ['applied-stage']
				saved = service.drafts.save(record, expected_hash=None)
				changed = record.model_copy(deep=True)
				changed.applied_stage_ids = []
				changed.edits[0].type_path = '/datum/outfit/renamed'
				with self.assertRaisesRegex(ValueError, 'applied identit'):
					service.save(SaveDraftRequest(draft=changed, expected_record_hash=saved.record_hash))
				changed.edits[0].type_path = record.edits[0].type_path
				result = service.save(SaveDraftRequest(draft=changed, expected_record_hash=saved.record_hash))
				self.assertEqual(result.draft.applied_stage_ids, ['applied-stage'])
			finally:
				service.shutdown()

	def test_refresh_requires_review_and_preserves_desired_expression(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			service = EditorService(root, root, GameChangeSetService(root))
			try:
				base = catalog()
				with patch.object(service.catalogs, 'read', return_value=('fixture', base, 'revision')):
					saved = service.save(SaveDraftRequest(draft=draft()))
				self.assertTrue(saved.draft.source_hashes)
				changed = base.model_copy(deep=True)
				changed.definitions[1].fields[0].expression = '"External edit"'
				with patch.object(service.catalogs, 'read', return_value=('new', changed, 'revision')), patch.object(service.catalogs, 'verify', return_value=changed):
					proposal = service.rebase(DraftAction(kind='outfit', id=saved.draft.id, record_hash=saved.record_hash))
				self.assertIn('External edit', proposal.changes[0])
				self.assertEqual(proposal.draft.edits[0].fields['name'], '"Updated"')
				self.assertEqual(service.drafts.get('outfit', saved.draft.id).record_hash, saved.record_hash)
			finally:
				service.shutdown()

	def test_committed_apply_returns_receipt_when_only_the_editor_cache_write_fails(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			service = EditorService(root, root, GameChangeSetService(root))
			try:
				saved = service.drafts.save(draft(), expected_hash=None)
				service._stages['committed-stage'] = saved.record_hash
				with service._source_workspace(EditorRun(id='validated', operation='validate', status='ready')) as source:
					service._candidates[saved.record_hash] = ValidatedCandidate(saved.record_hash, 'fixture', 'revision', {}, source, {}, {})
				receipt = {'stage_id': 'committed-stage', 'base_revision': 'revision', 'paths': [], 'sha256': {}}
				with patch.object(service.catalogs, 'verify', return_value=catalog()), patch.object(service, '_verify_compilation'), patch.object(service.changes, 'apply', return_value=receipt), patch('tools.definition_editor.service.atomic_write', side_effect=OSError('cache disk full')), patch.object(service, 'index') as refresh:
					result = service.apply(EditorApplyRequest(kind=saved.draft.kind, id=saved.draft.id, record_hash=saved.record_hash, stage_id='committed-stage'))
				self.assertEqual(result['stage_id'], 'committed-stage')
				self.assertIn('cache disk full', str(result['refresh_warning']))
				refresh.assert_called_once()
				self.assertNotIn('committed-stage', service._stages)
				self.assertNotIn(saved.record_hash, service._candidates)
				self.assertFalse(source.exists())
			finally:
				service.shutdown()

	def test_apply_reserves_native_operations_until_its_source_cleanup_finishes(self) -> None:
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			service = EditorService(root, root, GameChangeSetService(root))
			saved = service.drafts.save(draft(), expected_hash=None)
			service._stages['stage'] = saved.record_hash
			service._candidates[saved.record_hash] = ValidatedCandidate(saved.record_hash, 'fixture', 'revision', {}, root, {}, {})
			entered, release = threading.Event(), threading.Event()
			failures = []
			def verify(*args):
				entered.set()
				if not release.wait(5):
					raise TimeoutError('test reservation timed out')
			def apply():
				try:
					service.apply(EditorApplyRequest(kind=saved.draft.kind, id=saved.draft.id, record_hash=saved.record_hash, stage_id='stage'))
				except Exception as exc:
					failures.append(exc)
			with patch.object(service.catalogs, 'verify', return_value=catalog()), patch.object(service, '_verify_compilation', side_effect=verify), patch.object(service.changes, 'apply', return_value={'stage_id': 'stage'}), patch.object(service, 'index'):
				thread = threading.Thread(target=apply)
				thread.start()
				try:
					self.assertTrue(entered.wait(5))
					with self.assertRaisesRegex(ValueError, 'already running'):
						service._start('render', lambda run, context: None)
				finally:
					release.set()
					thread.join(timeout=5)
					service.shutdown()
			self.assertFalse(failures)

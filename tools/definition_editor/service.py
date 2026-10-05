from __future__ import annotations

import hashlib
import logging
import secrets
import shutil
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from tools.lore_editor.write_coordinator import repository_write_lock
from webapp.game_changes import GameChangeSetService
from webapp.git_adapter import repository_revision
from webapp.json_storage import atomic_write, canonical_json_bytes
from webapp.store.metadata import store_root

from .catalog import Analyzer, CatalogStore, verify_inputs
from .models import (
	AuthoringCatalog,
	CatalogStatus,
	DefinitionDraft,
	DraftAction,
	EditorApplyRequest,
	EditorRun,
	EditorStage,
	PreviewRequest,
	RebaseProposal,
	SavedDraft,
	SaveDraftRequest,
)
from .preview import (
	build_candidate,
	byond_binary,
	copy_source,
	create_source_directory,
	run_preview,
	source_fingerprint,
)
from .process import Cancelled, RunContext
from .source import build_changes
from .storage import DraftStore
from .validation import validate_candidate


@dataclass
class ValidatedCandidate:
	record_hash: str
	catalog_id: str
	game_revision: str
	changes: dict[str, tuple[bytes | None, bytes]]
	source: Path
	receipt: dict[str, object]
	effective_flags: dict[str, str]


class EditorService:
	def __init__(self, root: Path, game: Path, changes: GameChangeSetService) -> None:
		self.root, self.game, self.changes = root, game, changes
		self.drafts = DraftStore(root)
		self.catalogs = CatalogStore(root, game)
		self.analyzer = Analyzer()
		self.cache = store_root(root) / 'definition-editor'
		self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='definition-editor')
		self._lock = threading.RLock()
		self._runs: dict[str, EditorRun] = {}
		self._cancel: dict[str, threading.Event] = {}
		self._candidates: dict[str, ValidatedCandidate] = {}
		self._stages: dict[str, str] = {}
		self._sources: set[Path] = set()
		self._busy = False

	def _release_source(self, source: Path, run: EditorRun | None = None) -> None:
		if source not in self._sources:
			return
		try:
			parent = (store_root(self.root) / 'dm').resolve()
			if source.resolve() != source or source.parent != parent:
				raise ValueError('Owned private source is no longer in its original cache location.')
			if source.exists():
				shutil.rmtree(source)
			self._sources.remove(source)
		except (OSError, ValueError) as exc:
			message = f'Could not remove owned private build directory {source}: {exc}'
			if run:
				run.diagnostics.append(message)
			logging.getLogger(__name__).warning(message)

	@contextmanager
	def _source_workspace(self, run: EditorRun) -> Iterator[Path]:
		source = create_source_directory(self.root)
		self._sources.add(source)
		try:
			yield source
		finally:
			if not any(candidate.source == source for candidate in self._candidates.values()):
				self._release_source(source, run)

	def _retain_candidate(self, candidate: ValidatedCandidate, run: EditorRun) -> None:
		identity = (candidate.receipt.get('draft_kind'), candidate.receipt.get('draft_id'))
		for key, old in list(self._candidates.items()):
			if key == candidate.record_hash or (old.receipt.get('draft_kind'), old.receipt.get('draft_id')) == identity:
				del self._candidates[key]
				self._release_source(old.source, run)
		# Keep two usable compilations for switching between linked editor drafts.
		# Older drafts remain canonical; their transient compilation can be repeated.
		while len(self._candidates) >= 2:
			old = self._candidates.pop(next(iter(self._candidates)))
			self._release_source(old.source, run)
		self._candidates[candidate.record_hash] = candidate

	def _analyze(self, source: Path, output: Path, context: RunContext) -> AuthoringCatalog:
		try:
			return self.analyzer.export(source, output, context)
		finally:
			# The typed catalog and immutable active snapshot own the result. Raw
			# command payloads can be hundreds of MB and are not run-log artifacts.
			try:
				output.unlink(missing_ok=True)
			except OSError as exc:
				logging.getLogger(__name__).warning('Could not remove transient analyzer output %s: %s', output, exc)

	def status(self) -> CatalogStatus:
		status = CatalogStatus()
		try:
			self.analyzer.executable()
			status.analyzer_available = True
		except (OSError, ValueError):
			pass
		try:
			byond_binary('dm.exe')
			status.byond_available = True
		except ValueError:
			status.byond_available = False
		try:
			catalog_id, _, revision = self.catalogs.read()
			status.catalog_id, status.game_revision = catalog_id, revision
			self.catalogs.observe(catalog_id)
			status.current = True
		except (OSError, ValueError) as exc:
			status.reason = str(exc)
		return status

	def runs(self) -> list[EditorRun]:
		with self._lock:
			return [run.model_copy(deep=True) for run in self._runs.values()]

	def _persist(self, run: EditorRun) -> None:
		atomic_write(self.cache / 'runs' / run.id / 'status.json', canonical_json_bytes(run.model_dump()))

	def _start(self, operation: str, action: Callable[[EditorRun, RunContext], None], draft_hash: str | None = None) -> EditorRun:
		with self._lock:
			if self._busy:
				raise ValueError('An authoring operation is already running. Stop it or wait for completion.')
			self._busy = True
			if len(self._runs) >= 40:
				oldest = next(iter(self._runs))
				self._runs.pop(oldest)
				self._cancel.pop(oldest, None)
			run = EditorRun(id=secrets.token_hex(12), operation=operation, status='queued', draft_hash=draft_hash)
			cancel = threading.Event()
			self._runs[run.id], self._cancel[run.id] = run, cancel
			try:
				self._persist(run)
			except Exception:
				self._busy = False
				self._runs.pop(run.id)
				self._cancel.pop(run.id)
				raise
			def execute() -> None:
				context = RunContext(self.cache / 'runs' / run.id, cancel)
				try:
					run.status = 'running'
					self._persist(run)
					action(run, context)
					if run.status == 'running':
						run.status = 'ready'
						run.message = run.message or 'Completed.'
				except Cancelled:
					run.status, run.message = 'cancelled', 'Operation stopped.'
				except Exception as exc:
					run.status, run.message = 'failed', str(exc)
				finally:
					try:
						self._persist(run)
					finally:
						with self._lock:
							self._busy = False
			try:
				self._executor.submit(execute)
			except Exception:
				self._busy = False
				run.status, run.message = 'failed', 'The authoring worker could not be started.'
				raise
			return run.model_copy(deep=True)

	def index(self, applied: tuple[SavedDraft, dict[str, object], AuthoringCatalog, dict[str, str]] | None = None) -> EditorRun:
		def action(run: EditorRun, context: RunContext) -> None:
			run.message = 'Analyzing job, outfit, item, and trim source.'
			self._persist(run)
			revision = repository_revision(self.game)
			catalog = self._analyze(self.game, context.directory / 'catalog.json', context)
			run.message = 'Verifying source inputs and activating the catalog.'
			self._persist(run)
			catalog_id = self.catalogs.publish(catalog, revision)
			run.message = f'Indexed {len(catalog.definitions)} definitions.'
			if applied:
				saved, receipt, before, flags = applied
				outputs = receipt['sha256']
				assert isinstance(outputs, dict)
				expected = {item.path: item.sha256 for item in before.input_files} | outputs
				current = {item.path: item.sha256 for item in catalog.input_files}
				if any(current.get(path) != digest for path, digest in expected.items()):
					raise ValueError('Applied source was refreshed, but concurrent source edits prevent draft reconciliation. Review and rebase explicitly.')
				updated = saved.draft.model_copy(deep=True)
				updated.catalog_id = catalog_id
				updated.applied_stage_ids.append(str(receipt['stage_id']))
				for edit in updated.edits:
					edit.reference_ids = []
					if edit.type_path in flags and edit.operation == 'replace' and edit.old_job_selection == 'retire':
						edit.fields.setdefault('job_flags', flags[edit.type_path])
				self._bind(updated, catalog)
				self.drafts.save(updated, expected_hash=saved.record_hash)
				run.message += ' Applied draft reconciled against the receipt.'
		return self._start('catalog', action)

	@staticmethod
	def _bind(draft: DefinitionDraft, catalog: AuthoringCatalog) -> None:
		paths = {path for edit in draft.edits for path in (edit.type_path, edit.source_type, edit.parent_type) if path}
		draft.baseline = [item.model_copy(deep=True) for item in catalog.definitions if item.type_path in paths]
		draft.source_hashes = {span.path: span.sha256 for item in draft.baseline for span in [item.source, *(field.source for field in item.fields), *(proc.source for proc in item.procedures)] if span}

	def save(self, request: SaveDraftRequest) -> SavedDraft:
		with repository_write_lock(self.root):
			return self._save(request)

	def _save(self, request: SaveDraftRequest) -> SavedDraft:
		draft = request.draft.model_copy(deep=True)
		try:
			current = self.drafts.get(draft.kind, draft.id)
		except FileNotFoundError:
			current = None
		if current and current.draft.applied_stage_ids:
			def identities(record: DefinitionDraft) -> set[tuple[str, str, str | None, str]]:
				return {(edit.kind, edit.operation, edit.source_type, edit.type_path) for edit in record.edits}
			if not identities(current.draft) <= identities(draft):
				raise ValueError('Previously applied identities must remain in their owning draft. Use an explicit replacement to introduce a different identity.')
		# Receipts are backend-owned; browser input cannot erase or invent application history.
		draft.applied_stage_ids = list(current.draft.applied_stage_ids) if current else []
		if not draft.baseline:
			try:
				catalog_id, catalog, _ = self.catalogs.read()
				if catalog_id == draft.catalog_id:
					self._bind(draft, catalog)
			except ValueError:
				pass  # Offline authoring remains available without a derived catalog.
		return self.drafts.save(draft, expected_hash=request.expected_record_hash)

	def rebase(self, request: DraftAction) -> RebaseProposal:
		saved = self._saved(request)
		catalog_id, catalog, _ = self.catalogs.read()
		self.catalogs.verify(catalog_id)
		current = {item.type_path: item for item in catalog.definitions}
		changes = []
		for old in saved.draft.baseline:
			new = current.get(old.type_path)
			if new is None:
				changes.append(f'{old.type_path}: definition removed.')
				continue
			old_fields = {field.name: field.expression for field in old.fields}
			new_fields = {field.name: field.expression for field in new.fields}
			for name in sorted(old_fields.keys() | new_fields.keys()):
				if old_fields.get(name) != new_fields.get(name):
					changes.append(f'{old.type_path}.{name}: {old_fields.get(name)} → {new_fields.get(name)}')
			if [(proc.name, proc.text) for proc in old.procedures] != [(proc.name, proc.text) for proc in new.procedures]:
				changes.append(f'{old.type_path}: procedure source changed; inspect the current source.')
		updated = saved.draft.model_copy(deep=True)
		updated.catalog_id = catalog_id
		if any(edit.reference_ids for edit in updated.edits):
			changes.append('Reference selections cleared: select verified occurrences from the new snapshot.')
		for edit in updated.edits:
			edit.reference_ids = []
		self._bind(updated, catalog)
		return RebaseProposal(draft=updated, expected_record_hash=saved.record_hash, changes=changes or ['The inspected values are unchanged. The source snapshot binding will be updated.'])

	def _saved(self, request: DraftAction) -> SavedDraft:
		saved = self.drafts.get(request.kind, request.id)
		if saved.record_hash != request.record_hash:
			raise ValueError('The saved draft changed. Reload it before continuing.')
		return saved

	def validate(self, request: DraftAction, *, compile_game: bool = True) -> EditorRun:
		saved = self._saved(request)
		def action(run: EditorRun, context: RunContext) -> None:
			base = self.catalogs.verify(saved.draft.catalog_id)
			revision = repository_revision(self.game)
			changes = build_changes(self.game, base, saved.draft)
			if not changes:
				raise ValueError('The draft has no source changes to validate.')
			with self._source_workspace(run) as source:
				source_hash = copy_source(self.game, source, context, base.input_files, (proposed for _, proposed in changes.values()))
				self.catalogs.verify(saved.draft.catalog_id)
				for relative, (expected, proposed) in changes.items():
					path = source / relative
					if (path.read_bytes() if path.is_file() else None) != expected:
						raise ValueError('Source changed while creating the candidate snapshot.')
					atomic_write(path, proposed)
				candidate = self._analyze(source, context.directory / 'candidate.json', context)
				private_inputs = {path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in source.rglob('*') if path.is_file()}
				kinds = {item.type_path: item.kind for item in candidate.definitions}
				if any(kinds.get(edit.type_path) != edit.kind for edit in saved.draft.edits):
					raise ValueError('An authored definition has a parent outside its declared job, outfit, or trim hierarchy.')
				run.diagnostics = validate_candidate(base, candidate, {edit.type_path for edit in saved.draft.edits})
				run.effective = [item.model_copy(update={'procedures': [], 'references': []}) for item in candidate.definitions if item.type_path in {edit.type_path for edit in saved.draft.edits}]
				self._persist(run)
				if not compile_game:
					self.catalogs.verify(saved.draft.catalog_id)
					self._saved(request)
					run.message = 'Draft reparsed. Effective values reflect this exact saved source; compilation has not run.'
					return
				build = build_candidate(source, context)
				verify_inputs(source, candidate)
				self._verify_private_inputs(source, private_inputs)
				self.catalogs.verify(saved.draft.catalog_id)
				self._saved(request)
				receipt: dict[str, object] = {'schema_version': 1, 'draft_id': saved.draft.id, 'draft_kind': saved.draft.kind, 'record_hash': saved.record_hash, 'catalog_id': saved.draft.catalog_id, 'game_revision': revision, 'source_sha256': source_hash, 'build': build,
					'private_inputs': private_inputs, 'analyzer_sha256': hashlib.sha256(self.analyzer.executable().read_bytes()).hexdigest(), 'outputs': {name: hashlib.sha256(content).hexdigest() for name, (_, content) in changes.items()}}
				atomic_write(context.directory / 'validation.json', canonical_json_bytes(receipt))
				flags = {item.type_path: field.expression for item in candidate.definitions for field in item.fields if item.type_path in {edit.type_path for edit in saved.draft.edits} and field.name == 'job_flags' and field.expression is not None}
				self._retain_candidate(ValidatedCandidate(saved.record_hash, saved.draft.catalog_id, revision, changes, source, receipt, flags), run)
				run.message = 'The exact candidate passed source analysis and the maintained game build.'
		return self._start('validate' if compile_game else 'analyze', action, saved.record_hash)

	def _verify_compilation(self, candidate: ValidatedCandidate, base: AuthoringCatalog) -> None:
		if source_fingerprint(self.game, base.input_files, (proposed for _, proposed in candidate.changes.values())) != candidate.receipt['source_sha256']:
			raise ValueError('Source, assets, or build inputs differ from the compiled snapshot; validate again.')
		build = candidate.receipt['build']
		if not isinstance(build, dict) or hashlib.sha256(byond_binary('dm.exe').read_bytes()).hexdigest() != build.get('compiler_sha256') or hashlib.sha256(self.analyzer.executable().read_bytes()).hexdigest() != candidate.receipt['analyzer_sha256']:
			raise ValueError('The compiler or analyzer changed after validation; validate again.')

	@staticmethod
	def _verify_private_inputs(source: Path, inputs: dict[str, str]) -> None:
		from webapp.path_safety import resolve_repo_path
		for name, digest in inputs.items():
			path = resolve_repo_path(source, Path(name))
			if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
				raise ValueError('Private candidate source changed after validation; validate again.')

	def prepare(self, request: DraftAction) -> EditorStage:
		with repository_write_lock(self.root):
			saved = self._saved(request)
			candidate = self._candidates.get(saved.record_hash)
			if candidate is None:
				raise ValueError('Validate this exact saved draft successfully before preparing a change set.')
			base = self.catalogs.verify(saved.draft.catalog_id)
			self._verify_compilation(candidate, base)
			current = build_changes(self.game, base, saved.draft)
			if current != candidate.changes or repository_revision(self.game) != candidate.game_revision:
				raise ValueError('Candidate inputs changed after compilation; validate again.')
			stage = self.changes.prepare(current, allowed_paths=frozenset(current))
			self._stages[stage.stage_id] = saved.record_hash
			report = []
			if any(edit.operation == 'replace' for edit in saved.draft.edits):
				report.append('Only selected exact source references will be migrated. Dynamic/macro/map references, player preferences, bans, and operator configuration require separate review.')
			return EditorStage(**asdict(stage), compatibility_report=report)

	def apply(self, request: EditorApplyRequest) -> dict[str, object]:
		with self._lock:
			if self._busy:
				raise ValueError('Stop the native preview or wait for the authoring operation before applying.')
			self._busy = True
		try:
			with repository_write_lock(self.root):
				saved = self._saved(request)
				if self._stages.get(request.stage_id) != saved.record_hash:
					raise ValueError('The prepared change set does not belong to this validated draft.')
				base = self.catalogs.verify(saved.draft.catalog_id)
				candidate = self._candidates.get(saved.record_hash)
				if candidate is None:
					raise ValueError('The compiled candidate is no longer available; validate again.')
				self._verify_compilation(candidate, base)
				receipt = self.changes.apply(request.stage_id)
				del self._stages[request.stage_id]
				try:
					atomic_write(self.cache / 'receipts' / f'{request.stage_id}.json', canonical_json_bytes({**receipt, 'draft_id': saved.draft.id, 'record_hash': saved.record_hash}))
				except OSError as exc:
					# The game transaction already committed its durable receipt. A secondary
					# cache failure must not report that application failed or invite a retry.
					receipt['refresh_warning'] = f'Applied successfully; the editor receipt cache could not be written: {exc}'
				self._candidates.pop(saved.record_hash, None)
				self._release_source(candidate.source)
		finally:
			with self._lock:
				self._busy = False
		# Source currentness is invalid until the explicit refresh finishes. Never relabel
		# the pre-apply catalog as current because HEAD stayed unchanged.
		try:
			self.index((saved, receipt, base, candidate.effective_flags))
		except (OSError, ValueError) as exc:
			receipt['refresh_warning'] = ' '.join(filter(None, [str(receipt.get('refresh_warning', '')), str(exc)]))
		return receipt

	def preview(self, request: PreviewRequest) -> EditorRun:
		saved = self._saved(request)
		candidate = self._candidates.get(saved.record_hash)
		if candidate is None:
			raise ValueError('Validate this exact draft before starting a native preview.')
		if request.type_path not in {edit.type_path for edit in saved.draft.edits if edit.kind in ('job', 'outfit')}:
			raise ValueError('Preview target must belong to the validated draft.')
		base = self.catalogs.verify(saved.draft.catalog_id)
		self._verify_compilation(candidate, base)
		def action(run: EditorRun, context: RunContext) -> None:
			# Preview compilation changes artifacts only; production validation remains bound
			# to its separate compiler/output receipt and unchanged candidate source bytes.
			inputs = candidate.receipt.get('private_inputs')
			if not isinstance(inputs, dict):
				raise ValueError('The compiled candidate has no private source receipt; validate again.')
			self._verify_private_inputs(candidate.source, inputs)
			target_kind = next(edit.kind for edit in saved.draft.edits if edit.type_path == request.type_path)
			run_preview(candidate.source, request, context, run, lambda: self._persist(run), target_kind=target_kind)
		return self._start(request.mode, action, saved.record_hash)

	def artifact(self, run_id: str, image_index: int) -> Path:
		run = self._runs.get(run_id)
		if run is None or run.draft_hash is None or not 0 <= image_index < len(run.images):
			raise ValueError('Unknown preview image.')
		root = (self.cache / 'runs' / run.id).resolve()
		path = (root / run.images[image_index]).resolve()
		if not path.is_relative_to(root / 'images') or path.suffix != '.png':
			raise ValueError('Invalid preview artifact path.')
		return path

	def log(self, run_id: str) -> str:
		if run_id not in self._runs:
			raise ValueError('Unknown authoring operation.')
		path = self.cache / 'runs' / run_id / 'run.log'
		return path.read_bytes()[:2_000_000].decode('utf-8', errors='replace') if path.is_file() else 'The command is running. Its bounded log will be available when it finishes.'

	def stop(self, run_id: str) -> None:
		with self._lock:
			if run_id not in self._cancel:
				raise ValueError('Unknown authoring operation.')
			self._cancel[run_id].set()

	def shutdown(self) -> None:
		for cancel in self._cancel.values():
			cancel.set()
		self._executor.shutdown(wait=True, cancel_futures=True)
		self._candidates.clear()
		for source in tuple(self._sources):
			self._release_source(source)

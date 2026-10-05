from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.lore_editor.write_coordinator import RecordConflict, repository_write_lock
from webapp.json_storage import atomic_write, canonical_json_bytes, stable_record_filename
from webapp.path_safety import resolve_repo_path

from .models import DefinitionDraft, EditorKind, SavedDraft


class DraftStore:
	def __init__(self, root: Path) -> None:
		self.root = root.resolve()

	def _path(self, kind: EditorKind, record_id: str) -> Path:
		if kind not in ('job', 'outfit'):
			raise ValueError('Unknown editor kind.')
		return resolve_repo_path(self.root, Path(f'tools/{kind}_editor/content') / stable_record_filename(record_id))

	def get(self, kind: EditorKind, record_id: str) -> SavedDraft:
		path = self._path(kind, record_id)
		content = path.read_bytes()
		draft = DefinitionDraft.model_validate_json(content)
		if draft.kind != kind or draft.id != record_id:
			raise ValueError('Canonical draft identity does not match its filename.')
		return SavedDraft(draft=draft, record_hash=hashlib.sha256(content).hexdigest())

	def list(self, kind: EditorKind) -> list[SavedDraft]:
		root = self._path(kind, 'placeholder').parent
		return [self.get(kind, path.stem) for path in sorted(root.glob('*.json'))]

	def save(self, draft: DefinitionDraft, *, expected_hash: str | None) -> SavedDraft:
		with repository_write_lock(self.root):
			path = self._path(draft.kind, draft.id)
			current = self.get(draft.kind, draft.id) if path.exists() else None
			current_hash = current.record_hash if current else None
			if current_hash != expected_hash:
				raise RecordConflict(record_id=draft.id, expected_hash=expected_hash, current_hash=current_hash, base=None, current=current.draft.model_dump() if current else None, proposed=draft.model_dump())
			atomic_write(path, canonical_json_bytes(draft.model_dump()))
			return self.get(draft.kind, draft.id)

	def revision(self) -> str:
		rows = [(kind, record.draft.id, record.record_hash) for kind in ('job', 'outfit') for record in self.list(kind)]
		return hashlib.sha256(json.dumps(rows).encode()).hexdigest()

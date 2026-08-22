from __future__ import annotations

import os
from threading import Lock

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

_model = None
_model_lock = Lock()
_model_load_failed = False


def _model_cache_dir() -> str | None:
	local_app_data = os.environ.get("LOCALAPPDATA")
	if not local_app_data:
		return None
	return os.path.join(local_app_data, "AphelionContentTools", "models")


def _load_model():
	global _model, _model_load_failed
	if _model is not None or _model_load_failed:
		return _model
	with _model_lock:
		if _model is not None or _model_load_failed:
			return _model
		try:
			from fastembed import TextEmbedding
			_model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME, cache_dir=_model_cache_dir())
		except Exception:
			_model_load_failed = True
			_model = None
	return _model


def embeddings_available() -> bool:
	return _load_model() is not None


def embed_texts(texts: list[str]) -> list[list[float]]:
	"""Return one embedding vector per input text, or an all-zero vector per text if the model is
	unavailable (offline, declined download, missing dependency) -- callers never have to special-case
	this: a zero vector simply never ranks highly in cosine/vector search, so keyword search alone still
	works."""
	model = _load_model()
	if model is None:
		return [[0.0] * EMBEDDING_DIM for _ in texts]
	# `parallel=0` (data-parallel encoding across worker processes) was tried and reverted: fastembed
	# implements it with real `multiprocessing` workers, which on Windows require "spawn" semantics --
	# the *calling* entry script must be `if __name__ == "__main__":`-guarded for this to work at all,
	# and a naive script (confirmed by direct test, 2026-08-22) crashes repeatedly instead of embedding
	# anything. That's real fragility for uncertain gain given the actual fix for the slow-refresh problem
	# is content-hash diffing (see webapp/store/db.py's sync_snapshot) so full re-embeds become rare, not
	# faster embeds on every call. Single-process default threading only.
	return [list(vector) for vector in model.embed(list(texts))]

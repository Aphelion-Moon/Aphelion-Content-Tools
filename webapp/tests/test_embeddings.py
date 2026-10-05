from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from webapp.store import embeddings


class EmbeddingModelCacheTests(unittest.TestCase):
	def test_frozen_sidecar_uses_bundled_model_cache(self) -> None:
		bundle_root = Path("C:/Aphelion/_internal")
		with patch.object(embeddings.sys, "frozen", True, create=True), patch.object(
			embeddings.sys,
			"_MEIPASS",
			str(bundle_root),
			create=True,
		):
			cache_dir = embeddings._model_cache_dir()

		self.assertEqual(cache_dir, str(bundle_root / "models"))

	def test_embedding_uses_a_writer_desktop_sized_native_batch(self) -> None:
		model = Mock()
		model.embed.return_value = ([float(index)] * embeddings.EMBEDDING_DIM for index in range(2))
		with patch.object(embeddings, "_load_model", return_value=model):
			vectors = embeddings.embed_texts(["alpha", "bravo"])

		model.embed.assert_called_once_with(["alpha", "bravo"], batch_size=embeddings.EMBEDDING_BATCH_SIZE)
		self.assertEqual(len(vectors), 2)


if __name__ == "__main__":
	unittest.main()

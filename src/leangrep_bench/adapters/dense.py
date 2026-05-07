from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from leangrep_bench.adapters.base import (
    RetrievalAdapter,
    RetrievalResult,
    indexable_text,
)
from leangrep_bench.corpus.model import NormalizedDeclaration
from leangrep_bench.verify.model import BenchmarkContext

logger = logging.getLogger(__name__)


class DenseAdapter(RetrievalAdapter):
    """Sentence-transformer dense retrieval over the same indexable text the
    BM25 adapter sees. Index is cached on disk keyed by (model_name, content
    hash of the indexed strings).
    """

    def __init__(
        self,
        *,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        cache_dir: Path = Path(".cache/dense"),
        batch_size: int = 64,
        device: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.batch_size = batch_size
        self.device = device
        # Adapter name is short and stable for the registry.
        short = model_name.split("/")[-1]
        self.name = f"dense:{short}"

        self._embeddings: npt.NDArray[np.float32] | None = None
        self._names: list[str] = []
        self._model: Any = None  # SentenceTransformer, lazily loaded.

    def _ensure_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def _cache_paths(self, corpus_hash: str) -> tuple[Path, Path]:
        slug = self.model_name.replace("/", "_")
        base = self.cache_dir / slug / corpus_hash
        return base.with_suffix(".npy"), base.with_suffix(".names.json")

    def index(self, corpus: Iterable[NormalizedDeclaration]) -> None:
        names: list[str] = []
        texts: list[str] = []
        for decl in corpus:
            names.append(decl.qualified_name)
            texts.append(indexable_text(decl))

        self._names = names
        h = hashlib.sha256()
        # Hash both names and texts so any drift in either field invalidates.
        for n, t in zip(names, texts, strict=True):
            h.update(n.encode("utf-8"))
            h.update(b"\x00")
            h.update(t.encode("utf-8"))
            h.update(b"\x01")
        corpus_hash = h.hexdigest()[:16]

        emb_path, names_path = self._cache_paths(corpus_hash)
        if emb_path.exists() and names_path.exists():
            try:
                cached_names = json.loads(names_path.read_text(encoding="utf-8"))
                if cached_names == names:
                    self._embeddings = np.load(emb_path)
                    logger.info(
                        "loaded cached dense index from %s (%d docs)",
                        emb_path,
                        len(names),
                    )
                    return
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("dense cache load failed (%s); re-encoding", e)

        model = self._ensure_model()
        logger.info("encoding %d docs with %s", len(texts), self.model_name)
        embeddings = model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        embeddings = np.asarray(embeddings, dtype=np.float32)
        emb_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(emb_path, embeddings)
        names_path.write_text(json.dumps(names), encoding="utf-8")
        self._embeddings = embeddings

    def search(
        self,
        query: str,
        context: BenchmarkContext | None = None,
        k: int = 10,
    ) -> list[RetrievalResult]:
        del context
        if self._embeddings is None:
            raise RuntimeError("DenseAdapter.search called before index")
        model = self._ensure_model()
        q_emb = model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        q_vec: npt.NDArray[np.float32] = np.asarray(q_emb, dtype=np.float32)[0]
        # Cosine sim = dot product since both are unit-normalized.
        emb = self._embeddings
        scores: npt.NDArray[np.float32] = emb @ q_vec
        order = np.argsort(-scores)[:k]
        return [
            RetrievalResult(name=self._names[int(i)], score=float(scores[int(i)]))
            for i in order
        ]

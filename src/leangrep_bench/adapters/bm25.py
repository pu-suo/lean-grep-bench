from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

from leangrep_bench.adapters.base import (
    RetrievalAdapter,
    RetrievalResult,
    indexable_text,
)
from leangrep_bench.corpus.model import NormalizedDeclaration
from leangrep_bench.verify.model import BenchmarkContext

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split on non-word chars, drop short
    tokens. Same tokenizer used for queries and corpus documents.
    """
    out: list[str] = []
    for tok in _TOKEN_RE.findall(text.lower()):
        if len(tok) >= 2:
            out.append(tok)
    return out


class BM25Adapter(RetrievalAdapter):
    name = "bm25"

    def __init__(self) -> None:
        self._bm25: Any = None
        self._names: list[str] = []

    def index(self, corpus: Iterable[NormalizedDeclaration]) -> None:
        names: list[str] = []
        tokenized: list[list[str]] = []
        for decl in corpus:
            names.append(decl.qualified_name)
            tokenized.append(tokenize(indexable_text(decl)))
        self._names = names
        self._bm25 = BM25Okapi(tokenized)

    def search(
        self,
        query: str,
        context: BenchmarkContext | None = None,
        k: int = 10,
    ) -> list[RetrievalResult]:
        del context  # baseline doesn't use context
        if self._bm25 is None:
            raise RuntimeError("BM25Adapter.search called before index")
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        raw_scores = self._bm25.get_scores(q_tokens)
        scores: list[float] = [float(s) for s in raw_scores]
        idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        out: list[RetrievalResult] = []
        for i in idx[:k]:
            out.append(RetrievalResult(name=self._names[i], score=scores[i]))
        return out

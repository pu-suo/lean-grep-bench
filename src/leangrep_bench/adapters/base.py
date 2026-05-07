from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict

from leangrep_bench.corpus.model import NormalizedDeclaration
from leangrep_bench.verify.model import BenchmarkContext


class RetrievalResult(BaseModel):
    name: str
    score: float
    extra: dict[str, Any] = {}

    model_config = ConfigDict(extra="ignore")


class RetrievalAdapter(ABC):
    """Common interface every retrieval system implements."""

    name: str = "base"

    @abstractmethod
    def index(self, corpus: Iterable[NormalizedDeclaration]) -> None:
        """Build any indexes the adapter needs. Called once per run.
        For external API adapters, this is a no-op.
        """

    @abstractmethod
    def search(
        self,
        query: str,
        context: BenchmarkContext | None = None,
        k: int = 10,
    ) -> list[RetrievalResult]:
        """Return up to k ranked results."""


def indexable_text(decl: NormalizedDeclaration) -> str:
    """Concatenation used by both the BM25 and dense baselines so the only
    variable between them is the retrieval method, not the indexed string.
    """
    parts: list[str] = [decl.qualified_name]
    if decl.signature:
        parts.append(decl.signature)
    if decl.docstring:
        parts.append(decl.docstring)
    return "\n".join(parts)

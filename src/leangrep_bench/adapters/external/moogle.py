from __future__ import annotations

from collections.abc import Iterable

from leangrep_bench.adapters.base import RetrievalAdapter, RetrievalResult
from leangrep_bench.adapters.external.base import AdapterUnavailable
from leangrep_bench.corpus.model import NormalizedDeclaration
from leangrep_bench.verify.model import BenchmarkContext


class MoogleAdapter(RetrievalAdapter):
    """Moogle has no public API as of v1; this adapter is intentionally
    unavailable. If a stable endpoint becomes available, fill in the URL
    handling like the other external adapters and remove the raise.
    """

    name = "moogle"

    def __init__(self) -> None:
        raise AdapterUnavailable("Moogle has no public API; adapter not implemented.")

    def index(self, corpus: Iterable[NormalizedDeclaration]) -> None:
        raise AdapterUnavailable("Moogle has no public API")

    def search(
        self,
        query: str,
        context: BenchmarkContext | None = None,
        k: int = 10,
    ) -> list[RetrievalResult]:
        del query, context, k
        raise AdapterUnavailable("Moogle has no public API")

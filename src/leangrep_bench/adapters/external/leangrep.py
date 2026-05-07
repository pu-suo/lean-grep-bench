from __future__ import annotations

import os
from collections.abc import Iterable

from leangrep_bench.adapters.base import RetrievalAdapter, RetrievalResult
from leangrep_bench.adapters.external.base import AdapterUnavailable
from leangrep_bench.corpus.model import NormalizedDeclaration
from leangrep_bench.verify.model import BenchmarkContext


class LeanGrepAdapter(RetrievalAdapter):
    """Stub for the operator's lean-grep system.

    The real adapter will speak to whatever endpoint or library API the
    finished lean-grep exposes; for now, this just raises AdapterUnavailable
    unless ``LEANGREP_URL`` is set, in which case it prints a clear "not
    implemented" message to make the gap visible. The eval runner treats
    AdapterUnavailable as N/A for this adapter rather than crashing.
    """

    name = "lean_grep"

    def __init__(self) -> None:
        if not os.environ.get("LEANGREP_URL"):
            raise AdapterUnavailable(
                "lean-grep adapter is a stub: implement against the real "
                "endpoint when available. Set LEANGREP_URL to silence."
            )
        # Reaching here would mean URL is set but we still don't know its API.
        raise AdapterUnavailable(
            "lean-grep adapter not yet wired up to an HTTP/library API."
        )

    def index(self, corpus: Iterable[NormalizedDeclaration]) -> None:
        raise AdapterUnavailable("lean-grep adapter not implemented")

    def search(
        self,
        query: str,
        context: BenchmarkContext | None = None,
        k: int = 10,
    ) -> list[RetrievalResult]:
        del query, context, k
        raise AdapterUnavailable("lean-grep adapter not implemented")

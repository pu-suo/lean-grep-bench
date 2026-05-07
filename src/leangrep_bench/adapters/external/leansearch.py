from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import httpx

from leangrep_bench.adapters.base import RetrievalAdapter, RetrievalResult
from leangrep_bench.adapters.external.base import HTTPQueryCache
from leangrep_bench.corpus.model import NormalizedDeclaration
from leangrep_bench.verify.model import BenchmarkContext

logger = logging.getLogger(__name__)

# Default endpoint pattern. Override via constructor or LEANSEARCH_URL env var.
# leansearch.net documents a JSON API; the operator should pin the exact URL
# they're benchmarking against.
_DEFAULT_URL = "https://leansearch.net/api/search"


class LeanSearchAdapter(RetrievalAdapter):
    name = "leansearch"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        cache_dir: Path = Path(".cache/external/leansearch"),
        timeout_s: float = 20.0,
        rate_limit_s: float = 0.5,
        results_field: str = "results",
        name_field: str = "formal_name",
    ) -> None:
        env_url = os.environ.get("LEANSEARCH_URL")
        self.base_url = base_url or env_url or _DEFAULT_URL
        self.cache = HTTPQueryCache(cache_dir=cache_dir)
        self.timeout_s = timeout_s
        self.rate_limit_s = rate_limit_s
        self.results_field = results_field
        self.name_field = name_field
        self._last_call_t = 0.0
        self._lock = threading.Lock()
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout_s)
        return self._client

    def _fetch(self, query: str) -> str:
        with self._lock:
            elapsed = time.monotonic() - self._last_call_t
            if elapsed < self.rate_limit_s:
                time.sleep(self.rate_limit_s - elapsed)
            self._last_call_t = time.monotonic()

        client = self._get_client()
        try:
            r = client.get(self.base_url, params={"query": query, "num_results": 10})
            r.raise_for_status()
            return r.text
        except httpx.HTTPError as e:
            logger.warning("leansearch request failed for %r: %s", query, e)
            return ""

    def index(self, corpus: Iterable[NormalizedDeclaration]) -> None:
        # Remote service indexes itself; consume the iterator to satisfy the
        # interface and so the runner can time index() consistently.
        for _ in corpus:
            pass

    def search(
        self,
        query: str,
        context: BenchmarkContext | None = None,
        k: int = 10,
    ) -> list[RetrievalResult]:
        del context
        if not query.strip():
            return []
        text = self.cache.get_or_fetch(
            f"leansearch::{self.base_url}::{query}",
            lambda: self._fetch(query),
        )
        return self._parse(text, k=k)

    def _parse(self, text: str, *, k: int) -> list[RetrievalResult]:
        if not text:
            return []
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("leansearch returned non-JSON; treating as empty")
            return []
        return _extract_results(
            payload,
            results_field=self.results_field,
            name_field=self.name_field,
            k=k,
        )


def _extract_results(
    payload: Any,
    *,
    results_field: str,
    name_field: str,
    k: int,
) -> list[RetrievalResult]:
    """Pull a ranked list of declaration names out of the JSON payload.

    Tolerant: payload may be a list of objects, a dict with ``results``, or a
    dict with another results-bearing field.
    """
    items: list[Any] = []
    if isinstance(payload, list):
        items = list(payload)  # type: ignore[arg-type]
    elif isinstance(payload, dict):
        for candidate in (results_field, "results", "matches", "data", "items"):
            v: Any = payload.get(candidate)  # type: ignore[arg-type]
            if isinstance(v, list):
                items = list(v)  # type: ignore[arg-type]
                break
    out: list[RetrievalResult] = []
    for i, it in enumerate(items[:k]):
        name = _pick_name(it, name_field)
        if not name:
            continue
        # Use 1/(rank+1) as a synthetic score (higher = better).
        out.append(RetrievalResult(name=name, score=1.0 / (i + 1)))
    return out


def _pick_name(item: Any, name_field: str) -> str | None:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return None
    for candidate in (name_field, "formal_name", "name", "qualified_name", "decl"):
        v: Any = item.get(candidate)  # type: ignore[arg-type]
        if isinstance(v, str) and v:
            return v
    return None

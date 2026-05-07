from __future__ import annotations

import logging
import os
import re
import threading
import time
from collections.abc import Iterable
from html.parser import HTMLParser
from pathlib import Path

import httpx

from leangrep_bench.adapters.base import RetrievalAdapter, RetrievalResult
from leangrep_bench.adapters.external.base import (
    AdapterUnavailable,
    HTTPQueryCache,
)
from leangrep_bench.corpus.model import NormalizedDeclaration
from leangrep_bench.verify.model import BenchmarkContext

logger = logging.getLogger(__name__)

# Lean Finder doesn't have a documented public API URL the operator
# pre-shared; pass via constructor or LEANFINDER_URL env var.
_LEANFINDER_DEFAULT_URL = os.environ.get("LEANFINDER_URL", "")


class _ResultExtractor(HTMLParser):
    """Pull plausible declaration-name strings out of an HTML response.

    Heuristic: any element that contains a string matching a Lean
    qualified-name pattern is treated as a candidate. Order in document is
    treated as rank order.
    """

    _NAME_RE = re.compile(
        r"\b[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)+\b"
    )

    def __init__(self) -> None:
        super().__init__()
        self.candidates: list[str] = []
        self._seen: set[str] = set()
        self._in_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._in_script = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._in_script = False

    def handle_data(self, data: str) -> None:
        if self._in_script:
            return
        for m in self._NAME_RE.finditer(data):
            name = m.group(0)
            if name not in self._seen:
                self._seen.add(name)
                self.candidates.append(name)


class LeanFinderAdapter(RetrievalAdapter):
    name = "lean_finder"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        query_param: str = "query",
        cache_dir: Path = Path(".cache/external/leanfinder"),
        timeout_s: float = 30.0,
        rate_limit_s: float = 1.0,
    ) -> None:
        env_url = os.environ.get("LEANFINDER_URL", "")
        self.base_url = base_url or env_url or _LEANFINDER_DEFAULT_URL
        if not self.base_url:
            raise AdapterUnavailable(
                "Lean Finder URL not configured. Set --leanfinder-url or "
                "LEANFINDER_URL env var to the public endpoint."
            )
        self.query_param = query_param
        self.cache = HTTPQueryCache(cache_dir=cache_dir)
        self.timeout_s = timeout_s
        self.rate_limit_s = rate_limit_s
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
        try:
            r = self._get_client().get(
                self.base_url, params={self.query_param: query}
            )
            r.raise_for_status()
            return r.text
        except httpx.HTTPError as e:
            logger.warning("leanfinder request failed for %r: %s", query, e)
            return ""

    def index(self, corpus: Iterable[NormalizedDeclaration]) -> None:
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
            f"leanfinder::{self.base_url}::{query}",
            lambda: self._fetch(query),
        )
        return self._parse(text, k=k)

    def _parse(self, text: str, *, k: int) -> list[RetrievalResult]:
        if not text:
            return []
        ex = _ResultExtractor()
        try:
            ex.feed(text)
        except Exception as e:
            logger.warning("leanfinder HTML parse failed: %s", e)
            return []
        out: list[RetrievalResult] = []
        for i, name in enumerate(ex.candidates[:k]):
            out.append(RetrievalResult(name=name, score=1.0 / (i + 1)))
        return out

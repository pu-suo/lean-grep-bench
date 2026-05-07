from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AdapterUnavailable(RuntimeError):
    """Raised when an external adapter cannot be initialized (no endpoint,
    missing credentials, etc.). The eval runner should catch this and report
    N/A for that adapter rather than crashing the run.
    """


class HTTPQueryCache:
    """Disk-backed cache for external query responses.

    Re-runs of the eval are reproducible: the same (adapter, query) hits the
    same cached response. Each cache entry is a JSON file written atomically.
    Entries older than ``ttl_seconds`` are treated as misses on read.
    """

    def __init__(
        self,
        cache_dir: Path,
        ttl_seconds: int = 30 * 86400,
    ) -> None:
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, key: str) -> Path:
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{h}.json"

    def get_or_fetch(
        self,
        key: str,
        fetch_fn: Callable[[], str],
    ) -> str:
        path = self._path(key)
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                ts = float(payload.get("ts", 0))
                if time.time() - ts < self.ttl_seconds:
                    text = payload.get("text")
                    if isinstance(text, str):
                        return text
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("cache miss (corrupt) %s: %s", path, e)

        text = fetch_fn()
        # Atomic write so concurrent workers don't see partial files.
        with self._lock:
            self._atomic_write(path, {"key": key, "ts": time.time(), "text": text})
        return text

    @staticmethod
    def _atomic_write(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise

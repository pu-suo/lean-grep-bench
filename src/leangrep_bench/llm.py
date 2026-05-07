from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatRequest:
    model: str
    system: str
    user: str
    temperature: float
    seed: int

    def cache_key(self) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "system": self.system,
                "user": self.user,
                "temperature": self.temperature,
                "seed": self.seed,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChatResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int
    cached: bool


class _Backend(Protocol):
    def call(self, req: ChatRequest) -> tuple[str, int, int]: ...


class LLMClient:
    """Thin wrapper around an LLM backend with on-disk caching.

    Cache layout: one JSON file per request keyed by SHA-256 of the inputs,
    written atomically. Re-runs against an unchanged prompt cost nothing.
    """

    def __init__(
        self,
        *,
        cache_dir: Path,
        backend: _Backend | None = None,
    ) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._backend = backend or _OpenAIBackend()

    def _cache_path(self, req: ChatRequest) -> Path:
        key = req.cache_key()
        return self.cache_dir / f"{key}.json"

    def chat(self, req: ChatRequest) -> ChatResponse:
        path = self._cache_path(req)
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                return ChatResponse(
                    text=payload["text"],
                    prompt_tokens=int(payload.get("prompt_tokens", 0)),
                    completion_tokens=int(payload.get("completion_tokens", 0)),
                    cached=True,
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("cache miss (corrupt): %s (%s)", path, e)

        text, prompt_tokens, completion_tokens = self._backend.call(req)
        _atomic_write_json(
            path,
            {
                "text": text,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "request": {
                    "model": req.model,
                    "temperature": req.temperature,
                    "seed": req.seed,
                },
            },
        )
        return ChatResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached=False,
        )


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
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


class _OpenAIBackend:
    def __init__(self) -> None:
        self._client: Any | None = None
        self._strip_params: dict[str, bool] = {}

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from dotenv import load_dotenv
        except ImportError:
            load_dotenv = None
        if load_dotenv is not None:
            load_dotenv()
        from openai import OpenAI

        self._client = OpenAI()
        return self._client

    def call(self, req: ChatRequest) -> tuple[str, int, int]:
        client = self._ensure_client()
        messages = [
            {"role": "system", "content": req.system},
            {"role": "user", "content": req.user},
        ]
        kwargs: dict[str, Any] = {
            "model": req.model,
            "messages": messages,
        }
        if not self._strip_params.get(req.model, False):
            kwargs["temperature"] = req.temperature
            kwargs["seed"] = req.seed

        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as e:
            msg = str(e).lower()
            if "temperature" in msg or "seed" in msg or "unsupported" in msg:
                # This model rejects temperature/seed; remember and retry.
                self._strip_params[req.model] = True
                kwargs.pop("seed", None)
                kwargs.pop("temperature", None)
                resp = client.chat.completions.create(**kwargs)
            else:
                raise

        choice = resp.choices[0]
        text = (choice.message.content or "").strip()
        usage = getattr(resp, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        return text, prompt_tokens, completion_tokens

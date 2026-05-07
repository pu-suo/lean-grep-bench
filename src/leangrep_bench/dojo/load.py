from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pydantic import ValidationError

from leangrep_bench.dojo.model import TacticTrace


class TraceLoadError(ValueError):
    """Raised when a trace JSONL line cannot be parsed."""


def _iter_one_file(path: Path) -> Iterator[TacticTrace]:
    with path.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                yield TacticTrace.model_validate_json(line)
            except ValidationError as e:
                raise TraceLoadError(
                    f"{path}:{lineno}: invalid TacticTrace JSON: {e}"
                ) from e
            except ValueError as e:
                raise TraceLoadError(
                    f"{path}:{lineno}: malformed JSON: {e}"
                ) from e


def iter_traces(path: Path) -> Iterator[TacticTrace]:
    """Stream tactic traces from a JSONL file or a directory of JSONL files.

    Directory mode loads every ``*.jsonl`` file in lexicographic order, so the
    iteration order is deterministic across runs and machines. Files starting
    with ``_`` (e.g. ``_progress.json``, ``_failures.json``) are skipped to
    keep sidecar files from polluting the trace stream.

    A malformed line raises :class:`TraceLoadError` whose message includes the
    file path and 1-based line number, so the operator can locate the bad row
    in the JSONL produced on the trace box.
    """
    if path.is_dir():
        for f in sorted(path.glob("*.jsonl")):
            if f.name.startswith("_"):
                continue
            yield from _iter_one_file(f)
        return
    if not path.exists():
        raise FileNotFoundError(f"trace path does not exist: {path}")
    yield from _iter_one_file(path)


__all__ = ["TraceLoadError", "iter_traces"]

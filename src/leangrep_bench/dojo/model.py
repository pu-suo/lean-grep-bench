from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class Premise(BaseModel):
    """A declaration referenced by a tactic, as resolved by LeanDojo."""

    full_name: str
    def_path: str | None = None
    def_line: int | None = None

    model_config = ConfigDict(extra="ignore")


class TacticTrace(BaseModel):
    """One tactic invocation captured by a LeanDojo trace.

    Proof state is preserved as pretty-printed strings (``state_before_pp`` /
    ``state_after_pp``); structured parsing of goals and hypotheses happens
    in phase 9, not here. ``annotated_tactic`` is kept alongside the raw
    ``tactic`` text because it is the only reliable signal for which premise
    is the head of the application — phase 9 derives ``is_head`` from the
    first ``<a>`` tag in this string.
    """

    file: str
    enclosing_decl: str
    enclosing_kind: str
    enclosing_signature: str | None = None

    line_start: int
    line_end: int
    column_start: int
    column_end: int

    tactic: str
    annotated_tactic: str
    state_before_pp: str
    state_after_pp: str
    premises: list[Premise]

    trace_index: int

    model_config = ConfigDict(extra="ignore")


def write_jsonl(path: Path, rows: Iterable[TacticTrace]) -> int:
    """Write tactic traces to a JSONL file. Returns the number of rows written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(row.model_dump_json())
            f.write("\n")
            n += 1
    return n


def read_jsonl(path: Path) -> Iterator[TacticTrace]:
    """Stream tactic traces from a JSONL file."""
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield TacticTrace.model_validate_json(line)


def read_jsonl_raw(path: Path) -> Iterator[dict[str, object]]:
    """Stream raw dicts from a JSONL file (skipping pydantic validation)."""
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

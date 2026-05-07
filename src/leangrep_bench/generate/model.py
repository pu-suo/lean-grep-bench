from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

Scenario = Literal["local_only", "mathlib_only", "mixed"]


class GeneratedQuery(BaseModel):
    """A generated search query for a single proof step.

    ``cited_name_leakage`` flags queries that verbatim contain the cited
    declaration's name. ``goal_leakage`` flags queries that copy a
    ≥30-char substring from the goal text. ``leakage_flag`` is the OR
    of the two so audits can summarise either flavor uniformly.
    """

    id: str
    proof_step_id: str
    query: str
    scenario: Scenario
    generator_model: str
    seed: int
    cited_name_leakage: bool
    goal_leakage: bool
    leakage_flag: bool

    model_config = ConfigDict(extra="ignore")


def write_jsonl(path: Path, rows: Iterable[GeneratedQuery]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(r.model_dump_json())
            f.write("\n")
            f.flush()
            n += 1
    return n


def read_jsonl(path: Path) -> Iterator[GeneratedQuery]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield GeneratedQuery.model_validate_json(line)


def read_jsonl_raw(path: Path) -> Iterator[dict[str, object]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

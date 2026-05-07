from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class Prediction(BaseModel):
    """One adapter's top-k for one benchmark item."""

    adapter: str
    item_id: str
    scenario: str
    ground_truth_name: str
    predicted_names: list[str]
    scores: list[float]

    model_config = ConfigDict(extra="ignore")


def write_jsonl(path: Path, rows: Iterable[Prediction]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(r.model_dump_json())
            f.write("\n")
            f.flush()
            n += 1
    return n


def read_jsonl(path: Path) -> Iterator[Prediction]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield Prediction.model_validate_json(line)


def read_jsonl_raw(path: Path) -> Iterator[dict[str, object]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

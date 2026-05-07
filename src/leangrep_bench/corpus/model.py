from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class NormalizedDeclaration(BaseModel):
    """One Lean declaration after parsing and light normalization."""

    id: str
    source: str
    qualified_name: str
    name: str
    namespace: str | None
    kind: str
    signature: str
    docstring: str | None
    informal: str | None
    file: str
    line: int
    has_complete_info: bool
    missing_fields: list[str]

    model_config = ConfigDict(extra="ignore")


def write_jsonl(path: Path, rows: Iterable[NormalizedDeclaration]) -> int:
    """Write declarations to a JSONL file. Returns the number of rows written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(row.model_dump_json())
            f.write("\n")
            n += 1
    return n


def read_jsonl(path: Path) -> Iterator[NormalizedDeclaration]:
    """Stream declarations from a JSONL file."""
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield NormalizedDeclaration.model_validate_json(line)


def read_jsonl_raw(path: Path) -> Iterator[dict[str, object]]:
    """Stream raw dicts from a JSONL file (skipping pydantic validation)."""
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

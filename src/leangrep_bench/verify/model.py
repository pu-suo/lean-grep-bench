from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

Scenario = Literal["local_only", "mathlib_only", "mixed"]
Source = Literal["mathlib", "pfr"]


class BenchmarkContext(BaseModel):
    enclosing_decl: str
    enclosing_signature: str | None
    goal: str | None
    hypotheses: list[str]
    prior_tactics: list[str]

    model_config = ConfigDict(extra="ignore")


class Provenance(BaseModel):
    source_file: str
    line: int
    tactic_kind: str

    model_config = ConfigDict(extra="ignore")


class GenerationMeta(BaseModel):
    generator_model: str
    verifier_model: str
    seed: int

    model_config = ConfigDict(extra="ignore")


class BenchmarkItem(BaseModel):
    id: str
    scenario: Scenario
    query: str
    ground_truth_name: str
    ground_truth_source: Source
    context: BenchmarkContext
    provenance: Provenance
    generation: GenerationMeta
    # v2 corpus-context fields. The eval runner uses these to apply the
    # visibility filter over the union corpus. Optional on read so v1
    # benchmark.jsonl files still parse; the v2 regen step populates them.
    project: str | None = None
    mathlib_sha: str | None = None

    model_config = ConfigDict(extra="ignore")


class RejectedItem(BaseModel):
    id: str
    proof_step_id: str
    query: str
    ground_truth_name: str
    ground_truth_source: Source
    scenario: Scenario
    verifier_model: str
    reason: str

    model_config = ConfigDict(extra="ignore")


def write_jsonl_accepted(path: Path, rows: Iterable[BenchmarkItem]) -> int:
    return _write_jsonl(path, rows)


def write_jsonl_rejected(path: Path, rows: Iterable[RejectedItem]) -> int:
    return _write_jsonl(path, rows)


def _write_jsonl(path: Path, rows: Iterable[BaseModel]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(r.model_dump_json())
            f.write("\n")
            f.flush()
            n += 1
    return n


def read_jsonl_accepted(path: Path) -> Iterator[BenchmarkItem]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield BenchmarkItem.model_validate_json(line)


def read_jsonl_rejected(path: Path) -> Iterator[RejectedItem]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield RejectedItem.model_validate_json(line)


def read_jsonl_raw(path: Path) -> Iterator[dict[str, object]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

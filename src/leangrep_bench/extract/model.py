from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

TacticKind = Literal["apply", "exact", "use", "refine"]
# v2 source convention: ``"mathlib"`` for upstream lemmas, ``"local:<project>"``
# for declarations native to the traced project. v1 wrote ``"pfr"`` directly;
# loosening this to ``str`` keeps old files readable while letting new files
# carry the v2 form.
CitedSource = str


class ProofStep(BaseModel):
    """A single (tactic, cited declaration) pair derived from a LeanDojo trace.

    Produced from real elaborator output: ``goal_text`` and ``hypotheses``
    come from ``state_before_pp`` rather than being null/source-text, and
    ``cited_name`` is the elaborated full name from LeanDojo's premise
    resolution rather than a regex-parsed identifier.

    Multi-project (Phase 15) adds ``project`` and ``mathlib_sha`` so the
    downstream pipeline can apply the union-corpus visibility filter without
    consulting the manifest again. Both default for back-compat with v1's
    PFR-only ``data/proof_steps.jsonl``.
    """

    id: str
    source_file: str
    line: int
    column: int
    tactic_kind: TacticKind

    cited_name: str
    cited_source: CitedSource

    enclosing_decl: str
    enclosing_signature: str | None

    goal_text: str | None
    hypotheses: list[str]
    prior_tactics: list[str]

    raw_tactic_line: str

    # v2 corpus context. ``project`` defaults to ``"pfr"`` so the pre-existing
    # ``data/proof_steps.jsonl`` (written before Phase 15) still validates.
    # ``mathlib_sha`` is optional because legacy rows omit it.
    project: str = "pfr"
    mathlib_sha: str | None = None

    model_config = ConfigDict(extra="ignore")


@dataclass
class ExtractionSummary:
    trace_files_loaded: int = 0
    tactic_invocations: int = 0
    kept: int = 0
    by_tactic: Counter[str] = field(default_factory=lambda: Counter[str]())
    by_source: Counter[str] = field(default_factory=lambda: Counter[str]())
    skipped: Counter[str] = field(default_factory=lambda: Counter[str]())

    def render(self) -> str:
        lines = [
            "Proof step extraction",
            f"  trace files loaded:   {self.trace_files_loaded:,}",
            f"  tactic invocations:   {self.tactic_invocations:,}",
            f"  kept after filtering: {self.kept:,}",
            "  by tactic_kind: "
            + (
                ", ".join(f"{k}={v:,}" for k, v in self.by_tactic.most_common())
                or "(none)"
            ),
            "  by cited_source: "
            + (
                ", ".join(f"{k}={v:,}" for k, v in self.by_source.most_common())
                or "(none)"
            ),
            "  skipped: "
            + (
                ", ".join(f"{k}={v:,}" for k, v in self.skipped.most_common())
                or "(none)"
            ),
        ]
        return "\n".join(lines)


def write_jsonl(path: Path, rows: Iterable[ProofStep]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(r.model_dump_json())
            f.write("\n")
            n += 1
    return n


def read_jsonl(path: Path) -> Iterator[ProofStep]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield ProofStep.model_validate_json(line)


def read_jsonl_raw(path: Path) -> Iterator[dict[str, object]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

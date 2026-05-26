"""Flatten a benchmark JSONL into a human-viewable CSV.

The CSV is generated from the unified ``data/benchmark.jsonl`` after the
``benchmark merge`` step, and exposes one column per top-level field plus
the most commonly-inspected nested fields under ``context`` / ``provenance``
/ ``generation``. List-valued cells (``hypotheses``, ``prior_tactics``) are
joined with `` | `` so the file stays one-row-per-item.

Used both by the ``leangrep-bench benchmark export-csv`` CLI and by the
companion HTML viewer in ``scripts/convert_benchmark.py``.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from leangrep_bench.verify.model import BenchmarkItem, read_jsonl_accepted

COLUMNS: tuple[str, ...] = (
    "id",
    "project",
    "scenario",
    "query",
    "ground_truth_name",
    "ground_truth_source",
    "context.enclosing_decl",
    "context.enclosing_signature",
    "context.goal",
    "context.hypotheses",
    "context.prior_tactics",
    "provenance.source_file",
    "provenance.line",
    "provenance.tactic_kind",
    "generation.generator_model",
    "generation.verifier_model",
    "generation.seed",
)

LIST_JOIN = " | "
DEFAULT_MAX_LEN = 500


def load_items(path: Path) -> list[BenchmarkItem]:
    """Load and validate a benchmark JSONL into typed ``BenchmarkItem`` rows."""
    return list(read_jsonl_accepted(path))


def _truncate(s: str, max_len: int | None) -> str:
    if max_len is None or len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _cell(value: object, max_len: int | None) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        joined = LIST_JOIN.join(str(v) for v in value)  # type: ignore[reportUnknownArgumentType]
        return _truncate(joined, max_len)
    return _truncate(str(value), max_len)


def flatten_for_csv(item: BenchmarkItem, max_len: int | None) -> list[str]:
    return [
        _cell(item.id, max_len),
        _cell(item.project, max_len),
        _cell(item.scenario, max_len),
        _cell(item.query, max_len),
        _cell(item.ground_truth_name, max_len),
        _cell(item.ground_truth_source, max_len),
        _cell(item.context.enclosing_decl, max_len),
        _cell(item.context.enclosing_signature, max_len),
        _cell(item.context.goal, max_len),
        _cell(item.context.hypotheses, max_len),
        _cell(item.context.prior_tactics, max_len),
        _cell(item.provenance.source_file, max_len),
        _cell(item.provenance.line, max_len),
        _cell(item.provenance.tactic_kind, max_len),
        _cell(item.generation.generator_model, max_len),
        _cell(item.generation.verifier_model, max_len),
        _cell(item.generation.seed, max_len),
    ]


def write_csv(
    items: Iterable[BenchmarkItem],
    out: Path,
    max_len: int | None,
) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(COLUMNS)
        for item in items:
            writer.writerow(flatten_for_csv(item, max_len))
            n += 1
    return n


__all__ = [
    "COLUMNS",
    "DEFAULT_MAX_LEN",
    "LIST_JOIN",
    "flatten_for_csv",
    "load_items",
    "write_csv",
]

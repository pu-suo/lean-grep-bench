"""Tests for scripts/convert_benchmark.py."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "convert_benchmark.py"

spec = importlib.util.spec_from_file_location("convert_benchmark", SCRIPT)
assert spec and spec.loader
convert_benchmark = importlib.util.module_from_spec(spec)
sys.modules["convert_benchmark"] = convert_benchmark
spec.loader.exec_module(convert_benchmark)


FIXTURE = [
    {
        "id": "ex_001.q1",
        "scenario": "local_only",
        "query": "element is in range iff there exists preimage",
        "ground_truth_name": "FiniteRange.mem_iff",
        "ground_truth_source": "pfr",
        "context": {
            "enclosing_decl": "single_fibres",
            "enclosing_signature": "{G : Type*} (φ : G →+ H) : ∀ x, x ∈ Set.range φ",
            "goal": None,
            "hypotheses": ["G : Type*", "φ : G →+ H", "x : H"],
            "prior_tactics": ["intro x", "exact ⟨_, rfl⟩"],
        },
        "provenance": {
            "source_file": "PFR/WeakPFR.lean",
            "line": 464,
            "tactic_kind": "exact",
        },
        "generation": {
            "generator_model": "gpt-5-mini",
            "verifier_model": "gpt-5",
            "seed": 1,
        },
    },
    {
        "id": "ex_002.q1",
        "scenario": "mixed",
        "query": "entropy of pair, with \"quotes\" and, commas",
        "ground_truth_name": "ProbabilityTheory.entropy_pair",
        "ground_truth_source": "pfr",
        "context": {
            "enclosing_decl": "torsion_free_doubling",
            "enclosing_signature": "[FiniteRange X] (hX : Measurable X) : H[⟨X, Y⟩] ≤ H[X] + H[Y]",
            "goal": None,
            "hypotheses": [],
            "prior_tactics": [],
        },
        "provenance": {
            "source_file": "PFR/WeakPFR.lean",
            "line": 171,
            "tactic_kind": "apply",
        },
        "generation": {
            "generator_model": "gpt-5-mini",
            "verifier_model": "gpt-5",
            "seed": 1,
        },
    },
]


def _write_fixture(path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for item in FIXTURE:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def test_csv_columns_and_row_count(tmp_path: Path) -> None:
    src = tmp_path / "bench.jsonl"
    out = tmp_path / "bench.csv"
    _write_fixture(src)

    convert_benchmark.main(
        ["--in", str(src), "--out", str(out), "--format", "csv"]
    )

    with out.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))

    assert rows[0] == convert_benchmark.COLUMNS
    assert len(rows) == 1 + len(FIXTURE)
    for row in rows:
        assert len(row) == len(convert_benchmark.COLUMNS)

    body = out.read_text(encoding="utf-8")
    assert "→+" in body  # unicode preserved
    # List fields joined with " | "
    item0 = rows[1]
    hyp_idx = convert_benchmark.COLUMNS.index("context.hypotheses")
    assert " | " in item0[hyp_idx]


def test_csv_truncation(tmp_path: Path) -> None:
    src = tmp_path / "bench.jsonl"
    out = tmp_path / "bench.csv"
    _write_fixture(src)

    convert_benchmark.main(
        [
            "--in",
            str(src),
            "--out",
            str(out),
            "--format",
            "csv",
            "--max-len",
            "20",
        ]
    )
    with out.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    sig_idx = convert_benchmark.COLUMNS.index("context.enclosing_signature")
    assert rows[1][sig_idx].endswith("…")
    assert len(rows[1][sig_idx]) == 20


class _Validator(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []

    def error(self, message: str) -> None:  # pragma: no cover - py<3.10 compat
        self.errors.append(message)


def test_html_parses(tmp_path: Path) -> None:
    src = tmp_path / "bench.jsonl"
    out = tmp_path / "bench.html"
    _write_fixture(src)

    convert_benchmark.main(
        ["--in", str(src), "--out", str(out), "--format", "html"]
    )

    body = out.read_text(encoding="utf-8")
    parser = _Validator()
    parser.feed(body)
    parser.close()
    assert not parser.errors

    # Self-contained: no external links
    assert "<link" not in body
    assert "<script src" not in body

    # One row per fixture item
    assert body.count('<tr data-scenario=') == len(FIXTURE)

    # Quotes and commas in query are escaped, not breaking HTML
    assert "&quot;quotes&quot;" in body

    # Unicode preserved
    assert "→+" in body
    assert "⟨X, Y⟩" in body


def test_html_is_default_format(tmp_path: Path) -> None:
    src = tmp_path / "bench.jsonl"
    out = tmp_path / "out.html"
    _write_fixture(src)
    convert_benchmark.main(["--in", str(src), "--out", str(out)])
    body = out.read_text(encoding="utf-8")
    assert body.lstrip().startswith("<!doctype html>")

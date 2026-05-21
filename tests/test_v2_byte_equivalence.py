"""Phase 13 byte-equivalence gate.

Refactoring the corpus into the v2 union format must not change R@k for
the existing PFR-only benchmark. This test re-runs the BM25 baseline
against the v2 corpus + regenerated benchmark and asserts that every
per-scenario metric matches the v1 result file exactly.

Dense baselines are byte-equivalent in principle too, but they pull in
sentence-transformers and run for minutes — out of scope for a unit
test. BM25 equality is sufficient evidence the visibility filter, corpus
union, and ID regen behave as no-ops in the PFR-only case.

Skipped if the v1 result file isn't present (e.g. on a fresh clone with
no prior run-001 artifacts).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from leangrep_bench.eval.runner import run_eval

REPO_ROOT = Path(__file__).resolve().parent.parent
V1_METRICS = REPO_ROOT / "results" / "run-001" / "metrics.json"
BENCHMARK = REPO_ROOT / "data" / "benchmark.jsonl"
CORPUS_DIR = REPO_ROOT / "data" / "corpus"
UNION_DIR = CORPUS_DIR / "v2"


def _find_adapter(report: dict, name: str) -> dict:
    for a in report["adapters"]:
        if a["adapter"] == name:
            return a["metrics"]
    raise KeyError(name)


def test_bm25_byte_equivalent_to_v1(tmp_path: Path) -> None:
    if not V1_METRICS.exists():
        pytest.skip(f"no v1 metrics at {V1_METRICS}")
    if not UNION_DIR.exists():
        pytest.skip(f"union corpus not built at {UNION_DIR}")

    v2_metrics = run_eval(
        benchmark_path=BENCHMARK,
        corpus_dir=CORPUS_DIR,
        adapter_names=["bm25"],
        out_dir=tmp_path,
        k=10,
    )
    v1_metrics = json.loads(V1_METRICS.read_text(encoding="utf-8"))

    v1_bm25 = _find_adapter(v1_metrics, "bm25")
    v2_bm25 = _find_adapter(v2_metrics, "bm25")

    assert v1_bm25.keys() == v2_bm25.keys(), "slice sets differ"
    for slice_name, v1_slice in v1_bm25.items():
        v2_slice = v2_bm25[slice_name]
        for metric in ("recall_at_1", "recall_at_5", "recall_at_10", "mrr"):
            assert abs(v1_slice[metric] - v2_slice[metric]) < 1e-9, (
                f"{slice_name}/{metric} drifted: "
                f"v1={v1_slice[metric]:.9f} v2={v2_slice[metric]:.9f}"
            )

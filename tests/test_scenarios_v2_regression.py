"""Phase 14 regression test.

Re-classifies every v1 benchmark item under the v2 classifier and asserts
that the resulting label matches the label already stored on the item.
Any drift means either the v2 classifier or the v1 labels need fixing
(per Phase 14 spec risks). The drift must be resolved before Phase 15.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from leangrep_bench.corpus.model import read_jsonl as read_corpus
from leangrep_bench.corpus.scenarios import (
    CitedLemmaNotInCorpus,
    build_scenario_index,
    classify_scenario,
)
from leangrep_bench.verify.model import read_jsonl_accepted

REPO_ROOT = Path(__file__).resolve().parent.parent
UNION_DIR = REPO_ROOT / "data" / "corpus" / "v2"
BENCHMARK = REPO_ROOT / "data" / "benchmark.jsonl"


def test_v2_classifier_matches_v1_labels_for_all_pfr_items() -> None:
    if not UNION_DIR.exists():
        pytest.skip(f"union corpus not built at {UNION_DIR}")
    if not BENCHMARK.exists():
        pytest.skip(f"benchmark not present at {BENCHMARK}")

    corpus = []
    for p in sorted(UNION_DIR.glob("*.jsonl")):
        corpus.extend(read_corpus(p))
    index = build_scenario_index(corpus)

    items = list(read_jsonl_accepted(BENCHMARK))
    assert items, "expected v2 benchmark items"

    diffs: list[tuple[str, str, str, str]] = []
    unresolved: list[tuple[str, str]] = []

    for it in items:
        assert it.project is not None and it.mathlib_sha is not None, (
            f"item {it.id} missing project/mathlib_sha; "
            "rerun scripts/regen_v2_ids.py"
        )
        try:
            predicted = classify_scenario(
                project=it.project,
                mathlib_sha=it.mathlib_sha,
                cited_lemma_qualified_name=it.ground_truth_name,
                index=index,
            )
        except CitedLemmaNotInCorpus:
            unresolved.append((it.id, it.ground_truth_name))
            continue
        if predicted != it.scenario:
            diffs.append((it.id, it.ground_truth_name, it.scenario, predicted))

    assert not unresolved, (
        f"{len(unresolved)} items have cited lemmas not in the union corpus; "
        f"first 5: {unresolved[:5]}"
    )
    assert not diffs, (
        f"{len(diffs)} v2 labels disagree with v1; first 5: {diffs[:5]}"
    )

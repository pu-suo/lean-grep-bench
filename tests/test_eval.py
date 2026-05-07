from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from leangrep_bench.adapters.base import RetrievalAdapter, RetrievalResult
from leangrep_bench.adapters.registry import _BUILDERS  # type: ignore[attr-defined]
from leangrep_bench.corpus.model import NormalizedDeclaration
from leangrep_bench.corpus.model import write_jsonl as write_corpus_jsonl
from leangrep_bench.eval.metrics import compute_metrics
from leangrep_bench.eval.runner import run_eval
from leangrep_bench.verify.model import (
    BenchmarkContext,
    BenchmarkItem,
    GenerationMeta,
    Provenance,
)


def _item(item_id: str, scenario: str, gt: str, query: str) -> BenchmarkItem:
    return BenchmarkItem(
        id=item_id,
        scenario=scenario,  # type: ignore[arg-type]
        query=query,
        ground_truth_name=gt,
        ground_truth_source="mathlib",
        context=BenchmarkContext(
            enclosing_decl="x", enclosing_signature=None,
            goal=None, hypotheses=[], prior_tactics=[],
        ),
        provenance=Provenance(source_file="X.lean", line=1, tactic_kind="apply"),
        generation=GenerationMeta(
            generator_model="g", verifier_model="v", seed=0
        ),
    )


def _decl(qual: str) -> NormalizedDeclaration:
    return NormalizedDeclaration(
        id=f"mathlib::{qual}",
        source="mathlib",
        qualified_name=qual,
        name=qual.split(".")[-1],
        namespace=".".join(qual.split(".")[:-1]) or None,
        kind="theorem",
        signature="(x : Nat) : True",
        docstring=None,
        informal=None,
        file="X.lean",
        line=1,
        has_complete_info=True,
        missing_fields=[],
    )


def test_compute_metrics_basic() -> None:
    rows = [
        ("foo", ["foo", "bar", "baz"]),  # rank 1
        ("bar", ["a", "bar", "c"]),  # rank 2
        ("qux", ["a", "b", "c"]),  # not in top-3
    ]
    m = compute_metrics(rows, ks=(1, 5, 10))
    assert m.n == 3
    # Hits: rank 1 contributes to all k. Rank 2 contributes to k>=2 (so k=5,10).
    # Top-3 rank-2 hits k=5 and k=10. qux: no hit.
    assert m.recall_at[1] == 1 / 3
    assert m.recall_at[5] == 2 / 3
    assert m.recall_at[10] == 2 / 3
    # MRR = (1/1 + 1/2 + 0) / 3
    assert abs(m.mrr - (1.0 + 0.5) / 3) < 1e-9


def test_compute_metrics_empty() -> None:
    m = compute_metrics([], ks=(1, 5, 10))
    assert m.n == 0
    assert m.recall_at[1] == 0.0
    assert m.mrr == 0.0


class _MockAdapter(RetrievalAdapter):
    """Adapter that returns a hand-coded mapping query→list[name]."""

    def __init__(self, name: str, table: dict[str, list[str]]) -> None:
        self.name = name
        self.table = table
        self.indexed = 0

    def index(self, corpus: Iterable[NormalizedDeclaration]) -> None:
        self.indexed += 1
        list(corpus)

    def search(
        self,
        query: str,
        context: BenchmarkContext | None = None,
        k: int = 10,
    ) -> list[RetrievalResult]:
        del context
        names = self.table.get(query, [])
        return [
            RetrievalResult(name=n, score=float(k - i))
            for i, n in enumerate(names[:k])
        ]


def _setup_corpus_and_bench(tmp_path: Path) -> tuple[Path, Path]:
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    decls = [
        _decl("Foo.add_comm"),
        _decl("Foo.mul_comm"),
        _decl("Foo.add_assoc"),
    ]
    write_corpus_jsonl(corpus_dir / "mathlib_declarations.jsonl", decls)

    bench_path = tmp_path / "benchmark.jsonl"
    items = [
        _item("i1", "mathlib_only", "Foo.add_comm", "addition is commutative"),
        _item("i2", "mathlib_only", "Foo.mul_comm", "multiplication is commutative"),
        _item("i3", "local_only", "Foo.add_assoc", "addition is associative"),
    ]
    bench_path.write_text(
        "\n".join(it.model_dump_json() for it in items) + "\n",
        encoding="utf-8",
    )
    return bench_path, corpus_dir


def test_run_eval_with_mock_adapter(tmp_path: Path) -> None:
    bench_path, corpus_dir = _setup_corpus_and_bench(tmp_path)

    table = {
        "addition is commutative": ["Foo.add_comm", "Foo.mul_comm"],
        "multiplication is commutative": ["Foo.add_comm", "Foo.mul_comm"],
        "addition is associative": ["Foo.zero_lt", "Foo.add_assoc"],
    }
    mock = _MockAdapter(name="mock", table=table)
    builder_key = "test-mock"
    _BUILDERS[builder_key] = lambda: mock
    try:
        out_dir = tmp_path / "results"
        run_eval(
            benchmark_path=bench_path,
            corpus_dir=corpus_dir,
            adapter_names=[builder_key],
            out_dir=out_dir,
            k=10,
        )
        # Adapter was indexed once.
        assert mock.indexed == 1

        # metrics.json contents
        m = json.loads((out_dir / "metrics.json").read_text())
        adapter_block = m["adapters"][0]
        assert adapter_block["adapter"] == "mock"
        overall = adapter_block["metrics"]["overall"]
        assert overall["n"] == 3
        # i1 and i2 hit at rank 1 and 2 respectively. i3 hits at rank 2.
        # Recall@1 = 1/3 (only i1 hits at top-1).
        assert abs(overall["recall_at_1"] - 1 / 3) < 1e-9
        # Recall@5 = 3/3 (all hit within top-2).
        assert abs(overall["recall_at_5"] - 1.0) < 1e-9
        # MRR = (1/1 + 1/2 + 1/2) / 3 = 2/3
        assert abs(overall["mrr"] - 2 / 3) < 1e-9

        # results.md exists
        assert (out_dir / "results.md").exists()
        md = (out_dir / "results.md").read_text()
        assert "Overall (N=3)" in md
        assert "| mock |" in md

        # predictions.jsonl has all rows
        preds = (out_dir / "predictions.jsonl").read_text().strip().splitlines()
        assert len(preds) == 3

        # Resume: second run should not call adapter.search again.
        mock.indexed = 0
        run_eval(
            benchmark_path=bench_path,
            corpus_dir=corpus_dir,
            adapter_names=[builder_key],
            out_dir=out_dir,
            k=10,
        )
        # Adapter.index() is *not* called when all predictions are already cached.
        assert mock.indexed == 0
    finally:
        del _BUILDERS[builder_key]


def test_unknown_adapter_errors_cleanly(tmp_path: Path) -> None:
    bench_path, corpus_dir = _setup_corpus_and_bench(tmp_path)
    out_dir = tmp_path / "results"
    try:
        run_eval(
            benchmark_path=bench_path,
            corpus_dir=corpus_dir,
            adapter_names=["bm25", "totally-not-a-real-adapter"],
            out_dir=out_dir,
            k=10,
        )
        raise AssertionError("expected KeyError")
    except KeyError as e:
        assert "totally-not-a-real-adapter" in str(e)

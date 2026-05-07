from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from leangrep_bench.adapters.external import (
    AdapterUnavailable,
    HTTPQueryCache,
    LeanFinderAdapter,
    LeanGrepAdapter,
    LeanSearchAdapter,
    MoogleAdapter,
)


def test_cache_round_trip(tmp_path: Path) -> None:
    cache = HTTPQueryCache(cache_dir=tmp_path)
    calls = {"n": 0}

    def fetch() -> str:
        calls["n"] += 1
        return "first"

    a = cache.get_or_fetch("k1", fetch)
    b = cache.get_or_fetch("k1", fetch)
    assert a == "first"
    assert b == "first"
    assert calls["n"] == 1


def test_cache_invalidates_after_ttl(tmp_path: Path) -> None:
    cache = HTTPQueryCache(cache_dir=tmp_path, ttl_seconds=0)
    a = cache.get_or_fetch("k", lambda: "v1")
    b = cache.get_or_fetch("k", lambda: "v2")
    assert a == "v1"
    assert b == "v2"


def test_moogle_raises_unavailable() -> None:
    with pytest.raises(AdapterUnavailable):
        MoogleAdapter()


def test_leangrep_raises_unavailable() -> None:
    with pytest.raises(AdapterUnavailable):
        LeanGrepAdapter()


def test_leanfinder_raises_unavailable_when_no_url() -> None:
    import os

    saved = os.environ.pop("LEANFINDER_URL", None)
    try:
        with pytest.raises(AdapterUnavailable):
            LeanFinderAdapter()
    finally:
        if saved is not None:
            os.environ["LEANFINDER_URL"] = saved


class _StubLeanSearch(LeanSearchAdapter):
    """LeanSearch with HTTP replaced by a fixed mapping."""

    def __init__(self, *, mapping: dict[str, str], cache_dir: Path) -> None:
        super().__init__(base_url="http://stub", cache_dir=cache_dir, rate_limit_s=0.0)
        self._mapping = mapping
        self.fetch_calls = 0

    def _fetch(self, query: str) -> str:
        self.fetch_calls += 1
        return self._mapping.get(query, "")


def test_leansearch_parses_results(tmp_path: Path) -> None:
    payload = json.dumps(
        {
            "results": [
                {"formal_name": "Foo.bar", "score": 0.9},
                {"formal_name": "Foo.baz", "score": 0.7},
            ]
        }
    )
    adapter = _StubLeanSearch(
        mapping={"my query": payload}, cache_dir=tmp_path
    )
    results = adapter.search("my query", k=10)
    assert [r.name for r in results] == ["Foo.bar", "Foo.baz"]
    assert results[0].score > results[1].score


def test_leansearch_empty_response_returns_empty(tmp_path: Path) -> None:
    adapter = _StubLeanSearch(mapping={"q": ""}, cache_dir=tmp_path)
    assert adapter.search("q") == []


def test_leansearch_uses_cache(tmp_path: Path) -> None:
    payload = json.dumps([{"formal_name": "X.y"}])
    adapter = _StubLeanSearch(mapping={"q": payload}, cache_dir=tmp_path)
    adapter.search("q")
    adapter.search("q")
    assert adapter.fetch_calls == 1


class _StubLeanFinder(LeanFinderAdapter):
    def __init__(self, *, mapping: dict[str, str], cache_dir: Path) -> None:
        super().__init__(
            base_url="http://stub-leanfinder",
            cache_dir=cache_dir,
            rate_limit_s=0.0,
        )
        self._mapping = mapping
        self.fetch_calls = 0

    def _fetch(self, query: str) -> str:
        self.fetch_calls += 1
        return self._mapping.get(query, "")


def test_leanfinder_html_parse(tmp_path: Path) -> None:
    html = """
    <html><body>
      <ul>
        <li>Mathlib.Order.le_trans</li>
        <li>Foo.bar.baz</li>
      </ul>
      <pre>Other text Mathlib.Order.le_trans appears again</pre>
    </body></html>
    """
    adapter = _StubLeanFinder(mapping={"q": html}, cache_dir=tmp_path)
    results = adapter.search("q", k=10)
    names = [r.name for r in results]
    assert "Mathlib.Order.le_trans" in names
    assert "Foo.bar.baz" in names
    # Names appear once even when present multiple times in the HTML.
    assert names.count("Mathlib.Order.le_trans") == 1


def test_leanfinder_handles_empty_response(tmp_path: Path) -> None:
    adapter = _StubLeanFinder(mapping={"q": ""}, cache_dir=tmp_path)
    assert adapter.search("q") == []


def test_eval_runner_handles_unavailable_adapter(tmp_path: Path) -> None:
    """End-to-end: an unavailable adapter doesn't break the run."""
    from leangrep_bench.adapters.registry import _BUILDERS  # type: ignore[attr-defined]
    from leangrep_bench.corpus.model import (
        NormalizedDeclaration,
    )
    from leangrep_bench.corpus.model import (
        write_jsonl as write_corpus_jsonl,
    )
    from leangrep_bench.eval.runner import run_eval
    from leangrep_bench.verify.model import (
        BenchmarkContext,
        BenchmarkItem,
        GenerationMeta,
        Provenance,
    )

    # Tiny benchmark + corpus.
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    decl = NormalizedDeclaration(
        id="m::Foo.bar",
        source="mathlib",
        qualified_name="Foo.bar",
        name="bar",
        namespace="Foo",
        kind="theorem",
        signature="(x : Nat) : True",
        docstring=None,
        informal=None,
        file="X.lean",
        line=1,
        has_complete_info=True,
        missing_fields=[],
    )
    write_corpus_jsonl(corpus_dir / "mathlib_declarations.jsonl", [decl])

    bench_path = tmp_path / "bench.jsonl"
    item = BenchmarkItem(
        id="i1",
        scenario="mathlib_only",
        query="addition",
        ground_truth_name="Foo.bar",
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
    bench_path.write_text(item.model_dump_json() + "\n", encoding="utf-8")

    # Register a stub that always raises.
    def _bad() -> Any:
        raise AdapterUnavailable("simulated outage")

    _BUILDERS["test-bad"] = _bad
    try:
        out_dir = tmp_path / "out"
        metrics = run_eval(
            benchmark_path=bench_path,
            corpus_dir=corpus_dir,
            adapter_names=["bm25", "test-bad"],
            out_dir=out_dir,
            k=10,
        )
        # bm25 ran; test-bad is reported as unavailable.
        unavail = metrics["unavailable"]
        assert isinstance(unavail, dict)
        assert "test-bad" in unavail
        # results.md mentions the unavailable adapter.
        md = (out_dir / "results.md").read_text()
        assert "test-bad" in md
        # bm25 still produced predictions.
        preds_text = (out_dir / "predictions.jsonl").read_text()
        assert "bm25" in preds_text
    finally:
        del _BUILDERS["test-bad"]


def _all_adapter_names_resolve_to_class() -> None:
    """Defensive: every registry name builds (or raises AdapterUnavailable)."""
    from leangrep_bench.adapters.registry import _BUILDERS  # type: ignore[attr-defined]

    for name, builder in _BUILDERS.items():
        try:
            builder()
        except AdapterUnavailable:
            pass
        except Exception as e:
            raise AssertionError(
                f"adapter {name} raised unexpected error: {e!r}"
            ) from e


def test_all_registry_adapters_resolve() -> None:
    _all_adapter_names_resolve_to_class()

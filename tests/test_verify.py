from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from leangrep_bench.corpus.model import NormalizedDeclaration
from leangrep_bench.corpus.model import write_jsonl as write_corpus_jsonl
from leangrep_bench.extract.model import ProofStep
from leangrep_bench.generate.model import GeneratedQuery
from leangrep_bench.llm import ChatRequest, LLMClient
from leangrep_bench.verify.model import (
    BenchmarkItem,
    read_jsonl_accepted,
    read_jsonl_rejected,
)
from leangrep_bench.verify.pipeline import verify_queries
from leangrep_bench.verify.prompt import build_user_prompt, parse_verdict


def test_prompt_renders_required_fields() -> None:
    p = build_user_prompt(
        query="map of an a.e.-equal pair has equal pushforward",
        qualified_name="MeasureTheory.Measure.map_congr",
        kind="theorem",
        signature="(h : f =ᵐ[μ] g) : μ.map f = μ.map g",
        docstring="Two measures pushed forward by a.e.-equal maps coincide.",
    )
    assert "MeasureTheory.Measure.map_congr" in p
    assert "(h : f =ᵐ[μ] g)" in p
    assert "Two measures" in p
    assert "Query:" in p


def test_parse_verdict_yes() -> None:
    v = parse_verdict('{"verdict": "YES", "reason": "matches"}')
    assert v.is_yes is True
    assert v.reason == "matches"


def test_parse_verdict_no() -> None:
    v = parse_verdict('  {"verdict":"NO","reason":"unrelated"}  ')
    assert v.is_yes is False
    assert "unrelated" in v.reason


def test_parse_verdict_with_code_fence() -> None:
    v = parse_verdict('```json\n{"verdict": "YES", "reason": "ok"}\n```')
    assert v.is_yes is True


def test_parse_verdict_with_leading_text() -> None:
    text = 'Sure, here is the result:\n{"verdict": "NO", "reason": "no match"}'
    v = parse_verdict(text)
    assert v.is_yes is False


def test_parse_verdict_unparseable_raises() -> None:
    with pytest.raises(ValueError):
        parse_verdict("blank reply with neither verdict token")


def test_benchmark_item_schema_round_trip(tmp_path: Path) -> None:
    item = BenchmarkItem.model_validate(
        {
            "id": "x",
            "scenario": "mathlib_only",
            "query": "q",
            "ground_truth_name": "Foo.bar",
            "ground_truth_source": "mathlib",
            "context": {
                "enclosing_decl": "thm",
                "enclosing_signature": "True",
                "goal": None,
                "hypotheses": [],
                "prior_tactics": [],
            },
            "provenance": {
                "source_file": "PFR/X.lean",
                "line": 1,
                "tactic_kind": "apply",
            },
            "generation": {
                "generator_model": "gen",
                "verifier_model": "ver",
                "seed": 0,
            },
        }
    )
    p = tmp_path / "out.jsonl"
    p.write_text(item.model_dump_json() + "\n", encoding="utf-8")
    rows = list(read_jsonl_accepted(p))
    assert rows == [item]


@dataclass
class _Backend:
    response: str
    calls: int = 0

    def call(self, req: ChatRequest) -> tuple[str, int, int]:
        self.calls += 1
        return self.response, 50, 10


def _seed_files(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    queries = tmp_path / "queries.jsonl"
    steps = tmp_path / "steps.jsonl"
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    out = tmp_path / "benchmark.jsonl"
    rejected = tmp_path / "rejected.jsonl"

    step = ProofStep(
        id="pfr_step_test",
        source_file="PFR/Foo.lean",
        line=10,
        column=2,
        tactic_kind="apply",
        cited_name="Foo.bar",
        cited_source="mathlib",
        enclosing_decl="thm",
        enclosing_signature="(x : Nat) : True",
        goal_text="⊢ x = x",
        hypotheses=["x : Nat"],
        prior_tactics=["intro x"],
        raw_tactic_line="  apply Foo.bar",
    )
    steps.write_text(step.model_dump_json() + "\n", encoding="utf-8")

    query = GeneratedQuery(
        id="pfr_step_test.q1",
        proof_step_id="pfr_step_test",
        query="something true",
        scenario="mathlib_only",
        generator_model="gpt-5-mini",
        seed=1,
        cited_name_leakage=False,
        goal_leakage=False,
        leakage_flag=False,
    )
    queries.write_text(query.model_dump_json() + "\n", encoding="utf-8")

    decl = NormalizedDeclaration(
        id="mathlib::Foo.bar",
        source="mathlib",
        qualified_name="Foo.bar",
        name="bar",
        namespace="Foo",
        kind="theorem",
        signature="(x : Nat) : True",
        docstring=None,
        informal=None,
        file="Mathlib/Foo.lean",
        line=1,
        has_complete_info=True,
        missing_fields=[],
    )
    write_corpus_jsonl(corpus_dir / "mathlib_declarations.jsonl", [decl])

    return queries, steps, corpus_dir, out, rejected


def test_pipeline_yes_writes_accepted(tmp_path: Path) -> None:
    queries, steps, corpus_dir, out, rejected = _seed_files(tmp_path)
    backend = _Backend(response='{"verdict": "YES", "reason": "matches"}')
    client = LLMClient(cache_dir=tmp_path / "cache", backend=backend)

    stats = verify_queries(
        queries_path=queries,
        steps_path=steps,
        corpus_dir=corpus_dir,
        out_path=out,
        rejected_path=rejected,
        cache_dir=tmp_path / "cache",
        model="test",
        client=client,
        concurrency=1,
    )

    assert stats.accepted == 1
    assert stats.rejected == 0
    rows = list(read_jsonl_accepted(out))
    assert len(rows) == 1
    assert rows[0].ground_truth_name == "Foo.bar"
    # The elaborated goal text from the proof step must reach
    # ``BenchmarkContext.goal``; it's the headline guarantee of the
    # verifier output.
    assert rows[0].context.goal == "⊢ x = x"
    assert rows[0].context.hypotheses == ["x : Nat"]
    assert rows[0].context.prior_tactics == ["intro x"]


def test_pipeline_no_writes_rejected(tmp_path: Path) -> None:
    queries, steps, corpus_dir, out, rejected = _seed_files(tmp_path)
    backend = _Backend(response='{"verdict": "NO", "reason": "wrong"}')
    client = LLMClient(cache_dir=tmp_path / "cache", backend=backend)

    stats = verify_queries(
        queries_path=queries,
        steps_path=steps,
        corpus_dir=corpus_dir,
        out_path=out,
        rejected_path=rejected,
        cache_dir=tmp_path / "cache",
        model="test",
        client=client,
        concurrency=1,
    )

    assert stats.accepted == 0
    assert stats.rejected == 1
    assert list(read_jsonl_accepted(out)) == []
    rejs = list(read_jsonl_rejected(rejected))
    assert len(rejs) == 1
    assert rejs[0].reason == "wrong"


def test_pipeline_resume_skips_existing(tmp_path: Path) -> None:
    queries, steps, corpus_dir, out, rejected = _seed_files(tmp_path)
    backend = _Backend(response='{"verdict": "YES", "reason": "ok"}')
    client = LLMClient(cache_dir=tmp_path / "cache", backend=backend)

    verify_queries(
        queries_path=queries, steps_path=steps, corpus_dir=corpus_dir,
        out_path=out, rejected_path=rejected,
        cache_dir=tmp_path / "cache", model="test", client=client, concurrency=1,
    )
    stats2 = verify_queries(
        queries_path=queries, steps_path=steps, corpus_dir=corpus_dir,
        out_path=out, rejected_path=rejected,
        cache_dir=tmp_path / "cache", model="test", client=client, concurrency=1,
    )
    assert stats2.skipped_existing == 1
    assert stats2.accepted == 0
    assert stats2.rejected == 0
    # Backend should only have been called once.
    assert backend.calls == 1

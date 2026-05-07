from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from leangrep_bench.extract.model import ProofStep
from leangrep_bench.generate.pipeline import generate_queries
from leangrep_bench.generate.prompt import (
    GOAL_LEAKAGE_WINDOW,
    GOAL_PLACEHOLDER,
    build_user_prompt,
    cited_name_leakage_check,
    goal_leakage_check,
)
from leangrep_bench.llm import ChatRequest, LLMClient


def _step(**overrides: Any) -> ProofStep:
    base: dict[str, Any] = {
        "id": "pfr_step_test",
        "source_file": "PFR/Foo.lean",
        "line": 10,
        "column": 2,
        "tactic_kind": "apply",
        "cited_name": "MeasureTheory.Measure.map_congr",
        "cited_source": "mathlib",
        "enclosing_decl": "my_thm",
        "enclosing_signature": "(μ : Measure Ω) (h : f =ᵐ[μ] g) : True",
        "goal_text": "⊢ μ.map f = μ.map g",
        "hypotheses": ["μ : Measure Ω", "h : f =ᵐ[μ] g"],
        "prior_tactics": ["intro x", "rw [foo]"],
        "raw_tactic_line": "  apply MeasureTheory.Measure.map_congr h",
    }
    base.update(overrides)
    return ProofStep.model_validate(base)


def test_prompt_includes_goal_block() -> None:
    step = _step()
    p = build_user_prompt(step)
    assert "⊢ μ.map f = μ.map g" in p
    assert "find a lemma to close this goal" in p


def test_prompt_redacts_cited_name() -> None:
    step = _step()
    p = build_user_prompt(step)
    assert "MeasureTheory.Measure.map_congr" not in p
    assert "map_congr" not in p
    assert "???" in p


def test_prompt_anti_paraphrase_clause_present() -> None:
    step = _step()
    p = build_user_prompt(step)
    # The clause warns explicitly against verbatim restatement of the goal.
    assert "Do NOT restate the goal verbatim" in p
    assert "Do NOT describe the overall theorem" in p


def test_prompt_handles_missing_goal_with_placeholder() -> None:
    step = _step(goal_text=None)
    p = build_user_prompt(step)
    assert GOAL_PLACEHOLDER in p


def test_prompt_handles_blank_goal_with_placeholder() -> None:
    step = _step(goal_text="   \n  ")
    p = build_user_prompt(step)
    assert GOAL_PLACEHOLDER in p


def test_prompt_renders_empty_lists_as_none() -> None:
    step = _step(hypotheses=[], prior_tactics=[])
    p = build_user_prompt(step)
    # Two ``(none)`` markers: one for hypotheses, one for prior tactics.
    assert p.count("(none)") == 2


def test_cited_name_leakage_check_reused_from_v1() -> None:
    # Smoke test that the v1 import is wired through.
    name = "MeasureTheory.Measure.map_congr"
    assert cited_name_leakage_check("blah map_congr please", name)
    assert not cited_name_leakage_check(
        "the measure of two equal-almost-everywhere functions matches",
        name,
    )


def test_goal_leakage_flags_verbatim_long_substring() -> None:
    goal = "X.entropy ≤ Real.log (Nat.card X) for finite-range variables"
    # Query that copies a 30+ char substring of the goal verbatim.
    bad = "shows X.entropy ≤ Real.log (Nat.card X) something"
    assert goal_leakage_check(bad, goal)


def test_goal_leakage_does_not_flag_real_paraphrase() -> None:
    goal = "X.entropy ≤ Real.log (Nat.card X) for finite-range variables"
    good = "entropy of finite-range variable bounded by log of cardinality"
    assert not goal_leakage_check(good, goal)


def test_goal_leakage_handles_none_and_short() -> None:
    assert not goal_leakage_check("anything", None)
    # Goal shorter than the window can never trigger.
    short_goal = "abc"
    assert not goal_leakage_check("a literal abc shows up", short_goal)


def test_goal_leakage_window_is_advertised() -> None:
    # Document the window length so a future tighten-or-loosen change
    # has to update this test along with prompt.py.
    assert GOAL_LEAKAGE_WINDOW == 30


@dataclass
class _StubBackend:
    response: str
    calls: int = 0

    def call(self, req: ChatRequest) -> tuple[str, int, int]:
        self.calls += 1
        return self.response, 100, 20


def test_pipeline_with_stub_backend(tmp_path: Path) -> None:
    steps_path = tmp_path / "steps.jsonl"
    out_path = tmp_path / "queries.jsonl"
    cache_dir = tmp_path / "cache"
    corpus_dir = tmp_path / "corpus"

    step = _step()
    steps_path.write_text(step.model_dump_json() + "\n", encoding="utf-8")

    backend = _StubBackend(
        response="when two functions agree a.e. their pushforwards match"
    )
    client = LLMClient(cache_dir=cache_dir, backend=backend)

    stats = generate_queries(
        steps_path=steps_path,
        out_path=out_path,
        cache_dir=cache_dir,
        corpus_dir=corpus_dir,
        model="test-model",
        seed=42,
        client=client,
    )

    assert stats.generated == 1
    assert stats.api_calls == 1
    assert stats.cited_name_leakage_count == 0
    assert stats.goal_leakage_count == 0
    rows = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1


def test_pipeline_records_goal_leakage(tmp_path: Path) -> None:
    steps_path = tmp_path / "steps.jsonl"
    out_path = tmp_path / "queries.jsonl"
    cache_dir = tmp_path / "cache"
    corpus_dir = tmp_path / "corpus"

    step = _step(goal_text="X.entropy ≤ Real.log (Nat.card X) for finite types")
    steps_path.write_text(step.model_dump_json() + "\n", encoding="utf-8")

    # Response copies a long verbatim substring of the goal.
    backend = _StubBackend(
        response="shows X.entropy ≤ Real.log (Nat.card X) for finite types"
    )
    client = LLMClient(cache_dir=cache_dir, backend=backend)

    stats = generate_queries(
        steps_path=steps_path,
        out_path=out_path,
        cache_dir=cache_dir,
        corpus_dir=corpus_dir,
        model="test-model",
        seed=99,
        client=client,
    )

    assert stats.goal_leakage_count == 1
    assert stats.any_leakage_count == 1


def test_pipeline_resume_safe(tmp_path: Path) -> None:
    """Re-running with the same `--out` skips already-generated rows."""
    steps_path = tmp_path / "steps.jsonl"
    out_path = tmp_path / "queries.jsonl"
    cache_dir = tmp_path / "cache"
    corpus_dir = tmp_path / "corpus"

    step = _step()
    steps_path.write_text(step.model_dump_json() + "\n", encoding="utf-8")

    backend = _StubBackend(response="some paraphrase")
    client = LLMClient(cache_dir=cache_dir, backend=backend)
    generate_queries(
        steps_path=steps_path,
        out_path=out_path,
        cache_dir=cache_dir,
        corpus_dir=corpus_dir,
        model="test-model",
        seed=1,
        client=client,
    )
    stats2 = generate_queries(
        steps_path=steps_path,
        out_path=out_path,
        cache_dir=cache_dir,
        corpus_dir=corpus_dir,
        model="test-model",
        seed=1,
        client=client,
    )
    assert stats2.skipped_existing == 1
    assert stats2.generated == 0
    assert backend.calls == 1

from __future__ import annotations

from pathlib import Path

from leangrep_bench.dojo.model import Premise, TacticTrace, write_jsonl
from leangrep_bench.dojo.summarize import _tactic_head, summarize

FIXTURE = Path(__file__).parent / "fixtures" / "dojo_trace_sample.jsonl"


def test_tactic_head_handles_multiline_and_empty() -> None:
    assert _tactic_head("apply foo") == "apply"
    assert _tactic_head("  exact  bar") == "exact"
    assert _tactic_head("apply le_trans\n    (foo)\n    (bar)") == "apply"
    assert _tactic_head("") == ""
    assert _tactic_head("   ") == ""
    assert _tactic_head("simp") == "simp"


def test_summarize_counts_against_fixture() -> None:
    s = summarize(FIXTURE)
    assert s.total_tactics == 5
    assert s.files_loaded == 3  # Tactic.lean, Probability/Basic.lean, Entropy.lean
    assert s.by_tactic_head["apply"] == 2
    assert s.by_tactic_head["exact"] == 2
    assert s.by_tactic_head["refine"] == 1
    # Two records have empty premises.
    assert s.n_zero_premises == 2
    # One record has annotated_tactic == "" (the refine).
    assert s.n_with_annotated_tactic == 4
    # No record has empty state_before_pp.
    assert s.n_empty_state_before == 0


def test_summarize_render_is_deterministic(tmp_path: Path) -> None:
    rows = [
        TacticTrace(
            file="a.lean",
            enclosing_decl="X",
            enclosing_kind="theorem",
            enclosing_signature=None,
            line_start=1, line_end=1, column_start=0, column_end=5,
            tactic="apply foo",
            annotated_tactic="apply <a>foo</a>",
            state_before_pp="⊢ p",
            state_after_pp="no goals",
            premises=[Premise(full_name="foo")],
            trace_index=0,
        ),
        TacticTrace(
            file="a.lean",
            enclosing_decl="X",
            enclosing_kind="theorem",
            enclosing_signature=None,
            line_start=2, line_end=2, column_start=0, column_end=5,
            tactic="exact bar",
            annotated_tactic="",
            state_before_pp="",
            state_after_pp="no goals",
            premises=[],
            trace_index=1,
        ),
    ]
    out = tmp_path / "t.jsonl"
    write_jsonl(out, rows)
    rendered = summarize(out).render()
    assert "Trace summary" in rendered
    assert "tactic invocations:     2" in rendered
    assert "empty state_before_pp:  1" in rendered
    assert "zero-premise tactics:   1" in rendered
    assert "with annotated_tactic:  1" in rendered
    assert "apply=1" in rendered
    assert "exact=1" in rendered

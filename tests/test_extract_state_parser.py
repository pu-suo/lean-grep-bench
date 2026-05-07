from __future__ import annotations

from leangrep_bench.extract.state_parser import (
    parse_state_before,
    render_goal_text,
)


def test_single_goal() -> None:
    pp = "h : a = b\nk : Nat\n⊢ a = b"
    parsed = parse_state_before(pp)
    assert parsed is not None
    assert parsed.hypotheses == ["h : a = b", "k : Nat"]
    assert parsed.target == "a = b"


def test_multi_goal_takes_first_with_its_case_hypotheses() -> None:
    pp = (
        "case h.mp\n"
        "h1 : p\n"
        "⊢ q\n"
        "\n"
        "case h.mpr\n"
        "h2 : q\n"
        "⊢ p"
    )
    parsed = parse_state_before(pp)
    assert parsed is not None
    assert parsed.hypotheses == ["h1 : p"]
    assert parsed.target == "q"


def test_no_goal_marker_returns_none() -> None:
    assert parse_state_before("no goals") is None


def test_empty_pp_returns_none() -> None:
    assert parse_state_before("") is None
    assert parse_state_before("   \n  ") is None


def test_target_spans_continuation_lines() -> None:
    pp = "h : Nat\n⊢ a + b\n  + c = d"
    parsed = parse_state_before(pp)
    assert parsed is not None
    assert parsed.target == "a + b + c = d"


def test_render_goal_text_truncates_long_target() -> None:
    long = "x" * 5000
    rendered = render_goal_text(long, max_chars=100)
    assert rendered.startswith("⊢ ")
    assert rendered.endswith("[truncated]")
    assert len(rendered) <= len("⊢ ") + 100


def test_render_goal_text_short_pass_through() -> None:
    assert render_goal_text("a = b") == "⊢ a = b"


def test_let_binding_hypothesis_is_kept_intact() -> None:
    pp = "A : Finset Nat := {1, 2}\n⊢ A.Nonempty"
    parsed = parse_state_before(pp)
    assert parsed is not None
    assert parsed.hypotheses == ["A : Finset Nat := {1, 2}"]
    assert parsed.target == "A.Nonempty"

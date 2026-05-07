from __future__ import annotations

from typing import Any

from leangrep_bench.dojo.model import Premise, TacticTrace
from leangrep_bench.extract.head_premise import pick_head_premise


def _trace(annotated: str, premises: list[str], **overrides: Any) -> TacticTrace:
    base: dict[str, Any] = dict(
        file="PFR/T.lean",
        enclosing_decl="t",
        enclosing_kind="theorem",
        enclosing_signature=None,
        line_start=1,
        line_end=1,
        column_start=0,
        column_end=len(annotated),
        tactic=annotated.replace("<a>", "").replace("</a>", ""),
        annotated_tactic=annotated,
        state_before_pp="⊢ True",
        state_after_pp="no goals",
        premises=[Premise(full_name=p) for p in premises],
        trace_index=0,
    )
    base.update(overrides)
    return TacticTrace(**base)


def test_simple_apply_picks_first_annotated() -> None:
    t = _trace("apply <a>foo</a> arg", ["Some.foo"])
    r = pick_head_premise(t)
    assert r.premise is not None
    assert r.premise.full_name == "Some.foo"


def test_dot_chain_picks_outermost_in_chain() -> None:
    t = _trace(
        "apply (h.trans <a>X</a>).<a>trans</a>",
        ["X", "LE.le.trans"],
    )
    r = pick_head_premise(t)
    assert r.premise is not None
    assert r.premise.full_name == "LE.le.trans"


def test_qualified_annotation_exact_match() -> None:
    t = _trace("apply <a>Nat.add_comm</a> a b", ["Nat.add_comm"])
    r = pick_head_premise(t)
    assert r.premise is not None
    assert r.premise.full_name == "Nat.add_comm"


def test_anonymous_constructor_skips() -> None:
    t = _trace("exact ⟨<a>foo</a>, <a>bar</a>⟩", ["X.foo", "X.bar"])
    r = pick_head_premise(t)
    assert r.premise is None
    assert r.skip_reason == "no_head_token"


def test_local_hypothesis_only_skips() -> None:
    t = _trace("apply h.trans", [])
    r = pick_head_premise(t)
    assert r.premise is None
    assert r.skip_reason == "no_head_token"


def test_no_kind_token_skips() -> None:
    t = _trace("simp [foo]", [])
    r = pick_head_premise(t)
    assert r.premise is None
    assert r.skip_reason == "no_head_token"


def test_bullet_prefix_is_stripped() -> None:
    t = _trace("· apply <a>foo</a>", ["Mod.foo"])
    r = pick_head_premise(t)
    assert r.premise is not None
    assert r.premise.full_name == "Mod.foo"


def test_explicit_at_marker_is_stripped() -> None:
    t = _trace("apply @<a>foo</a> _ _", ["Mod.foo"])
    r = pick_head_premise(t)
    assert r.premise is not None
    assert r.premise.full_name == "Mod.foo"


def test_ambiguous_suffix_match_skips() -> None:
    t = _trace(
        "apply (h.trans <a>X</a>).<a>trans</a>",
        ["X", "LE.le.trans", "Eq.trans"],
    )
    r = pick_head_premise(t)
    assert r.premise is None
    assert r.skip_reason == "ambiguous_head"


def test_exact_match_wins_over_suffix_match() -> None:
    t = _trace("apply <a>trans</a>", ["trans", "LE.le.trans"])
    r = pick_head_premise(t)
    assert r.premise is not None
    assert r.premise.full_name == "trans"


def test_use_kind_supported() -> None:
    t = _trace("use <a>Classical.arbitrary</a>", ["Classical.arbitrary"])
    r = pick_head_premise(t)
    assert r.premise is not None
    assert r.premise.full_name == "Classical.arbitrary"


def test_refine_kind_supported() -> None:
    t = _trace("refine <a>Or.inr</a> ?_", ["Or.inr"])
    r = pick_head_premise(t)
    assert r.premise is not None
    assert r.premise.full_name == "Or.inr"


def test_paren_chain_no_annotation_skips() -> None:
    t = _trace("apply (h.foo bar).baz", [])
    r = pick_head_premise(t)
    assert r.premise is None


def test_no_premises_with_annotation_returns_no_head_premise() -> None:
    t = _trace("apply <a>foo</a>", [])
    r = pick_head_premise(t)
    assert r.premise is None
    assert r.skip_reason == "no_head_premise"

from __future__ import annotations

from leangrep_bench.verify.ids import mint_item_id


def _base() -> dict:
    return {
        "project": "pfr",
        "goal": "a + b = b + a",
        "hypotheses": ["a : Nat", "b : Nat"],
        "prior_tactics": ["intro a", "intro b"],
        "cited_lemma_qualified_name": "Nat.add_comm",
    }


def test_id_is_deterministic() -> None:
    a = mint_item_id(**_base())
    b = mint_item_id(**_base())
    assert a == b


def test_id_format() -> None:
    out = mint_item_id(**_base())
    assert out.startswith("lgb_pfr_")
    assert len(out) == len("lgb_pfr_") + 16


def test_hypothesis_order_does_not_matter() -> None:
    a = mint_item_id(**_base())
    b = _base()
    b["hypotheses"] = list(reversed(b["hypotheses"]))
    assert a == mint_item_id(**b)


def test_prior_tactic_order_matters() -> None:
    a = mint_item_id(**_base())
    b = _base()
    b["prior_tactics"] = list(reversed(b["prior_tactics"]))
    assert a != mint_item_id(**b)


def test_changing_cited_lemma_changes_id() -> None:
    a = mint_item_id(**_base())
    b = _base()
    b["cited_lemma_qualified_name"] = "Nat.mul_comm"
    assert a != mint_item_id(**b)


def test_project_is_part_of_id() -> None:
    a = mint_item_id(**_base())
    b = _base()
    b["project"] = "pnt"
    out = mint_item_id(**b)
    assert out.startswith("lgb_pnt_")
    assert a != out


def test_unicode_hypotheses_supported() -> None:
    args = _base()
    args["hypotheses"] = ["α : Type", "x : α"]
    out = mint_item_id(**args)
    assert out.startswith("lgb_pfr_")

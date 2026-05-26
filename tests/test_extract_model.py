from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from leangrep_bench.extract.model import (
    ProofStep,
    read_jsonl,
    read_jsonl_raw,
    write_jsonl,
)


def _step(**overrides: Any) -> ProofStep:
    base: dict[str, Any] = dict(
        id="pfr_step_00000",
        source_file="PFR/HomPFR.lean",
        line=42,
        column=2,
        tactic_kind="apply",
        cited_name="Nat.add_comm",
        cited_source="mathlib",
        enclosing_decl="PFR.helper",
        enclosing_signature="(x : Nat) : x = x",
        goal_text="⊢ a + b = b + a",
        hypotheses=["a : Nat", "b : Nat"],
        prior_tactics=["intro a", "intro b"],
        raw_tactic_line="apply Nat.add_comm",
    )
    base.update(overrides)
    return ProofStep(**base)


def test_jsonl_round_trip(tmp_path: Path) -> None:
    rows = [
        _step(),
        _step(id="pfr_step_00001", tactic_kind="exact", cited_name="rfl"),
    ]
    out = tmp_path / "steps.jsonl"
    n = write_jsonl(out, rows)
    assert n == 2
    loaded = list(read_jsonl(out))
    assert loaded == rows


def test_extra_fields_are_ignored() -> None:
    payload = _step().model_dump()
    payload["mystery_field"] = "ok"
    parsed = ProofStep.model_validate(payload)
    assert parsed == _step()


def test_missing_required_field_raises_with_field_name() -> None:
    payload = _step().model_dump()
    del payload["cited_name"]
    with pytest.raises(ValidationError) as ei:
        ProofStep.model_validate(payload)
    assert "cited_name" in str(ei.value)


def test_read_jsonl_raw_skips_validation(tmp_path: Path) -> None:
    out = tmp_path / "steps.jsonl"
    out.write_text('{"id":"x","not_a_real_field":1}\n', encoding="utf-8")
    rows = list(read_jsonl_raw(out))
    assert rows == [{"id": "x", "not_a_real_field": 1}]

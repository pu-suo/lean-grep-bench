from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from leangrep_bench.dojo.model import (
    Premise,
    TacticTrace,
    read_jsonl,
    read_jsonl_raw,
    write_jsonl,
)


def _trace(**overrides: Any) -> TacticTrace:
    base: dict[str, Any] = dict(
        file="PFR/Tactic.lean",
        enclosing_decl="PFR.helper",
        enclosing_kind="theorem",
        enclosing_signature="(x : Nat) : x = x",
        line_start=10,
        line_end=10,
        column_start=2,
        column_end=20,
        tactic="apply Nat.add_comm",
        annotated_tactic="apply <a>Nat.add_comm</a>",
        state_before_pp="⊢ a + b = b + a",
        state_after_pp="no goals",
        premises=[
            Premise(
                full_name="Nat.add_comm",
                def_path="Mathlib/Data/Nat/Basic.lean",
                def_line=42,
            )
        ],
        trace_index=0,
    )
    base.update(overrides)
    return TacticTrace(**base)


def test_jsonl_round_trip(tmp_path: Path) -> None:
    rows = [_trace(), _trace(trace_index=1, tactic="exact rfl", premises=[])]
    out = tmp_path / "traces.jsonl"
    n = write_jsonl(out, rows)
    assert n == 2
    loaded = list(read_jsonl(out))
    assert loaded == rows


def test_extra_fields_are_ignored() -> None:
    """``ConfigDict(extra="ignore")`` lets the loader tolerate fields the
    trace box might capture beyond what the Mac-side schema knows about."""
    payload = _trace().model_dump()
    payload["mystery_field"] = "ok"
    parsed = TacticTrace.model_validate(payload)
    assert parsed == _trace()


def test_missing_required_field_raises_with_field_name() -> None:
    payload = _trace().model_dump()
    del payload["state_before_pp"]
    with pytest.raises(ValidationError) as ei:
        TacticTrace.model_validate(payload)
    assert "state_before_pp" in str(ei.value)


def test_premise_optional_fields_default_to_none() -> None:
    p = Premise(full_name="Foo.bar")
    assert p.def_path is None
    assert p.def_line is None


def test_read_jsonl_raw_skips_validation(tmp_path: Path) -> None:
    out = tmp_path / "traces.jsonl"
    out.write_text(
        '{"file":"x.lean","not_a_real_field":1}\n', encoding="utf-8"
    )
    rows = list(read_jsonl_raw(out))
    assert rows == [{"file": "x.lean", "not_a_real_field": 1}]

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from leangrep_bench.corpus.model import (
    NormalizedDeclaration,
    read_jsonl,
    write_jsonl,
)


def _sample_decl() -> NormalizedDeclaration:
    return NormalizedDeclaration(
        id="mathlib::Foo.bar",
        source="mathlib",
        qualified_name="Foo.bar",
        name="bar",
        namespace="Foo",
        kind="theorem",
        signature="(x : Nat) : x = x",
        docstring="The classic identity lemma.",
        informal=None,
        file="Mathlib/Foo.lean",
        line=42,
        has_complete_info=True,
        missing_fields=[],
    )


def test_jsonl_round_trip(tmp_path: Path) -> None:
    decl = _sample_decl()
    out = tmp_path / "decls.jsonl"
    n = write_jsonl(out, [decl])
    assert n == 1
    rows = list(read_jsonl(out))
    assert len(rows) == 1
    assert rows[0] == decl


def test_validation_rejects_missing_fields() -> None:
    with pytest.raises(ValidationError):
        NormalizedDeclaration.model_validate({"id": "x"})


def test_validation_rejects_wrong_types() -> None:
    base = _sample_decl().model_dump()
    base["line"] = "not-an-int"
    with pytest.raises(ValidationError):
        NormalizedDeclaration.model_validate(base)

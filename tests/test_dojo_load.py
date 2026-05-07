from __future__ import annotations

from pathlib import Path

import pytest

from leangrep_bench.dojo.load import TraceLoadError, iter_traces
from leangrep_bench.dojo.model import TacticTrace, write_jsonl

FIXTURE = Path(__file__).parent / "fixtures" / "dojo_trace_sample.jsonl"


def _make_trace(file_name: str, idx: int) -> TacticTrace:
    return TacticTrace(
        file=file_name,
        enclosing_decl=f"PFR.t{idx}",
        enclosing_kind="theorem",
        enclosing_signature=None,
        line_start=10 + idx,
        line_end=10 + idx,
        column_start=0,
        column_end=10,
        tactic="exact rfl",
        annotated_tactic="",
        state_before_pp="⊢ x = x",
        state_after_pp="no goals",
        premises=[],
        trace_index=idx,
    )


def test_iter_traces_over_single_file(tmp_path: Path) -> None:
    out = tmp_path / "one.jsonl"
    write_jsonl(out, [_make_trace("a.lean", 0), _make_trace("a.lean", 1)])
    rows = list(iter_traces(out))
    assert len(rows) == 2
    assert [r.trace_index for r in rows] == [0, 1]


def test_iter_traces_over_directory_lex_order(tmp_path: Path) -> None:
    write_jsonl(tmp_path / "b.jsonl", [_make_trace("b.lean", 0)])
    write_jsonl(tmp_path / "a.jsonl", [_make_trace("a.lean", 0)])
    write_jsonl(tmp_path / "c.jsonl", [_make_trace("c.lean", 0)])
    rows = list(iter_traces(tmp_path))
    assert [r.file for r in rows] == ["a.lean", "b.lean", "c.lean"]


def test_iter_traces_skips_underscore_sidecars(tmp_path: Path) -> None:
    write_jsonl(tmp_path / "real.jsonl", [_make_trace("real.lean", 0)])
    # _progress / _failures sidecars should not be iterated.
    (tmp_path / "_progress.jsonl").write_text(
        '{"completed": []}\n', encoding="utf-8"
    )
    rows = list(iter_traces(tmp_path))
    assert len(rows) == 1
    assert rows[0].file == "real.lean"


def test_malformed_line_raises_with_path_and_lineno(tmp_path: Path) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        "\n"
        "{\"file\": \"a.lean\", incomplete\n",
        encoding="utf-8",
    )
    with pytest.raises(TraceLoadError) as ei:
        list(iter_traces(bad))
    msg = str(ei.value)
    assert "bad.jsonl" in msg
    assert ":2" in msg


def test_validation_error_raises_with_path_and_lineno(tmp_path: Path) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        '{"file":"a.lean","enclosing_decl":"x","enclosing_kind":"theorem"}\n',
        encoding="utf-8",
    )
    with pytest.raises(TraceLoadError) as ei:
        list(iter_traces(bad))
    msg = str(ei.value)
    assert "bad.jsonl:1" in msg


def test_missing_path_raises_filenotfound(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        list(iter_traces(tmp_path / "does_not_exist.jsonl"))


def test_iter_traces_loads_real_fixture() -> None:
    rows = list(iter_traces(FIXTURE))
    assert len(rows) == 5
    files = {r.file for r in rows}
    assert "PFR/Tactic.lean" in files
    assert "PFR/ForMathlib/Entropy.lean" in files

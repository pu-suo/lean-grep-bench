from __future__ import annotations

from pathlib import Path
from typing import Any

from leangrep_bench.dojo.model import Premise, TacticTrace, write_jsonl
from leangrep_bench.extract.extractor import extract_proof_steps
from leangrep_bench.extract.index import CorpusEntry, CorpusIndex
from leangrep_bench.extract.model import read_jsonl


def _trace(**overrides: Any) -> TacticTrace:
    base: dict[str, Any] = dict(
        file="PFR/T.lean",
        enclosing_decl="PFR.helper",
        enclosing_kind="theorem",
        enclosing_signature=None,
        line_start=10,
        line_end=10,
        column_start=2,
        column_end=20,
        tactic="apply Nat.add_comm",
        annotated_tactic="apply <a>Nat.add_comm</a>",
        state_before_pp="a b : Nat\n⊢ a + b = b + a",
        state_after_pp="no goals",
        premises=[Premise(full_name="Nat.add_comm")],
        trace_index=0,
    )
    base.update(overrides)
    return TacticTrace(**base)


def _index() -> CorpusIndex:
    return CorpusIndex(
        [
            CorpusEntry(
                qualified_name="Nat.add_comm",
                short_name="add_comm",
                namespace="Nat",
                signature="(a b : Nat) : a + b = b + a",
                source="mathlib",
            ),
            CorpusEntry(
                qualified_name="PFR.helper",
                short_name="helper",
                namespace="PFR",
                signature="(a b : Nat) : a + b = b + a",
                source="pfr",
            ),
            CorpusEntry(
                qualified_name="Some.short",
                short_name="short",
                namespace="Some",
                signature="too short",
                source="mathlib",
            ),
            CorpusEntry(
                qualified_name="rfl",
                short_name="rfl",
                namespace=None,
                signature="just enough chars to clear minimum",
                source="mathlib",
            ),
        ]
    )


def test_extract_apply_keeps_step(tmp_path: Path) -> None:
    trace_path = tmp_path / "t.jsonl"
    write_jsonl(trace_path, [_trace()])
    out = tmp_path / "steps.jsonl"

    summary = extract_proof_steps(trace_path, index=_index(), out_path=out)
    assert summary.kept == 1
    assert summary.tactic_invocations == 1
    assert summary.by_tactic["apply"] == 1
    assert summary.by_source["mathlib"] == 1

    [step] = list(read_jsonl(out))
    assert step.tactic_kind == "apply"
    assert step.cited_name == "Nat.add_comm"
    assert step.cited_source == "mathlib"
    assert step.enclosing_decl == "PFR.helper"
    assert step.enclosing_signature == "(a b : Nat) : a + b = b + a"
    assert step.goal_text == "⊢ a + b = b + a"
    assert step.hypotheses == ["a b : Nat"]
    assert step.raw_tactic_line == "apply Nat.add_comm"


def test_skip_non_target_tactic(tmp_path: Path) -> None:
    trace_path = tmp_path / "t.jsonl"
    write_jsonl(
        trace_path,
        [_trace(tactic="rw [foo]", annotated_tactic="rw [<a>foo</a>]")],
    )
    out = tmp_path / "steps.jsonl"

    summary = extract_proof_steps(trace_path, index=_index(), out_path=out)
    assert summary.kept == 0
    assert summary.tactic_invocations == 0


def test_skip_no_head_token(tmp_path: Path) -> None:
    trace_path = tmp_path / "t.jsonl"
    write_jsonl(
        trace_path,
        [
            _trace(
                tactic="exact ⟨1, 2⟩",
                annotated_tactic="exact ⟨1, 2⟩",
                premises=[],
            )
        ],
    )
    out = tmp_path / "steps.jsonl"
    summary = extract_proof_steps(trace_path, index=_index(), out_path=out)
    assert summary.kept == 0
    assert summary.skipped["no_head_token"] == 1


def test_skip_unresolved_to_corpus(tmp_path: Path) -> None:
    trace_path = tmp_path / "t.jsonl"
    write_jsonl(
        trace_path,
        [
            _trace(
                tactic="apply Mystery.lemma",
                annotated_tactic="apply <a>Mystery.lemma</a>",
                premises=[Premise(full_name="Mystery.lemma")],
            )
        ],
    )
    out = tmp_path / "steps.jsonl"
    summary = extract_proof_steps(trace_path, index=_index(), out_path=out)
    assert summary.kept == 0
    assert summary.skipped["unresolved_to_corpus"] == 1


def test_skip_blocklisted_short_name(tmp_path: Path) -> None:
    trace_path = tmp_path / "t.jsonl"
    write_jsonl(
        trace_path,
        [
            _trace(
                tactic="exact rfl",
                annotated_tactic="exact <a>rfl</a>",
                premises=[Premise(full_name="rfl")],
            )
        ],
    )
    out = tmp_path / "steps.jsonl"
    summary = extract_proof_steps(trace_path, index=_index(), out_path=out)
    assert summary.kept == 0
    assert summary.skipped["blocklisted"] == 1


def test_skip_signature_too_short(tmp_path: Path) -> None:
    trace_path = tmp_path / "t.jsonl"
    write_jsonl(
        trace_path,
        [
            _trace(
                tactic="apply Some.short",
                annotated_tactic="apply <a>Some.short</a>",
                premises=[Premise(full_name="Some.short")],
            )
        ],
    )
    out = tmp_path / "steps.jsonl"
    summary = extract_proof_steps(trace_path, index=_index(), out_path=out)
    assert summary.kept == 0
    assert summary.skipped["signature_too_short"] == 1


def test_prior_tactics_track_preceding_tactics(tmp_path: Path) -> None:
    traces = [
        _trace(
            trace_index=0,
            tactic="intro a",
            annotated_tactic="intro a",
            premises=[],
        ),
        _trace(
            trace_index=1,
            tactic="intro b",
            annotated_tactic="intro b",
            premises=[],
        ),
        _trace(trace_index=2),
    ]
    trace_path = tmp_path / "t.jsonl"
    write_jsonl(trace_path, traces)
    out = tmp_path / "steps.jsonl"

    summary = extract_proof_steps(trace_path, index=_index(), out_path=out)
    assert summary.kept == 1
    [step] = list(read_jsonl(out))
    assert step.prior_tactics == ["intro a", "intro b"]


def test_prior_tactics_reset_across_decls(tmp_path: Path) -> None:
    traces = [
        _trace(
            enclosing_decl="PFR.helperA",
            trace_index=0,
            tactic="intro a",
            annotated_tactic="intro a",
            premises=[],
        ),
        _trace(enclosing_decl="PFR.helperA", trace_index=1),
        _trace(enclosing_decl="PFR.helperB", trace_index=0),
    ]
    trace_path = tmp_path / "t.jsonl"
    write_jsonl(trace_path, traces)
    out = tmp_path / "steps.jsonl"

    summary = extract_proof_steps(trace_path, index=_index(), out_path=out)
    assert summary.kept == 2
    steps = list(read_jsonl(out))
    assert steps[0].prior_tactics == ["intro a"]
    assert steps[1].prior_tactics == []


def test_summary_files_loaded_counts_distinct_source_files(tmp_path: Path) -> None:
    traces = [
        _trace(file="PFR/A.lean"),
        _trace(file="PFR/B.lean"),
        _trace(file="PFR/A.lean"),
    ]
    trace_path = tmp_path / "t.jsonl"
    write_jsonl(trace_path, traces)
    out = tmp_path / "steps.jsonl"

    summary = extract_proof_steps(trace_path, index=_index(), out_path=out)
    assert summary.trace_files_loaded == 2

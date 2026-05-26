from __future__ import annotations

import pytest

from leangrep_bench.corpus.model import NormalizedDeclaration
from leangrep_bench.corpus.scenarios import (
    CitedLemmaNotInCorpus,
    build_scenario_index,
    classify_scenario,
)

_SHA = "deadbeef" * 5  # 40 hex chars
_PROJECT = "pfr"


def _mathlib(qname: str, name: str) -> NormalizedDeclaration:
    return NormalizedDeclaration(
        id=f"mathlib::{qname}",
        source="mathlib",
        qualified_name=qname,
        name=name,
        namespace=qname.rsplit(".", 1)[0] if "." in qname else None,
        kind="theorem",
        signature="",
        docstring=None,
        informal=None,
        file="X.lean",
        line=1,
        has_complete_info=True,
        missing_fields=[],
        visible_in=[(_PROJECT, _SHA)],
    )


def _local(project: str, qname: str, name: str) -> NormalizedDeclaration:
    return NormalizedDeclaration(
        id=f"local:{project}::{qname}",
        source=f"local:{project}",
        qualified_name=qname,
        name=name,
        namespace=qname.rsplit(".", 1)[0] if "." in qname else None,
        kind="theorem",
        signature="",
        docstring=None,
        informal=None,
        file="X.lean",
        line=1,
        has_complete_info=True,
        missing_fields=[],
        visible_in=[(project, _SHA)],
    )


def test_mathlib_qname_classifies_as_mathlib_only() -> None:
    corpus = [_mathlib("Nat.add_comm", "add_comm")]
    idx = build_scenario_index(corpus)
    assert (
        classify_scenario(
            project=_PROJECT,
            mathlib_sha=_SHA,
            cited_lemma_qualified_name="Nat.add_comm",
            index=idx,
        )
        == "mathlib_only"
    )


def test_local_qname_without_short_collision_is_local_only() -> None:
    corpus = [
        _mathlib("Nat.add_comm", "add_comm"),
        _local(_PROJECT, "tau_strictly_decreases", "tau_strictly_decreases"),
    ]
    idx = build_scenario_index(corpus)
    assert (
        classify_scenario(
            project=_PROJECT,
            mathlib_sha=_SHA,
            cited_lemma_qualified_name="tau_strictly_decreases",
            index=idx,
        )
        == "local_only"
    )


def test_local_qname_with_short_collision_is_mixed() -> None:
    # Mathlib has Nat.add_comm; PFR redefines a top-level add_comm.
    # Short name 'add_comm' is shared.
    corpus = [
        _mathlib("Nat.add_comm", "add_comm"),
        _local(_PROJECT, "add_comm", "add_comm"),
    ]
    idx = build_scenario_index(corpus)
    assert (
        classify_scenario(
            project=_PROJECT,
            mathlib_sha=_SHA,
            cited_lemma_qualified_name="add_comm",
            index=idx,
        )
        == "mixed"
    )


def test_local_qname_dotted_with_short_collision_is_mixed() -> None:
    # PFR defines Foo.add_comm; Mathlib has Nat.add_comm. The short names
    # collide ('add_comm') so the PFR-cited Foo.add_comm is mixed.
    corpus = [
        _mathlib("Nat.add_comm", "add_comm"),
        _local(_PROJECT, "Foo.add_comm", "add_comm"),
    ]
    idx = build_scenario_index(corpus)
    assert (
        classify_scenario(
            project=_PROJECT,
            mathlib_sha=_SHA,
            cited_lemma_qualified_name="Foo.add_comm",
            index=idx,
        )
        == "mixed"
    )


def test_unknown_cited_raises() -> None:
    corpus = [_mathlib("Nat.add_comm", "add_comm")]
    idx = build_scenario_index(corpus)
    with pytest.raises(CitedLemmaNotInCorpus):
        classify_scenario(
            project=_PROJECT,
            mathlib_sha=_SHA,
            cited_lemma_qualified_name="some.nonexistent.lemma",
            index=idx,
        )


def test_qname_in_both_mathlib_and_local_is_mixed_not_mathlib_only() -> None:
    # Models PFR's ForMathlib staging directory: the project locally
    # declares a lemma whose fully-qualified name also exists upstream in
    # Mathlib. v2 spec: mathlib_only requires the qname to resolve
    # *uniquely* to a Mathlib decl. Here it doesn't, so the item is mixed.
    corpus = [
        _mathlib("ProbabilityTheory.IdentDistrib.prodMk", "prodMk"),
        _local(_PROJECT, "ProbabilityTheory.IdentDistrib.prodMk", "prodMk"),
    ]
    idx = build_scenario_index(corpus)
    assert (
        classify_scenario(
            project=_PROJECT,
            mathlib_sha=_SHA,
            cited_lemma_qualified_name="ProbabilityTheory.IdentDistrib.prodMk",
            index=idx,
        )
        == "mixed"
    )


def test_classifier_is_per_project() -> None:
    # A local decl from project A is not visible to project B's classifier.
    corpus = [
        _mathlib("Nat.add_comm", "add_comm"),
        _local("pfr", "tau_strictly_decreases", "tau_strictly_decreases"),
        _local("pnt", "prime_counting_function", "prime_counting_function"),
    ]
    idx = build_scenario_index(corpus)

    assert (
        classify_scenario(
            project="pnt",
            mathlib_sha=_SHA,
            cited_lemma_qualified_name="prime_counting_function",
            index=idx,
        )
        == "local_only"
    )
    # PFR project context cannot resolve PNT's local lemma.
    with pytest.raises(CitedLemmaNotInCorpus):
        classify_scenario(
            project="pfr",
            mathlib_sha=_SHA,
            cited_lemma_qualified_name="prime_counting_function",
            index=idx,
        )


def test_classifier_is_per_mathlib_sha() -> None:
    other_sha = "feedface" * 5
    corpus = [
        NormalizedDeclaration(
            id="mathlib::Nat.add_comm",
            source="mathlib",
            qualified_name="Nat.add_comm",
            name="add_comm",
            namespace="Nat",
            kind="theorem",
            signature="",
            docstring=None,
            informal=None,
            file="X.lean",
            line=1,
            has_complete_info=True,
            missing_fields=[],
            visible_in=[(_PROJECT, _SHA)],  # only visible to _SHA
        ),
    ]
    idx = build_scenario_index(corpus)
    # Under another mathlib_sha, the lemma is invisible: not classifiable.
    with pytest.raises(CitedLemmaNotInCorpus):
        classify_scenario(
            project=_PROJECT,
            mathlib_sha=other_sha,
            cited_lemma_qualified_name="Nat.add_comm",
            index=idx,
        )

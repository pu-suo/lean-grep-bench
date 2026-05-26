"""Coverage for :class:`CorpusIndex` name resolution.

These tests pin the precedence rules ``resolve()`` uses to reconstruct
qualified names when LeanDojo-v2 hands back a short form. The recovery
logic is what closes the local/mathlib citation gap that opened when we
moved from LeanDojo-v1 (elaborated full names) to LeanDojo-v2 (as-written
names).
"""

from __future__ import annotations

from leangrep_bench.extract.index import CorpusEntry, CorpusIndex


def _entry(qualified_name: str, source: str = "mathlib") -> CorpusEntry:
    short = qualified_name.split(".")[-1]
    namespace = (
        ".".join(qualified_name.split(".")[:-1])
        if "." in qualified_name
        else None
    )
    return CorpusEntry(
        qualified_name=qualified_name,
        short_name=short,
        namespace=namespace,
        signature="signature placeholder",
        source=source,
    )


def test_resolve_qualified_hits_fast_path() -> None:
    idx = CorpusIndex([_entry("Real.log_nonneg"), _entry("Nat.add_comm")])
    e = idx.resolve("Real.log_nonneg")
    assert e is not None
    assert e.qualified_name == "Real.log_nonneg"


def test_resolve_short_unique_falls_back_when_qualified_missing() -> None:
    # LeanDojo-v2 hands us bare ``log_nonneg``; the corpus only knows
    # ``Real.log_nonneg``. With a unique short name, the lookup succeeds.
    idx = CorpusIndex([_entry("Real.log_nonneg"), _entry("Nat.add_comm")])
    e = idx.resolve("log_nonneg")
    assert e is not None
    assert e.qualified_name == "Real.log_nonneg"


def test_resolve_short_ambiguous_without_namespace_is_unresolved() -> None:
    # Two ``le_trans`` candidates. With no enclosing context the lookup
    # refuses to guess — picking arbitrarily would corrupt the ground truth.
    idx = CorpusIndex(
        [
            _entry("Preorder.le_trans"),
            _entry("Real.le_trans"),
        ]
    )
    assert idx.resolve("le_trans") is None


def test_resolve_namespace_tiebreaker_picks_enclosing() -> None:
    # Inside ``BKLNW.table_14_check``, a bare ``check_row_prop_of_bounds``
    # should resolve to ``BKLNW.check_row_prop_of_bounds`` even though there
    # is no unique short-name match (another ``check_row_prop_of_bounds``
    # exists in a different namespace).
    idx = CorpusIndex(
        [
            _entry("BKLNW.check_row_prop_of_bounds", source="local:pnt"),
            _entry("Other.check_row_prop_of_bounds", source="mathlib"),
        ]
    )
    e = idx.resolve(
        "check_row_prop_of_bounds",
        enclosing_decl="BKLNW.table_14_check",
    )
    assert e is not None
    assert e.qualified_name == "BKLNW.check_row_prop_of_bounds"


def test_resolve_namespace_walks_innermost_first() -> None:
    # Lean's identifier resolution looks at the innermost enclosing namespace
    # first. With ``enclosing_decl="A.B.C.thm"``, a bare ``foo`` should
    # prefer ``A.B.C.foo`` over ``A.B.foo`` if both exist.
    idx = CorpusIndex(
        [
            _entry("A.foo"),
            _entry("A.B.foo"),
            _entry("A.B.C.foo"),
        ]
    )
    e = idx.resolve("foo", enclosing_decl="A.B.C.thm")
    assert e is not None
    assert e.qualified_name == "A.B.C.foo"


def test_resolve_namespace_falls_through_when_inner_missing() -> None:
    # ``A.B.C.foo`` doesn't exist; the resolver should walk outward and
    # accept ``A.B.foo``.
    idx = CorpusIndex([_entry("A.B.foo"), _entry("A.foo")])
    e = idx.resolve("foo", enclosing_decl="A.B.C.thm")
    assert e is not None
    assert e.qualified_name == "A.B.foo"


def test_resolve_missing_name_returns_none() -> None:
    idx = CorpusIndex([_entry("Real.log_nonneg")])
    assert idx.resolve("never_in_corpus", enclosing_decl="A.thm") is None

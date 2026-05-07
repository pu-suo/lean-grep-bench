from __future__ import annotations

from leangrep_bench.corpus.to_additive import (
    apply_name_dict,
    guess_name,
    parse_to_additive_attr,
    split_case,
)


def test_split_case_underscore_lowercase() -> None:
    assert split_case("prod_congr") == ["prod", "_", "congr"]
    assert split_case("mul_le_mul") == ["mul", "_", "le", "_", "mul"]


def test_split_case_camelcase() -> None:
    assert split_case("MulOneClass") == ["Mul", "One", "Class"]
    # Lean's splitCase only splits on lowercase→uppercase, so consecutive
    # uppercase runs stay intact. ``HMul`` and ``ABCdef`` are single tokens.
    assert split_case("HMul") == ["HMul"]
    assert split_case("ABCdef") == ["ABCdef"]
    # And one with a real internal split.
    assert split_case("HMulLE") == ["HMul", "LE"]


def test_apply_name_dict_basic() -> None:
    # prod_congr → applyNameDict produces ["sum", "_", "congr"]
    out = apply_name_dict(["prod", "_", "congr"])
    assert out == ["sum", "_", "congr"]


def test_apply_name_dict_capitalized() -> None:
    # Camelcase preservation: "Mul" → "Add"
    out = apply_name_dict(["Mul", "One", "Class"])
    assert out == ["Add", "Zero", "Class"]


def test_apply_name_dict_monoid_expands_to_two_tokens() -> None:
    # ``monoid`` is mapped to ``["Add", "Monoid"]`` in nameDict; because the
    # source token is lowercase, the first replacement word is decapitalized.
    out = apply_name_dict(["monoid"])
    assert out == ["add", "Monoid"]
    # Capitalized form keeps the original casing of the first replacement.
    out_upper = apply_name_dict(["Monoid"])
    assert out_upper == ["Add", "Monoid"]


def test_guess_name_prod_congr() -> None:
    assert guess_name("prod_congr") == "sum_congr"


def test_guess_name_mul_le_mul() -> None:
    assert guess_name("mul_le_mul") == "add_le_add"


def test_guess_name_prod_eq_one() -> None:
    assert guess_name("prod_eq_one") == "sum_eq_zero"


def test_guess_name_apostrophe_preserved() -> None:
    # to_additive applies the algorithm separately on each segment of
    # an apostrophe-split name, then re-joins with apostrophes.
    assert guess_name("prod_congr'") == "sum_congr'"


def test_guess_name_unknown_word_unchanged() -> None:
    # ``foo_bar`` has no entries in either dict, so no change.
    assert guess_name("foo_bar") == "foo_bar"


def test_parse_to_additive_bare() -> None:
    assert parse_to_additive_attr("to_additive") == (True, None)


def test_parse_to_additive_with_explicit_name() -> None:
    assert parse_to_additive_attr("to_additive add_le_add") == (True, "add_le_add")


def test_parse_to_additive_with_attr_clause_then_name() -> None:
    body = "to_additive (attr := gcongr high) add_le_add"
    assert parse_to_additive_attr(body) == (True, "add_le_add")


def test_parse_to_additive_with_only_attr_clause() -> None:
    assert parse_to_additive_attr("to_additive (attr := simp)") == (True, None)


def test_parse_to_additive_with_existing_then_name() -> None:
    assert parse_to_additive_attr("to_additive existing some_name") == (
        True,
        "some_name",
    )


def test_parse_to_additive_inside_compound_attribute() -> None:
    # A compound ``@[simp, to_additive sum_le_sum]`` — outer parser calls
    # us with the whole bracket payload; we should still find the clause.
    assert parse_to_additive_attr("simp, to_additive sum_le_sum") == (
        True,
        "sum_le_sum",
    )


def test_parse_to_additive_absent() -> None:
    assert parse_to_additive_attr("simp") == (False, None)
    assert parse_to_additive_attr("inline, reducible") == (False, None)

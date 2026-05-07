"""Synthesize the additive twin of a ``@[to_additive]``-decorated declaration.

`to_additive` is Mathlib's macro that, for every multiplicative theorem
(`prod_congr`, `mul_le_mul`, …) generates an additive twin (`sum_congr`,
`add_le_add`, …) at elaboration time. The twin never appears in the source
file as a literal `theorem` line, so the regex-based corpus parser can't
see it. This module reproduces enough of Mathlib's name-guessing logic to
emit twin entries from source-level scanning alone.

Reference: ``Mathlib/Tactic/Translate/ToAdditive.lean`` (the ``nameDict``
and ``abbreviationDict`` tables) and ``Mathlib/Tactic/Translate/GuessName.lean``
(the ``splitCase`` / ``applyNameDict`` / ``fixAbbreviation`` pipeline). Both
are copied here verbatim and translated into Python; keep them in sync if
Mathlib's tables drift.
"""

from __future__ import annotations

import re

# --- nameDict -------------------------------------------------------------
# Copied from `Mathlib/Tactic/Translate/ToAdditive.lean:288`.
_NAME_DICT: dict[str, list[str]] = {
    "one": ["Zero"],
    "mul": ["Add"],
    "smul": ["VAdd"],
    "inv": ["Neg"],
    "div": ["Sub"],
    "prod": ["Sum"],
    "hmul": ["HAdd"],
    "hsmul": ["HVAdd"],
    "hdiv": ["HSub"],
    "hpow": ["HSMul"],
    "finprod": ["Finsum"],
    "tprod": ["TSum"],
    "pow": ["NSMul"],
    "npow": ["NSMul"],
    "zpow": ["ZSMul"],
    "mabs": ["Abs"],
    "monoid": ["Add", "Monoid"],
    "submonoid": ["Add", "Submonoid"],
    "group": ["Add", "Group"],
    "subgroup": ["Add", "Subgroup"],
    "semigroup": ["Add", "Semigroup"],
    "magma": ["Add", "Magma"],
    "haar": ["Add", "Haar"],
    "prehaar": ["Add", "Prehaar"],
    "unit": ["Add", "Unit"],
    "units": ["Add", "Units"],
    "cyclic": ["Add", "Cyclic"],
    "semigrp": ["Add", "Semigrp"],
    "grp": ["Add", "Grp"],
    "commute": ["Add", "Commute"],
    "semiconj": ["Add", "Semiconj"],
    "conjugates": ["Add", "Conjugates"],
    "conj": ["Add", "Conj"],
    "commutator": ["Add", "Commutator"],
    "rootable": ["Divisible"],
    "zpowers": ["ZMultiples"],
    "powers": ["Multiples"],
    "multipliable": ["Summable"],
    "gpfree": ["APFree"],
    "quantale": ["Add", "Quantale"],
    "square": ["Even"],
    "mconv": ["Conv"],
    "irreducible": ["Add", "Irreducible"],
    "mlconvolution": ["LConvolution"],
}

# --- abbreviationDict -----------------------------------------------------
# Copied from `Mathlib/Tactic/Translate/ToAdditive.lean:335`.
_ABBREV_DICT: dict[str, str] = {
    "isCancelAdd": "IsCancelAdd",
    "isLeftCancelAdd": "IsLeftCancelAdd",
    "isRightCancelAdd": "IsRightCancelAdd",
    "cancelAdd": "AddCancel",
    "leftCancelAdd": "AddLeftCancel",
    "rightCancelAdd": "AddRightCancel",
    "cancelCommAdd": "AddCancelComm",
    "commAdd": "AddComm",
    "zero_le": "Nonneg",
    "zeroLE": "Nonneg",
    "zero_lt": "Pos",
    "zeroLT": "Pos",
    "lezero": "Nonpos",
    "le_zero": "Nonpos",
    "ltzero": "Neg",
    "lt_zero": "Neg",
    "addSingle": "Single",
    "addSupport": "Support",
    "addTSupport": "TSupport",
    "addPointed": "Pointed",
    "addSpanning": "Spanning",
    "addIndicator": "Indicator",
    "isEven": "Even",
    "isRegular": "IsAddRegular",
    "isLeftRegular": "IsAddLeftRegular",
    "isRightRegular": "IsAddRightRegular",
    "hasFundamentalDomain": "HasAddFundamentalDomain",
    "quotientMeasure": "AddQuotientMeasure",
    "negFun": "InvFun",
    "uniqueProds": "UniqueSums",
    "orderOf": "AddOrderOf",
    "zeroLePart": "PosPart",
    "leZeroPart": "NegPart",
    "isScalarTower": "VAddAssocClass",
    "isOfFinOrder": "IsOfFinAddOrder",
    "isCentralScalar": "IsCentralVAdd",
    "function_addSemiconj": "Function_semiconj",
    "function_addCommute": "Function_commute",
    "divisionAddMonoid": "SubtractionMonoid",
    "subNegZeroAddMonoid": "SubNegZeroMonoid",
    "modularCharacter": "AddModularCharacter",
    "isQuotientCoveringMap": "IsAddQuotientCoveringMap",
    "addExact": "exact",
    "isMonHom": "IsAddMonHom",
    "mapMon": "MapAddMon",
    "monObj": "AddMonObj",
    "yonedaMon": "yonedaAddMon",
}


def split_case(s: str) -> list[str]:
    """Split an identifier on ``_`` and at lowercase→uppercase boundaries.

    Mirrors Lean's ``String.splitCase`` for the cases that show up in
    Mathlib decl names: split on ``_`` (kept as its own token) and split
    when a lowercase letter is followed by an uppercase letter. Runs of
    consecutive uppercase letters (``HMul``, ``LE``, ``ABCdef``) stay
    intact — Lean only splits on case when the *next* character is
    uppercase **and** the previous one is not, so ``HMul`` → ``["HMul"]``.

    The ``endCapitalNames`` special-cases (``LE``/``LT``/``Coe…``) are not
    reproduced; in practice they only matter for camel-case identifiers
    that contain those tokens, and the abbreviation pass downstream
    catches the few cases that fall through.
    """
    if not s:
        return []
    parts: list[str] = []
    cur: list[str] = []
    for ch in s:
        if ch == "_":
            if cur:
                parts.append("".join(cur))
                cur = []
            parts.append("_")
            continue
        if cur and cur[-1].islower() and ch.isupper():
            parts.append("".join(cur))
            cur = [ch]
            continue
        cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return parts


def _decapitalize_seq(s: str) -> str:
    """Lowercase the initial run of uppercase letters in ``s``."""
    if not s or not s[0].isupper():
        return s
    i = 0
    while i < len(s) and s[i].isupper():
        i += 1
    return s[:i].lower() + s[i:]


def _decapitalize_like(r: str, s: str) -> str:
    """If ``r`` starts uppercase, return ``s`` unchanged; else
    ``_decapitalize_seq(s)``."""
    if r and r[0].isupper():
        return s
    return _decapitalize_seq(s)


def apply_name_dict(tokens: list[str]) -> list[str]:
    """Replace each token whose lowercase form is in ``_NAME_DICT`` with
    the corresponding additive word(s), preserving the original token's
    initial casing."""
    out: list[str] = []
    for tok in tokens:
        repl = _NAME_DICT.get(tok.lower())
        if repl is None:
            out.append(tok)
            continue
        first = _decapitalize_like(tok, repl[0])
        out.append(first)
        out.extend(repl[1:])
    return out


def fix_abbreviation(tokens: list[str]) -> str:
    """Walk the token list, looking for prefix runs whose joined form
    matches an entry in ``_ABBREV_DICT``. Mirrors Lean's
    ``fixAbbreviationAux``."""
    pieces: list[str] = []
    s_acc: list[str] = []
    pending: list[str] = list(tokens)
    while pending or s_acc:
        if not pending:
            pieces.extend(s_acc)
            break
        pre = pending[0]
        rest = pending[1:]
        s = [*s_acc, pre]
        t = "".join(s)
        if pre == "_" and t and t[0].isupper():
            pieces.append(s[0])
            pending = s[1:] + rest
            s_acc = []
            continue
        post = _ABBREV_DICT.get(_decapitalize_seq(t))
        if post is not None:
            pieces.append(_decapitalize_like(t, post))
            pending = rest
            s_acc = []
            continue
        s_acc = s
        pending = rest
    return "".join(pieces)


def guess_name(name: str) -> str:
    """Return the additive twin of a multiplicative identifier name.

    Apostrophes split the name into independently-translated tokens,
    matching Lean's ``String.mapTokens '\\''``. Pass a *short* name
    (no namespace prefix); the caller is responsible for prepending
    namespaces.
    """
    parts = name.split("'")
    return "'".join(fix_abbreviation(apply_name_dict(split_case(p))) for p in parts)


# --- Attribute parsing ----------------------------------------------------

# Match the *outer* ``to_additive`` attribute (we still need to scan the
# bracket contents ourselves to skip any ``(reorder := ...)`` clauses).
_TO_ADDITIVE_RE = re.compile(r"\bto_additive\b")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_'.]*")


def parse_to_additive_attr(attr_body: str) -> tuple[bool, str | None]:
    """Parse the inner text of an ``@[...]`` attribute block.

    Returns ``(is_to_additive, explicit_name)``. The explicit name is the
    first identifier following the ``to_additive`` keyword (skipping any
    ``existing`` flag and parenthesised ``(reorder := …)`` / ``(attr := …)``
    clauses) and is ``None`` when the attribute relies on automatic
    name-mangling.

    ``attr_body`` is the raw text *between* ``@[`` and the closing ``]``
    — possibly multi-line. We may receive a comma-separated attribute list
    (``simp, to_additive name``); only the ``to_additive`` clause is
    relevant here.
    """
    m = _TO_ADDITIVE_RE.search(attr_body)
    if m is None:
        return (False, None)

    i = m.end()
    n = len(attr_body)
    while i < n:
        ch = attr_body[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "(":
            depth = 1
            i += 1
            while i < n and depth > 0:
                if attr_body[i] == "(":
                    depth += 1
                elif attr_body[i] == ")":
                    depth -= 1
                i += 1
            continue
        # Accept the (rare) ``existing`` keyword and keep scanning for
        # an explicit name following it.
        if attr_body[i : i + len("existing")] == "existing" and (
            i + len("existing") == n or not (
                attr_body[i + len("existing")].isalnum()
                or attr_body[i + len("existing")] == "_"
            )
        ):
            i += len("existing")
            continue
        if ch == "," or ch == "]":
            # The to_additive clause ended without an explicit name.
            return (True, None)
        m2 = _IDENT_RE.match(attr_body, i)
        if m2 is None:
            return (True, None)
        return (True, m2.group(0))

    return (True, None)


__all__ = [
    "apply_name_dict",
    "fix_abbreviation",
    "guess_name",
    "parse_to_additive_attr",
    "split_case",
]

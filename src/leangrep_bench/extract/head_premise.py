"""Pick the *head* premise from a LeanDojo-annotated tactic.

LeanDojo wraps each elaborated identifier in ``<a>...</a>`` inside the
``annotated_tactic`` string. The trace also carries a deduplicated
``premises`` list with each identifier's full name.

The "head" of an ``apply X`` / ``exact X`` / ``use X`` / ``refine X`` term is
the function being applied to the goal. With curried dot-chains it is the
*last* identifier in the outermost dot-chain, not the first ``<a>``:

    apply foo                                  → head = foo
    apply Namespace.foo args                   → head = Namespace.foo
    apply (X.trans foo).trans                  → head = trans (outer .trans)
    exact (foo arg).symm                       → head = symm
    exact ⟨...⟩  (anonymous constructor)       → no clear head, skip
    apply h.method                             → no head premise, skip
"""

from __future__ import annotations

from dataclasses import dataclass

from leangrep_bench.dojo.model import Premise, TacticTrace


@dataclass(frozen=True)
class HeadResolution:
    """Result of picking the head premise from a tactic."""

    premise: Premise | None
    skip_reason: str | None


_KIND_PREFIXES: tuple[str, ...] = ("apply", "exact", "use", "refine")


def pick_head_premise(trace: TacticTrace) -> HeadResolution:
    """Return the head premise of ``trace.annotated_tactic``, or a skip reason."""
    body = _strip_kind(trace.annotated_tactic)
    if body is None:
        return HeadResolution(None, "no_head_token")

    head_short = _walk_outer_chain(body)
    if head_short is None:
        return HeadResolution(None, "no_head_token")

    matches = _premises_matching(head_short, trace.premises)
    if len(matches) == 0:
        return HeadResolution(None, "no_head_premise")
    if len(matches) > 1:
        return HeadResolution(None, "ambiguous_head")
    return HeadResolution(matches[0], None)


def _strip_kind(annotated: str) -> str | None:
    """Strip the leading tactic-kind keyword. Returns the body."""
    s = annotated.lstrip()
    # Strip leading bullets that PFR uses to start a focused sub-proof, e.g.
    # ``· apply foo`` — the bullet may stack with whitespace.
    while s and s[0] in "·•‣":
        s = s[1:].lstrip()
    for kw in _KIND_PREFIXES:
        if s.startswith(kw) and (len(s) == len(kw) or not _ident_cont(s[len(kw)])):
            return s[len(kw) :].lstrip()
    return None


def _ident_cont(ch: str) -> bool:
    return ch.isalnum() or ch == "_" or ch == "'"


def _walk_outer_chain(body: str) -> str | None:
    """Walk the outermost dot-chain of the head term.

    Returns the *last* annotated short name in the chain, or ``None`` if the
    chain has no annotated atom (e.g., an anonymous constructor or a tactic
    that operates only on local hypotheses).
    """
    s = body
    if not s:
        return None
    # Anonymous constructors / structure literals have no callable head.
    if s.startswith("⟨"):
        return None

    # Strip a leading explicit-mode marker.
    if s.startswith("@"):
        s = s[1:].lstrip()

    last_a: str | None = None
    i = 0
    n = len(s)
    while i < n:
        kind, j, name = _read_atom(s, i)
        if kind == "a":
            last_a = name
        elif kind in ("p", "h"):
            # Paren or local-hypothesis atom — does not advance the head.
            pass
        else:
            break
        i = j
        # Continue walking through ``.atom`` chain; anything else terminates.
        if i < n and s[i] == ".":
            i += 1
            continue
        break
    return last_a


def _read_atom(s: str, idx: int) -> tuple[str, int, str | None]:
    """Read one atom starting at ``s[idx]``.

    Atom kinds:
      ``"a"`` — annotated identifier ``<a>...</a>``; returns the inner text.
      ``"p"`` — balanced parenthesised group ``(...)``.
      ``"h"`` — bare identifier (treated as a local hypothesis here, since
                LeanDojo would have annotated it if it were a real premise).
      ``"x"`` — none of the above; the atom reader could not advance.
    """
    n = len(s)
    if idx >= n:
        return ("x", idx, None)
    if s[idx] == "(":
        depth = 1
        j = idx + 1
        while j < n and depth > 0:
            if s[j] == "(":
                depth += 1
            elif s[j] == ")":
                depth -= 1
            j += 1
        return ("p", j, None)
    if s.startswith("<a>", idx):
        end = s.find("</a>", idx + 3)
        if end == -1:
            return ("x", idx, None)
        return ("a", end + len("</a>"), s[idx + 3 : end])
    ch = s[idx]
    if ch.isalpha() or ch == "_":
        j = idx
        while j < n and _ident_cont(s[j]):
            j += 1
        return ("h", j, s[idx:j])
    return ("x", idx, None)


def _premises_matching(short: str, premises: list[Premise]) -> list[Premise]:
    """Return premises whose ``full_name`` ends with ``short``.

    Match rules (in priority order):
      1. Exact match (``full_name == short``).
      2. Suffix match (``full_name.endswith("." + short)``).

    If any exact match exists, only exact matches are returned. This keeps
    ``trans`` from accidentally pulling in *every* ``.trans`` premise when an
    unqualified ``trans`` is the head.
    """
    exact = [p for p in premises if p.full_name == short]
    if exact:
        return exact
    suffix = "." + short
    return [p for p in premises if p.full_name.endswith(suffix)]


__all__ = ["HeadResolution", "pick_head_premise"]

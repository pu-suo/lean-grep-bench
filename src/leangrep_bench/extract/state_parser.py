"""Parse LeanDojo's ``state_before_pp`` blob into (hypotheses, target).

Lean's pretty-printer emits proof states in a regular form:

    case <name>             -- optional, present when the goal is split
    h1 : T1                 -- one hypothesis per line
    h2 : T2 := value        -- let-bindings show the bound value
    ...
    ⊢ <target>              -- the conclusion proposition; ``⊢`` (U+22A2)

For multi-goal states each goal block follows the same shape, separated by
a blank line. We only return the *first* goal: PFR proofs almost always have
a single active goal at any tactic point, and downstream prompt rendering
gets cleaner if hypotheses are not interleaved across cases.
"""

from __future__ import annotations

from dataclasses import dataclass

GOAL_MARKER = "⊢"  # ⊢


@dataclass(frozen=True)
class ParsedState:
    hypotheses: list[str]
    target: str


def parse_state_before(pp: str) -> ParsedState | None:
    """Return the first goal's (hypotheses, target).

    Returns ``None`` if the blob is empty/whitespace or does not contain a
    ``⊢`` marker (which happens for ``"no goals"`` and similar terminal
    states — those legitimately have no target to render).
    """
    if not pp.strip():
        return None
    lines = pp.split("\n")

    target_idx = next(
        (i for i, ln in enumerate(lines) if ln.lstrip().startswith(GOAL_MARKER)),
        None,
    )
    if target_idx is None:
        return None

    hyps: list[str] = []
    for raw in lines[:target_idx]:
        s = raw.strip()
        if not s:
            continue
        if s.startswith("case "):
            # Reset on a case marker so we keep the hypotheses scoped to the
            # case immediately before the target line we picked.
            hyps = []
            continue
        hyps.append(s)

    target_parts = [
        lines[target_idx].lstrip()[len(GOAL_MARKER) :].lstrip(),
    ]
    j = target_idx + 1
    while j < len(lines):
        ln = lines[j]
        s = ln.strip()
        if not s:
            break
        if s.startswith("case "):
            break
        if s.startswith(GOAL_MARKER):
            break
        target_parts.append(s)
        j += 1

    target = " ".join(p for p in target_parts if p).strip()
    return ParsedState(hypotheses=hyps, target=target)


def render_goal_text(target: str, *, max_chars: int = 2000) -> str:
    """Format the target as ``⊢ {target}`` with truncation past ``max_chars``."""
    truncated = target
    marker = " ... [truncated]"
    if len(truncated) > max_chars:
        truncated = truncated[: max_chars - len(marker)] + marker
    return f"{GOAL_MARKER} {truncated}"


__all__ = ["GOAL_MARKER", "ParsedState", "parse_state_before", "render_goal_text"]

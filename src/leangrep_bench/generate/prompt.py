"""User-prompt builder and leakage checks for query generation.

The prompt presents a redacted tactic line, the elaborated goal state,
local hypotheses, and the up-to-5 most recent prior tactics, then asks
the LLM to write a one-line natural-language search query an agent in
that proof position would send. An anti-paraphrase clause warns the
model not to mirror the goal text in its query — the leakage checks
below catch the cases where it does anyway.
"""

from __future__ import annotations

import re

from leangrep_bench.extract.model import ProofStep

REDACTION_TOKEN = "???"
GOAL_PLACEHOLDER = "(no goal available)"
GOAL_LEAKAGE_WINDOW = 30

SYSTEM_PROMPT = (
    "You are simulating an AI agent writing a Lean 4 proof. The agent has hit "
    "a point where it needs a lemma it doesn't remember the name of, and will "
    "use a search tool that takes a natural-language query. Write the query "
    "the agent would send.\n\n"
    "Output format:\n"
    "- Exactly one line: the query, in natural mathematical English.\n"
    "- 4 to 15 words. Shorter when the goal is specific.\n"
    "- Describe what the lemma says, not what it's called.\n"
    "- Do not include any Lean identifiers, namespace paths, or guesses at "
    "what the lemma might be named.\n"
    "- Do not invent identifier names."
)


def redact_tactic_line(raw: str, cited_name: str) -> str:
    """Replace every literal occurrence of ``cited_name`` (or its longest
    matching dotted-suffix form) in ``raw`` with the redaction token.

    Tries suffix forms of the qualified name longest-first. A candidate
    matches only as a maximal identifier — i.e. it can't be preceded by
    another identifier/dot character or followed by an identifier
    continuation character.
    """
    if not raw or not cited_name:
        return raw
    parts = cited_name.split(".")
    for k in range(len(parts), 0, -1):
        candidate = ".".join(parts[-k:])
        pattern = (
            r"(?<![A-Za-z0-9_.])"
            + re.escape(candidate)
            + r"(?![A-Za-z0-9_'])"
        )
        new_raw, count = re.subn(pattern, REDACTION_TOKEN, raw)
        if count > 0:
            return new_raw
    return raw


def _render_list(items: list[str]) -> str:
    if not items:
        return "(none)"
    return "\n".join(f"  - {it}" for it in items)


def build_user_prompt(step: ProofStep) -> str:
    """Render the user-side prompt for a single proof step."""
    goal = (step.goal_text or "").strip() or GOAL_PLACEHOLDER
    hyps = _render_list(step.hypotheses)
    prior = _render_list(step.prior_tactics)
    redacted = redact_tactic_line(step.raw_tactic_line, step.cited_name).strip()
    return (
        "You're trying to find a lemma to close this goal:\n\n"
        f"  {goal}\n\n"
        "The tactic you're about to write looks like this, with the lemma "
        "name hidden:\n\n"
        f"  {redacted}\n\n"
        f"Local hypotheses (what's bound in scope):\n{hyps}\n\n"
        "Prior tactics in this proof block (oldest to newest):\n"
        f"{prior}\n\n"
        f"You are inside the declaration `{step.enclosing_decl}`.\n\n"
        "Your job: write the search query an agent in this position would "
        "send. The query should describe the SHAPE of the missing lemma — "
        "what it takes as input, what it concludes — based on:\n"
        "  - the goal (what proposition the lemma must prove),\n"
        "  - the redacted tactic line (arity and argument structure),\n"
        "  - the local hypotheses (what's already known),\n"
        "  - the prior tactics (what's been done).\n\n"
        "Critical constraints:\n"
        "- Do NOT restate the goal verbatim in English. The goal might say "
        "`⊢ X.entropy ≤ Real.log (Nat.card X)` but a real search query "
        "reads more like \"entropy of finite-range variable bounded by log "
        "of cardinality.\" Translate to natural mathematical English at the "
        "level of generality a human searcher would use.\n"
        "- Do NOT include any Lean identifiers, namespace paths, or guesses "
        "at what the lemma might be named.\n"
        "- Do NOT describe the overall theorem you are inside.\n"
        "- 4 to 15 words.\n\n"
        "If the goal is genuinely closed by a very specific lemma, your "
        "query can be specific. If the goal would close under several "
        "plausible lemmas, write the narrowest plausible description of the "
        "one shape that fits the redacted tactic call.\n\n"
        "Write the search query (one line) you would send."
    )


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


def _tokens(s: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(s) if len(t) >= 3}


def cited_name_leakage_check(query: str, cited_name: str) -> bool:
    """True if the query verbatim contains the cited (qualified or short) name
    or a likely Lean-identifier rendering of it.
    """
    q = query.lower()

    # Exact substring of full or short name (case-insensitive).
    if cited_name.lower() in q:
        return True
    short = cited_name.split(".")[-1].lower()
    if len(short) >= 4 and short in q.replace(" ", "").replace("-", ""):
        return True

    # Token-level: every >=3-char component of the short name appears as a
    # word in the query. Catches `add_comm` → "add comm" or "addition is
    # commutative" only when the literal tokens reappear.
    parts = [p for p in re.split(r"[._]", cited_name.split(".")[-1]) if len(p) >= 3]
    if parts:
        q_tokens = _tokens(query)
        if all(p.lower() in q_tokens for p in parts) and len(parts) >= 2:
            return True

    return False


def _normalize_for_leakage(s: str) -> str:
    return " ".join(s.lower().split())


def goal_leakage_check(
    query: str,
    goal_text: str | None,
    *,
    window: int = GOAL_LEAKAGE_WINDOW,
) -> bool:
    """Flag queries that copy a substring of length ``window`` or more
    from the goal text. Catches LLM responses that mechanically mirror
    the goal in English instead of paraphrasing for search.

    Both strings are case-folded and whitespace-collapsed before
    comparison so trivial reformatting (extra spaces, case changes)
    doesn't dodge the check.
    """
    if not goal_text:
        return False
    q = _normalize_for_leakage(query)
    g = _normalize_for_leakage(goal_text)
    if len(q) < window or len(g) < window:
        return False
    return any(q[i : i + window] in g for i in range(len(q) - window + 1))


__all__ = [
    "GOAL_LEAKAGE_WINDOW",
    "GOAL_PLACEHOLDER",
    "REDACTION_TOKEN",
    "SYSTEM_PROMPT",
    "build_user_prompt",
    "cited_name_leakage_check",
    "goal_leakage_check",
    "redact_tactic_line",
]

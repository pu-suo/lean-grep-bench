from __future__ import annotations

import json
import re
from dataclasses import dataclass

SYSTEM_PROMPT = (
    "You judge whether a search query and a Lean 4 declaration are plausibly "
    "matched. Answer YES if a person sending this query could reasonably be "
    "hoping to find this declaration. Answer NO if the declaration does not "
    "match what the query is asking for. Be strict but not pedantic.\n\n"
    "Output exactly one JSON object on a single line:\n"
    '  {"verdict": "YES" | "NO", "reason": "<one short sentence>"}'
)

_MAX_SIGNATURE_CHARS = 1200
_MAX_DOCSTRING_CHARS = 1200


def _truncate(s: str | None, limit: int) -> str:
    if not s:
        return "(none)"
    if len(s) <= limit:
        return s
    return s[:limit].rstrip() + " …"


def build_user_prompt(
    *,
    query: str,
    qualified_name: str,
    kind: str,
    signature: str,
    docstring: str | None,
) -> str:
    sig = _truncate(signature, _MAX_SIGNATURE_CHARS)
    doc = _truncate(docstring, _MAX_DOCSTRING_CHARS)
    return (
        f"Query:\n  {query}\n\n"
        f"Declaration:\n"
        f"  Name: {qualified_name}\n"
        f"  Kind: {kind}\n"
        f"  Signature:\n    {sig}\n"
        f"  Docstring (may be empty):\n    {doc}\n\n"
        f"Is this declaration a plausible match for the query?"
    )


@dataclass(frozen=True)
class Verdict:
    is_yes: bool
    reason: str


_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_verdict(text: str) -> Verdict:
    """Parse the verifier's response. Tolerates surrounding whitespace, code
    fences, and the rare model that puts a leading paragraph before the JSON.
    Falls back to a regex-based YES/NO scan if no JSON parses.
    """
    cleaned = text.strip()

    # Strip ``` fences if present.
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline >= 0:
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3].rstrip()

    # First, try to parse the full body as JSON.
    candidates: list[str] = []
    candidates.append(cleaned)
    m = _JSON_OBJ_RE.search(cleaned)
    if m is not None:
        candidates.append(m.group(0))
    for cand in candidates:
        try:
            obj_any = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj_any, dict):
            continue
        # Cast keys/values via str() so pyright is happy with strict typing.
        verdict = str(obj_any.get("verdict", "")).strip().upper()  # type: ignore[arg-type]
        reason = str(obj_any.get("reason", "")).strip()  # type: ignore[arg-type]
        if verdict in ("YES", "NO"):
            return Verdict(is_yes=verdict == "YES", reason=reason or "(no reason)")

    # Last-ditch: word-boundary YES/NO scan.
    has_yes = bool(re.search(r"\bYES\b", cleaned, re.IGNORECASE))
    has_no = bool(re.search(r"\bNO\b", cleaned, re.IGNORECASE))
    if has_yes and not has_no:
        return Verdict(is_yes=True, reason="(unparsed JSON; YES inferred)")
    if has_no and not has_yes:
        return Verdict(is_yes=False, reason="(unparsed JSON; NO inferred)")

    raise ValueError(f"Unparseable verifier response: {text!r}")

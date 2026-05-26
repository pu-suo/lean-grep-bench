"""Content-hash item IDs for v2.

An item's ID is a hash over the (goal, hypotheses, prior_tactics, cited
lemma) tuple, so the same proof-step always gets the same ID across
regenerations. The project name is part of the ID so it stays human-
readable at a glance.

Format: ``lgb_<project>_<16-hex-chars>``.

Phase 13 uses this to re-mint the 637 v1 PFR items.
"""

from __future__ import annotations

import hashlib
import json


def mint_item_id(
    *,
    project: str,
    goal: str | None,
    hypotheses: list[str],
    prior_tactics: list[str],
    cited_lemma_qualified_name: str,
) -> str:
    """Mint a stable v2 item ID from the proof-step content tuple."""
    payload = [
        goal or "",
        sorted(hypotheses),
        list(prior_tactics),
        cited_lemma_qualified_name,
    ]
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"lgb_{project}_{digest}"


__all__ = ["mint_item_id"]

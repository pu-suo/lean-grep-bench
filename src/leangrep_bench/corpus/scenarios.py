"""v2 scenario classifier.

Phase 14 re-states the v1 taxonomy in *corpus-relative* terms: an item's
scenario describes where the cited lemma lives in the union corpus
relative to the item's ``(project, mathlib_sha)`` context, rather than
being computed from a per-item ``cited_source`` flag.

The three scenarios are:

- ``mathlib_only`` — the cited lemma's fully-qualified name is present
  in the Mathlib snapshot pinned by the item's ``mathlib_sha``.
- ``local_only``  — the cited lemma is a project-local declaration of
  the item's *own* project, and its short name does not collide with
  any Mathlib short name in the item's Mathlib snapshot.
- ``mixed``       — the cited lemma is project-local *and* its short
  name collides with at least one Mathlib short name in the item's
  Mathlib snapshot.

Fully-qualified names are inherently unique within a single Mathlib
snapshot, so the "resolves uniquely" wording from the spec is
automatically satisfied — there is no separate uniqueness check.

For Phase 13's PFR-only manifest these definitions produce labels
identical to v1's ``_classify`` in ``generate/pipeline.py``; the Phase
14 regression test in ``tests/test_scenarios.py`` is the
gate that proves it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

from leangrep_bench.corpus.model import NormalizedDeclaration

Scenario = Literal["local_only", "mathlib_only", "mixed"]

_LOCAL_SOURCE_PREFIX = "local:"


class CitedLemmaNotInCorpus(Exception):
    """Raised when a cited lemma is neither in any project's local decls nor
    in the relevant Mathlib snapshot. Indicates a data-integrity bug, not a
    valid scenario state."""


@dataclass
class ScenarioIndex:
    """Cached views of the union corpus needed by the classifier."""

    # ``field(default_factory=dict)`` infers ``dict[Unknown, Unknown]`` under
    # strict pyright. Use typed lambdas so the field annotations are honored.
    mathlib_qnames: dict[str, frozenset[str]] = field(
        default_factory=lambda: {}
    )
    mathlib_short_names: dict[str, frozenset[str]] = field(
        default_factory=lambda: {}
    )
    local_qnames: dict[str, frozenset[str]] = field(
        default_factory=lambda: {}
    )


def build_scenario_index(corpus: Iterable[NormalizedDeclaration]) -> ScenarioIndex:
    """Build the per-SHA / per-project lookup tables from a union corpus.

    A declaration's role is read from its ``source`` field: ``"mathlib"`` for
    Mathlib decls (visible_in lists the projects pinning that SHA), and
    ``"local:<project>"`` for project-local decls.
    """
    mathlib_qnames: dict[str, set[str]] = {}
    mathlib_short_names: dict[str, set[str]] = {}
    local_qnames: dict[str, set[str]] = {}

    for d in corpus:
        if d.source == "mathlib":
            for _, sha in d.visible_in:
                mathlib_qnames.setdefault(sha, set()).add(d.qualified_name)
                mathlib_short_names.setdefault(sha, set()).add(d.name)
        elif d.source.startswith(_LOCAL_SOURCE_PREFIX):
            project = d.source.removeprefix(_LOCAL_SOURCE_PREFIX)
            local_qnames.setdefault(project, set()).add(d.qualified_name)

    return ScenarioIndex(
        mathlib_qnames={k: frozenset(v) for k, v in mathlib_qnames.items()},
        mathlib_short_names={k: frozenset(v) for k, v in mathlib_short_names.items()},
        local_qnames={k: frozenset(v) for k, v in local_qnames.items()},
    )


def classify_scenario(
    *,
    project: str,
    mathlib_sha: str,
    cited_lemma_qualified_name: str,
    index: ScenarioIndex,
) -> Scenario:
    """Return the v2 scenario for one item, using only the union corpus index.

    The ordering of checks enforces the spec's *unique resolution* requirement
    for ``mathlib_only``: if the cited qualified name is in both Mathlib and
    the project's locals (e.g. PFR's ``PFR/Mathlib/`` staging copies of
    lemmas that have since landed upstream), the item is ``mixed``, not
    ``mathlib_only``.

    Raises ``CitedLemmaNotInCorpus`` if the lemma is in neither the project's
    locals nor the Mathlib snapshot — that is a data-integrity bug.
    """
    cited = cited_lemma_qualified_name
    in_mathlib = cited in index.mathlib_qnames.get(mathlib_sha, frozenset())
    in_local = cited in index.local_qnames.get(project, frozenset())

    if in_mathlib and not in_local:
        return "mathlib_only"

    if in_local:
        short = cited.rsplit(".", 1)[-1]
        if short in index.mathlib_short_names.get(mathlib_sha, frozenset()):
            return "mixed"
        return "local_only"

    raise CitedLemmaNotInCorpus(
        f"cited lemma {cited!r} not in corpus under "
        f"project={project!r}, mathlib_sha={mathlib_sha!r}"
    )


__all__ = [
    "CitedLemmaNotInCorpus",
    "Scenario",
    "ScenarioIndex",
    "build_scenario_index",
    "classify_scenario",
]

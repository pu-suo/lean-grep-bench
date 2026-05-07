"""Convert LeanDojo ``TacticTrace`` records into ``ProofStep`` rows.

The producer is `data/dojo_trace/`; the consumer is the rest of the
benchmark pipeline (generation, verification, eval).
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import cast

from leangrep_bench.dojo.load import iter_traces
from leangrep_bench.dojo.model import TacticTrace
from leangrep_bench.extract.head_premise import pick_head_premise
from leangrep_bench.extract.index import CorpusIndex
from leangrep_bench.extract.model import (
    ExtractionSummary,
    ProofStep,
    TacticKind,
    write_jsonl,
)
from leangrep_bench.extract.state_parser import (
    parse_state_before,
    render_goal_text,
)

logger = logging.getLogger(__name__)


_TACTIC_KINDS: frozenset[str] = frozenset({"apply", "exact", "use", "refine"})

# Names that should never count as citations (purely syntactic / trivial).
_SYNTAX_BLOCKLIST: frozenset[str] = frozenset(
    {
        "rfl",
        "trivial",
        "True.intro",
        "()",
        "absurd",
        "sorry",
        "this",
    }
)

_MIN_SIGNATURE_CHARS = 20


def _tactic_kind(tactic: str) -> str | None:
    """Return ``apply`` | ``exact`` | ``use`` | ``refine`` if the tactic
    starts with one (allowing leading bullets), else ``None``."""
    s = tactic.lstrip()
    while s and s[0] in "·•‣":
        s = s[1:].lstrip()
    if not s:
        return None
    head = s.split(None, 1)[0] if s else ""
    return head if head in _TACTIC_KINDS else None


def _convert(
    trace: TacticTrace,
    *,
    index: CorpusIndex,
    next_id: list[int],
    prior: deque[str],
    summary: ExtractionSummary,
) -> ProofStep | None:
    kind = _tactic_kind(trace.tactic)
    if kind is None:
        return None
    summary.tactic_invocations += 1

    head = pick_head_premise(trace)
    if head.premise is None:
        summary.skipped[head.skip_reason or "no_head"] += 1
        return None

    entry = index.lookup_qualified(head.premise.full_name)
    if entry is None:
        summary.skipped["unresolved_to_corpus"] += 1
        return None

    if (
        entry.short_name in _SYNTAX_BLOCKLIST
        or entry.qualified_name in _SYNTAX_BLOCKLIST
    ):
        summary.skipped["blocklisted"] += 1
        return None

    if len(entry.signature) < _MIN_SIGNATURE_CHARS:
        summary.skipped["signature_too_short"] += 1
        return None

    parsed = parse_state_before(trace.state_before_pp)
    goal_text: str | None
    hypotheses: list[str]
    if parsed is None:
        goal_text = None
        hypotheses = []
    else:
        goal_text = render_goal_text(parsed.target)
        hypotheses = parsed.hypotheses

    enclosing_entry = index.lookup_qualified(trace.enclosing_decl)
    enclosing_signature = (
        enclosing_entry.signature if enclosing_entry is not None else None
    )

    step_id = f"pfr_step_{next_id[0]:05d}"
    next_id[0] += 1

    summary.kept += 1
    summary.by_tactic[kind] += 1
    summary.by_source[entry.source] += 1

    return ProofStep(
        id=step_id,
        source_file=trace.file,
        line=trace.line_start,
        column=trace.column_start,
        tactic_kind=cast(TacticKind, kind),
        cited_name=entry.qualified_name,
        cited_source=entry.source,
        enclosing_decl=trace.enclosing_decl,
        enclosing_signature=enclosing_signature,
        goal_text=goal_text,
        hypotheses=hypotheses,
        prior_tactics=list(prior),
        raw_tactic_line=trace.tactic,
    )


def _iter_steps(
    traces: Iterable[TacticTrace],
    *,
    index: CorpusIndex,
    summary: ExtractionSummary,
) -> Iterator[ProofStep]:
    next_id = [0]
    prior: deque[str] = deque(maxlen=5)
    cur_key: tuple[str, str] | None = None
    seen_files: set[str] = set()

    for trace in traces:
        seen_files.add(trace.file)
        key = (trace.file, trace.enclosing_decl)
        if key != cur_key:
            cur_key = key
            prior = deque(maxlen=5)

        step = _convert(
            trace,
            index=index,
            next_id=next_id,
            prior=prior,
            summary=summary,
        )
        if step is not None:
            yield step
        # Append the raw tactic text *after* yielding so prior_tactics reflects
        # what came strictly before this point in the proof.
        prior.append(trace.tactic)

    summary.trace_files_loaded = len(seen_files)


def extract_proof_steps(
    trace_path: Path,
    *,
    index: CorpusIndex,
    out_path: Path,
) -> ExtractionSummary:
    summary = ExtractionSummary()
    write_jsonl(
        out_path,
        _iter_steps(iter_traces(trace_path), index=index, summary=summary),
    )
    return summary


__all__ = ["extract_proof_steps"]

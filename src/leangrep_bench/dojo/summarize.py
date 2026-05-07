from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from leangrep_bench.dojo.load import iter_traces


@dataclass
class TraceSummary:
    files_loaded: int = 0
    total_tactics: int = 0
    by_tactic_head: Counter[str] = field(default_factory=lambda: Counter[str]())
    by_source_file: Counter[str] = field(default_factory=lambda: Counter[str]())
    n_empty_state_before: int = 0
    n_zero_premises: int = 0
    n_with_annotated_tactic: int = 0

    def render(self) -> str:
        top_tactics = self.by_tactic_head.most_common(10)
        head_str = ", ".join(f"{k}={v:,}" for k, v in top_tactics) or "(none)"
        lines = [
            "Trace summary",
            f"  source files loaded:    {self.files_loaded:,}",
            f"  tactic invocations:     {self.total_tactics:,}",
            f"  empty state_before_pp:  {self.n_empty_state_before:,}",
            f"  zero-premise tactics:   {self.n_zero_premises:,}",
            f"  with annotated_tactic:  {self.n_with_annotated_tactic:,}",
            f"  top tactic heads:       {head_str}",
        ]
        return "\n".join(lines)


def _tactic_head(tactic: str) -> str:
    """Return the first whitespace-separated token of a (possibly multi-line)
    tactic string. Empty string if the tactic has no leading token."""
    stripped = tactic.lstrip()
    if not stripped:
        return ""
    for i, ch in enumerate(stripped):
        if ch.isspace():
            return stripped[:i]
    return stripped


def summarize(path: Path) -> TraceSummary:
    """Walk a trace JSONL (or directory of JSONLs) and compute summary stats."""
    summary = TraceSummary()
    seen_files: set[str] = set()
    for trace in iter_traces(path):
        summary.total_tactics += 1
        seen_files.add(trace.file)
        summary.by_source_file[trace.file] += 1
        summary.by_tactic_head[_tactic_head(trace.tactic)] += 1
        if not trace.state_before_pp.strip():
            summary.n_empty_state_before += 1
        if not trace.premises:
            summary.n_zero_premises += 1
        if trace.annotated_tactic:
            summary.n_with_annotated_tactic += 1
    summary.files_loaded = len(seen_files)
    return summary


__all__ = ["TraceSummary", "summarize"]

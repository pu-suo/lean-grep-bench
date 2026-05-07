from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from leangrep_bench.corpus.model import read_jsonl_raw


@dataclass
class CorpusStats:
    total: int
    signature_pct: float
    docstring_pct: float
    by_kind: list[tuple[str, int]]


def compute_stats(jsonl_path: Path) -> CorpusStats:
    total = 0
    sig = 0
    doc = 0
    kinds: Counter[str] = Counter()
    for row in read_jsonl_raw(jsonl_path):
        total += 1
        if row.get("signature"):
            sig += 1
        if row.get("docstring"):
            doc += 1
        kind = row.get("kind")
        if isinstance(kind, str):
            kinds[kind] += 1
    sig_pct = (sig / total * 100.0) if total else 0.0
    doc_pct = (doc / total * 100.0) if total else 0.0
    return CorpusStats(
        total=total,
        signature_pct=sig_pct,
        docstring_pct=doc_pct,
        by_kind=sorted(kinds.items(), key=lambda kv: -kv[1]),
    )


def format_stats(jsonl_path: Path, stats: CorpusStats) -> str:
    lines = [
        f"{jsonl_path.name}",
        f"  total: {stats.total:,}",
        f"  signature non-empty: {stats.signature_pct:.1f}%",
        f"  docstring non-empty: {stats.docstring_pct:.1f}%",
        "  by kind: " + ", ".join(f"{k}={v:,}" for k, v in stats.by_kind),
    ]
    return "\n".join(lines)

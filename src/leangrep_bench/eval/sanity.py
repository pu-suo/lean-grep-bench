from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from leangrep_bench.adapters.base import RetrievalAdapter
from leangrep_bench.adapters.registry import build_adapter
from leangrep_bench.corpus.model import NormalizedDeclaration
from leangrep_bench.corpus.model import read_jsonl as read_corpus
from leangrep_bench.verify.model import BenchmarkItem, read_jsonl_accepted

logger = logging.getLogger(__name__)


@dataclass
class AdapterScores:
    name: str
    by_scenario: dict[str, dict[int, int]]  # scenario -> {k -> hits}
    counts: dict[str, int]  # scenario -> total

    def recall(self, scenario: str, k: int) -> float:
        hits = self.by_scenario.get(scenario, {}).get(k, 0)
        n = self.counts.get(scenario, 0)
        return (hits / n) if n else 0.0


def _load_corpus(corpus_dir: Path) -> list[NormalizedDeclaration]:
    out: list[NormalizedDeclaration] = []
    for fname in ("mathlib_declarations.jsonl", "pfr_declarations.jsonl"):
        p = corpus_dir / fname
        if not p.exists():
            continue
        for d in read_corpus(p):
            out.append(d)
    return out


def _evaluate(
    adapter: RetrievalAdapter,
    items: list[BenchmarkItem],
    ks: tuple[int, ...] = (1, 5, 10),
) -> AdapterScores:
    by_scenario: dict[str, dict[int, int]] = defaultdict(lambda: dict.fromkeys(ks, 0))
    counts: dict[str, int] = defaultdict(int)
    max_k = max(ks)
    for item in items:
        results = adapter.search(item.query, context=item.context, k=max_k)
        ret_names = [r.name for r in results]
        counts[item.scenario] += 1
        for k in ks:
            if item.ground_truth_name in ret_names[:k]:
                by_scenario[item.scenario][k] += 1
    return AdapterScores(
        name=adapter.name, by_scenario=dict(by_scenario), counts=dict(counts)
    )


def run_sanity_check(
    *,
    benchmark_path: Path,
    corpus_dir: Path,
    adapter_names: Iterable[str],
    ks: tuple[int, ...] = (1, 5, 10),
) -> list[AdapterScores]:
    items = list(read_jsonl_accepted(benchmark_path))
    if not items:
        raise RuntimeError(f"no benchmark items found in {benchmark_path}")
    corpus = _load_corpus(corpus_dir)
    if not corpus:
        raise RuntimeError(f"no corpus found in {corpus_dir}")

    out: list[AdapterScores] = []
    for name in adapter_names:
        adapter = build_adapter(name)
        logger.info("indexing %s on %d docs", adapter.name, len(corpus))
        adapter.index(corpus)
        logger.info("scoring %s on %d benchmark items", adapter.name, len(items))
        out.append(_evaluate(adapter, items, ks=ks))
    return out


def render_table(
    scores: list[AdapterScores], ks: tuple[int, ...] = (1, 5, 10)
) -> str:
    """Render a compact text table of recall by scenario."""
    scenarios: list[str] = []
    for s in scores:
        for scen in s.counts:
            if scen not in scenarios:
                scenarios.append(scen)
    scenarios.sort()
    lines: list[str] = []
    for s in scores:
        lines.append(f"## {s.name}")
        for scen in scenarios:
            n = s.counts.get(scen, 0)
            cells: list[str] = []
            for k in ks:
                r = s.recall(scen, k) * 100.0
                cells.append(f"R@{k}={r:5.1f}%")
            lines.append(f"  {scen:<14s} (n={n:>4d}): " + "  ".join(cells))
        # Overall
        total_n = sum(s.counts.values())
        total_hits = {
            k: sum(s.by_scenario.get(scen, {}).get(k, 0) for scen in scenarios)
            for k in ks
        }
        cells2: list[str] = []
        for k in ks:
            r = (total_hits[k] / total_n * 100.0) if total_n else 0.0
            cells2.append(f"R@{k}={r:5.1f}%")
        lines.append(f"  {'overall':<14s} (n={total_n:>4d}): " + "  ".join(cells2))
    return "\n".join(lines)

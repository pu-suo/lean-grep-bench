from __future__ import annotations

import json
import logging
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

from leangrep_bench.adapters.base import RetrievalAdapter
from leangrep_bench.adapters.external.base import AdapterUnavailable
from leangrep_bench.adapters.registry import build_adapter, list_adapters
from leangrep_bench.corpus.model import NormalizedDeclaration
from leangrep_bench.corpus.model import read_jsonl as read_corpus
from leangrep_bench.eval.metrics import SliceMetrics, compute_metrics
from leangrep_bench.eval.model import Prediction, read_jsonl
from leangrep_bench.verify.model import BenchmarkItem, read_jsonl_accepted


@dataclass
class _AdapterReport:
    adapter: str
    metrics: dict[str, SliceMetrics]


@dataclass
class _RunReport:
    n_items: int
    ks: tuple[int, ...]
    adapters: list[_AdapterReport] = field(default_factory=lambda: [])
    unavailable: dict[str, str] = field(default_factory=lambda: {})

logger = logging.getLogger(__name__)

_KS: tuple[int, ...] = (1, 5, 10)


def _load_corpus(corpus_dir: Path) -> list[NormalizedDeclaration]:
    out: list[NormalizedDeclaration] = []
    for fname in ("mathlib_declarations.jsonl", "pfr_declarations.jsonl"):
        p = corpus_dir / fname
        if not p.exists():
            continue
        for d in read_corpus(p):
            out.append(d)
    return out


def _existing_predictions(
    predictions_path: Path,
) -> dict[tuple[str, str], Prediction]:
    out: dict[tuple[str, str], Prediction] = {}
    for p in read_jsonl(predictions_path):
        out[(p.adapter, p.item_id)] = p
    return out


def _run_adapter(
    adapter: RetrievalAdapter,
    items: list[BenchmarkItem],
    corpus: list[NormalizedDeclaration],
    *,
    existing: dict[tuple[str, str], Prediction],
    k: int,
    out_file: IO[str],
) -> int:
    """Index the adapter, run predictions for items not already cached, append
    each new prediction to ``out_file`` immediately, return # new predictions.
    """
    needed = [it for it in items if (adapter.name, it.id) not in existing]
    if not needed:
        logger.info(
            "%s: all %d items already in predictions.jsonl, skipping",
            adapter.name,
            len(items),
        )
        return 0

    logger.info("%s: indexing %d corpus docs", adapter.name, len(corpus))
    adapter.index(corpus)

    written = 0
    for i, item in enumerate(needed, 1):
        results = adapter.search(item.query, context=item.context, k=k)
        pred = Prediction(
            adapter=adapter.name,
            item_id=item.id,
            scenario=item.scenario,
            ground_truth_name=item.ground_truth_name,
            predicted_names=[r.name for r in results],
            scores=[r.score for r in results],
        )
        existing[(adapter.name, item.id)] = pred
        out_file.write(pred.model_dump_json() + "\n")
        out_file.flush()
        written += 1
        if i % 50 == 0:
            logger.info("%s: %d/%d", adapter.name, i, len(needed))
    return written


def _slice_metrics(
    preds: Iterable[Prediction], scenario: str | None
) -> SliceMetrics:
    rows = (
        (p.ground_truth_name, p.predicted_names)
        for p in preds
        if scenario is None or p.scenario == scenario
    )
    return compute_metrics(rows, ks=_KS)


def run_eval(
    *,
    benchmark_path: Path,
    corpus_dir: Path,
    adapter_names: list[str],
    out_dir: Path,
    k: int = 10,
) -> dict[str, object]:
    items = list(read_jsonl_accepted(benchmark_path))
    if not items:
        raise RuntimeError(f"no benchmark items in {benchmark_path}")
    corpus = _load_corpus(corpus_dir)
    if not corpus:
        raise RuntimeError(f"no corpus in {corpus_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = out_dir / "predictions.jsonl"
    metrics_path = out_dir / "metrics.json"
    results_md = out_dir / "results.md"

    existing = _existing_predictions(predictions_path)

    # Validate adapter names exist in the registry early. Catch
    # AdapterUnavailable per-adapter so a missing external endpoint doesn't
    # prevent the rest of the eval from running.
    known = set(list_adapters())
    unknown = [n for n in adapter_names if n not in known]
    if unknown:
        raise KeyError(f"unknown adapters: {unknown}. Available: {sorted(known)}")

    unavailable: dict[str, str] = {}
    built: list[tuple[str, RetrievalAdapter]] = []
    for name in adapter_names:
        try:
            built.append((name, build_adapter(name)))
        except AdapterUnavailable as e:
            unavailable[name] = str(e)
            logger.warning("adapter %s unavailable: %s", name, e)

    out_file = predictions_path.open("a", encoding="utf-8")
    try:
        for name, adapter in built:
            try:
                _run_adapter(
                    adapter,
                    items,
                    corpus,
                    existing=existing,
                    k=k,
                    out_file=out_file,
                )
            except AdapterUnavailable as e:
                unavailable[name] = str(e)
                logger.warning("adapter %s became unavailable mid-run: %s", name, e)
    finally:
        out_file.close()

    # Compute metrics over everything in predictions.jsonl that matches the
    # adapters we successfully built (resume tolerates leftover predictions
    # from prior runs with different adapter sets).
    built_names = {a.name for _, a in built}
    all_preds = list(read_jsonl(predictions_path))
    by_adapter: dict[str, list[Prediction]] = defaultdict(list)
    for p in all_preds:
        if p.adapter in built_names:
            by_adapter[p.adapter].append(p)

    scenarios = sorted({p.scenario for p in all_preds})
    report = _RunReport(
        n_items=len(items), ks=_KS, unavailable=dict(unavailable)
    )
    for _, adapter in built:
        preds = by_adapter.get(adapter.name, [])
        slice_results: dict[str, SliceMetrics] = {}
        slice_results["overall"] = _slice_metrics(preds, None)
        for scen in scenarios:
            slice_results[scen] = _slice_metrics(preds, scen)
        report.adapters.append(
            _AdapterReport(adapter=adapter.name, metrics=slice_results)
        )

    metrics_json = _report_to_dict(report)
    metrics_path.write_text(
        json.dumps(metrics_json, indent=2) + "\n", encoding="utf-8"
    )
    results_md.write_text(_render_markdown(report), encoding="utf-8")
    return metrics_json


def _slice_to_dict(s: SliceMetrics) -> dict[str, object]:
    return {
        "n": s.n,
        "recall_at_1": s.recall_at[1],
        "recall_at_5": s.recall_at[5],
        "recall_at_10": s.recall_at[10],
        "mrr": s.mrr,
    }


def _report_to_dict(report: _RunReport) -> dict[str, object]:
    return {
        "ks": list(report.ks),
        "n_items": report.n_items,
        "adapters": [
            {
                "adapter": a.adapter,
                "metrics": {k: _slice_to_dict(v) for k, v in a.metrics.items()},
            }
            for a in report.adapters
        ],
        "unavailable": dict(report.unavailable),
    }


def _render_markdown(report: _RunReport) -> str:
    if not report.adapters:
        return "# Eval results\n\nNo adapters evaluated.\n"

    first_metrics = report.adapters[0].metrics
    slice_names = [
        "overall",
        *sorted(n for n in first_metrics if n != "overall"),
    ]

    lines: list[str] = []
    lines.append("# Eval results")
    lines.append("")
    lines.append(f"- Items: {report.n_items}")
    lines.append(
        f"- Adapters: {', '.join(a.adapter for a in report.adapters)}"
    )
    if report.unavailable:
        lines.append("- Unavailable adapters (N/A in tables below):")
        for n, reason in sorted(report.unavailable.items()):
            lines.append(f"  - **{n}**: {reason}")
    lines.append("")
    for slc in slice_names:
        n = first_metrics[slc].n
        title = "Overall" if slc == "overall" else slc
        lines.append(f"## {title} (N={n})")
        lines.append("")
        lines.append("| System | R@1 | R@5 | R@10 | MRR |")
        lines.append("|---|---|---|---|---|")
        for a in report.adapters:
            s = a.metrics[slc]
            lines.append(
                f"| {a.adapter} | "
                f"{s.recall_at[1]:.3f} | "
                f"{s.recall_at[5]:.3f} | "
                f"{s.recall_at[10]:.3f} | "
                f"{s.mrr:.3f} |"
            )
        lines.append("")
    return "\n".join(lines)


__all__ = ["run_eval"]

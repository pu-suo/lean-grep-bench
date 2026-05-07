"""Audit writer for the benchmark.

Produces a markdown summary with: accept/reject counts and pass rate
overall and by scenario, plus N random rejection rows (with verifier
reasoning) and N random acceptance rows (with goal text and
provenance).
"""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

from leangrep_bench.verify.model import (
    read_jsonl_accepted,
    read_jsonl_rejected,
)


def _truncate(s: str | None, limit: int) -> str:
    if not s:
        return "(none)"
    if len(s) <= limit:
        return s
    return s[:limit].rstrip() + " …"


def write_audit(
    *,
    accepted_path: Path,
    rejected_path: Path,
    out_path: Path,
    sample_size: int = 10,
    seed: int = 0,
) -> str:
    accepted = list(read_jsonl_accepted(accepted_path))
    rejected = list(read_jsonl_rejected(rejected_path))
    total = len(accepted) + len(rejected)
    pass_rate = (len(accepted) / total * 100.0) if total else 0.0

    by_scenario_total: Counter[str] = Counter()
    by_scenario_pass: Counter[str] = Counter()
    for a in accepted:
        by_scenario_total[a.scenario] += 1
        by_scenario_pass[a.scenario] += 1
    for r in rejected:
        by_scenario_total[r.scenario] += 1

    rng = random.Random(seed)
    rej_sample = rng.sample(rejected, min(sample_size, len(rejected)))
    acc_sample = rng.sample(accepted, min(sample_size, len(accepted)))

    lines: list[str] = []
    lines.append("# Benchmark Verification Audit")
    lines.append("")
    lines.append(
        f"- Accepted: **{len(accepted):,}** / {total:,} ({pass_rate:.2f}%)"
    )
    lines.append(f"- Rejected: {len(rejected):,}")
    lines.append("- By scenario:")
    for scen, t in by_scenario_total.most_common():
        p = by_scenario_pass.get(scen, 0)
        sr = (p / t * 100.0) if t else 0.0
        lines.append(f"  - {scen}: {p:,}/{t:,} ({sr:.1f}%)")
    lines.append("")

    lines.append(f"## {len(rej_sample)} random rejections")
    lines.append("")
    for i, r in enumerate(rej_sample, 1):
        lines.append(f"### R{i}. `{r.id}` — scenario: `{r.scenario}`")
        lines.append("")
        lines.append(f"- **Query**: {r.query}")
        lines.append(
            f"- **Ground truth**: `{r.ground_truth_name}` "
            f"({r.ground_truth_source})"
        )
        lines.append(f"- **Verifier reason**: {r.reason}")
        lines.append("")

    lines.append(f"## {len(acc_sample)} random acceptances")
    lines.append("")
    for i, a in enumerate(acc_sample, 1):
        lines.append(f"### A{i}. `{a.id}` — scenario: `{a.scenario}`")
        lines.append("")
        lines.append(f"- **Query**: {a.query}")
        lines.append(
            f"- **Ground truth**: `{a.ground_truth_name}` "
            f"({a.ground_truth_source})"
        )
        lines.append(
            f"- **Provenance**: `{a.provenance.source_file}:{a.provenance.line}`"
            f" ({a.provenance.tactic_kind})"
        )
        lines.append(f"- **Enclosing**: `{a.context.enclosing_decl}`")
        lines.append(f"- **Goal**: `{_truncate(a.context.goal, 220)}`")
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    out_path.write_text(text, encoding="utf-8")
    return text


__all__ = ["write_audit"]

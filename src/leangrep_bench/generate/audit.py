"""Audit writer for generated queries.

Produces a markdown file with: total counts, by-scenario breakdown,
query word-count distribution, leakage breakdown (cited-name, goal,
either), and N random spot-check rows showing the goal, hypotheses,
prior tactics, redacted line, generated query, and ground truth.
"""

from __future__ import annotations

import random
import statistics
from collections import Counter
from pathlib import Path

from leangrep_bench.extract.model import ProofStep
from leangrep_bench.extract.model import read_jsonl as read_steps
from leangrep_bench.generate.model import read_jsonl as read_queries
from leangrep_bench.generate.prompt import redact_tactic_line


def _percentiles(xs: list[int], ps: tuple[int, ...]) -> dict[int, float]:
    if not xs:
        return {p: 0.0 for p in ps}
    xs_sorted = sorted(xs)
    out: dict[int, float] = {}
    if len(xs_sorted) > 1:
        qs = statistics.quantiles(xs_sorted, n=100)
        for p in ps:
            out[p] = float(qs[p - 1])
    else:
        for p in ps:
            out[p] = float(xs_sorted[0])
    return out


def write_audit(
    *,
    queries_path: Path,
    steps_path: Path,
    out_path: Path,
    sample_size: int = 15,
    seed: int = 0,
) -> str:
    queries = list(read_queries(queries_path))
    steps_by_id: dict[str, ProofStep] = {
        s.id: s for s in read_steps(steps_path)
    }

    by_scenario: Counter[str] = Counter()
    word_counts: list[int] = []
    cited_only = 0
    goal_only = 0
    both = 0
    for q in queries:
        by_scenario[q.scenario] += 1
        word_counts.append(len(q.query.split()))
        if q.cited_name_leakage and q.goal_leakage:
            both += 1
        elif q.cited_name_leakage:
            cited_only += 1
        elif q.goal_leakage:
            goal_only += 1

    pct = _percentiles(word_counts, (5, 50, 95))
    n = len(queries) or 1

    rng = random.Random(seed)
    sample = rng.sample(queries, min(sample_size, len(queries)))

    lines: list[str] = []
    lines.append("# Query Generation Audit")
    lines.append("")
    lines.append(f"- Total queries: **{len(queries):,}**")
    lines.append("- By scenario:")
    for k, v in by_scenario.most_common():
        lines.append(f"  - {k}: {v:,}")
    lines.append(
        f"- Query word count: 5th={pct[5]:.1f}, "
        f"50th={pct[50]:.1f}, 95th={pct[95]:.1f}"
    )
    lines.append("- Leakage breakdown:")
    lines.append(
        f"  - cited-name only: **{cited_only:,} "
        f"({cited_only / n * 100:.2f}%)**"
    )
    lines.append(
        f"  - goal-restatement only: **{goal_only:,} "
        f"({goal_only / n * 100:.2f}%)**"
    )
    lines.append(f"  - both:              **{both:,} ({both / n * 100:.2f}%)**")
    any_leak = cited_only + goal_only + both
    lines.append(
        f"  - **any leakage:**   **{any_leak:,} ({any_leak / n * 100:.2f}%)**"
    )
    lines.append("")
    lines.append(f"## {sample_size} random spot-checks")
    lines.append("")
    for i, q in enumerate(sample, 1):
        step = steps_by_id.get(q.proof_step_id)
        lines.append(f"### {i}. `{q.id}` — scenario: `{q.scenario}`")
        lines.append("")
        if step is None:
            lines.append("- **(missing step record)**")
            lines.append(f"- **Query**: {q.query}")
            lines.append("")
            continue
        lines.append(f"- **Ground truth**: `{step.cited_name}`")
        lines.append(f"- **Tactic kind**: `{step.tactic_kind}`")
        lines.append(f"- **Source**: `{step.source_file}:{step.line}`")
        lines.append(f"- **Enclosing**: `{step.enclosing_decl}`")
        goal = (step.goal_text or "(none)").replace("\n", " ")
        if len(goal) > 220:
            goal = goal[:220] + " …"
        lines.append(f"- **Goal**: `{goal}`")
        if step.hypotheses:
            lines.append("- **Hypotheses**:")
            for h in step.hypotheses[:6]:
                truncated = h if len(h) <= 200 else h[:200] + " …"
                lines.append(f"  - `{truncated}`")
            if len(step.hypotheses) > 6:
                lines.append(f"  - … (+{len(step.hypotheses) - 6} more)")
        if step.prior_tactics:
            lines.append("- **Prior tactics**:")
            for t in step.prior_tactics:
                truncated = t if len(t) <= 200 else t[:200] + " …"
                lines.append(f"  - `{truncated}`")
        redacted = redact_tactic_line(
            step.raw_tactic_line, step.cited_name
        ).strip()
        lines.append(f"- **Redacted line**: `{redacted}`")
        lines.append(f"- **Query**: {q.query}")
        flags: list[str] = []
        if q.cited_name_leakage:
            flags.append("cited-name leakage")
        if q.goal_leakage:
            flags.append("goal-restatement leakage")
        if flags:
            lines.append(f"- ⚠ **Leakage**: {', '.join(flags)}")
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    out_path.write_text(text, encoding="utf-8")
    return text


__all__ = ["write_audit"]

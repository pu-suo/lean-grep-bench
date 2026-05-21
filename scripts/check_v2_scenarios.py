"""Re-classify every benchmark item under the v2 scenario classifier and
print any disagreements against the labels stored in the file. Exits
non-zero if there is any drift or any unresolved cited lemma.

Run from the repo root:

    python scripts/check_v2_scenarios.py
    python scripts/check_v2_scenarios.py --benchmark data/benchmark.jsonl

Same logic as ``tests/test_scenarios_v2_regression.py``; this script is
the operator-facing form you can run ad hoc when investigating drift in a
new benchmark cut.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import typer

from leangrep_bench.corpus.model import read_jsonl as read_corpus
from leangrep_bench.corpus.scenarios import (
    CitedLemmaNotInCorpus,
    build_scenario_index,
    classify_scenario,
)
from leangrep_bench.verify.model import read_jsonl_accepted

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BENCHMARK = REPO_ROOT / "data" / "benchmark.jsonl"
DEFAULT_UNION_DIR = REPO_ROOT / "data" / "corpus" / "v2"


def main(
    benchmark: Path = typer.Option(DEFAULT_BENCHMARK, "--benchmark"),
    union_dir: Path = typer.Option(DEFAULT_UNION_DIR, "--union-dir"),
) -> None:
    """Print scenario-classification diffs between the stored labels and v2."""
    if not union_dir.exists():
        typer.echo(f"ERROR: union corpus not found at {union_dir}", err=True)
        raise typer.Exit(2)
    if not benchmark.exists():
        typer.echo(f"ERROR: benchmark not found at {benchmark}", err=True)
        raise typer.Exit(2)

    corpus = []
    for p in sorted(union_dir.glob("*.jsonl")):
        corpus.extend(read_corpus(p))
    typer.echo(f"loaded union corpus: {len(corpus):,} declarations")
    index = build_scenario_index(corpus)

    items = list(read_jsonl_accepted(benchmark))
    typer.echo(f"loaded benchmark:    {len(items):,} items")

    diffs: list[tuple[str, str, str, str]] = []
    unresolved: list[tuple[str, str]] = []
    by_transition: Counter[tuple[str, str]] = Counter()
    by_predicted: Counter[str] = Counter()

    for it in items:
        if it.project is None or it.mathlib_sha is None:
            typer.echo(
                f"item {it.id} missing project/mathlib_sha "
                "(rerun scripts/regen_v2_ids.py)",
                err=True,
            )
            raise typer.Exit(2)
        try:
            predicted = classify_scenario(
                project=it.project,
                mathlib_sha=it.mathlib_sha,
                cited_lemma_qualified_name=it.ground_truth_name,
                index=index,
            )
        except CitedLemmaNotInCorpus:
            unresolved.append((it.id, it.ground_truth_name))
            continue
        by_predicted[predicted] += 1
        if predicted != it.scenario:
            diffs.append((it.id, it.ground_truth_name, it.scenario, predicted))
            by_transition[(it.scenario, predicted)] += 1

    typer.echo("")
    typer.echo("v2 scenario distribution (predicted):")
    for scen, n in by_predicted.most_common():
        typer.echo(f"  {scen}: {n}")
    typer.echo("")

    if unresolved:
        typer.echo(
            f"UNRESOLVED: {len(unresolved)} items have cited lemmas not in "
            f"the union corpus. First 10:"
        )
        for iid, name in unresolved[:10]:
            typer.echo(f"  {iid}  {name}")
        raise typer.Exit(1)

    if diffs:
        typer.echo(f"DRIFT: {len(diffs)} items have v1 != v2 labels.")
        typer.echo("By transition (v1 -> v2):")
        for (old, new), n in by_transition.most_common():
            typer.echo(f"  {old:>13s} -> {new:<13s} : {n}")
        typer.echo("")
        typer.echo("First 20 disagreements:")
        for iid, name, v1, v2 in diffs[:20]:
            typer.echo(f"  {iid}  {name}  v1={v1}  v2={v2}")
        raise typer.Exit(1)

    typer.echo("OK: zero diffs against stored labels.")


if __name__ == "__main__":
    sys.exit(typer.run(main) or 0)

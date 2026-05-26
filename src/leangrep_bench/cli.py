import logging
from pathlib import Path

import typer

from leangrep_bench import __version__
from leangrep_bench.adapters.registry import list_adapters
from leangrep_bench.corpus.build import build_corpus
from leangrep_bench.corpus.manifest import read_manifest, write_manifest
from leangrep_bench.corpus.stats import compute_stats, format_stats
from leangrep_bench.corpus.union import build_union_corpus
from leangrep_bench.dojo.cli import dojo_app
from leangrep_bench.eval.runner import run_eval
from leangrep_bench.eval.sanity import render_table, run_sanity_check
from leangrep_bench.extract.extractor import extract_proof_steps
from leangrep_bench.extract.index import CorpusIndex
from leangrep_bench.extract.model import read_jsonl as read_steps
from leangrep_bench.generate.audit import write_audit as write_query_audit
from leangrep_bench.generate.pipeline import generate_queries
from leangrep_bench.generate.prompt import build_user_prompt
from leangrep_bench.verify.audit import write_audit as write_benchmark_audit
from leangrep_bench.verify.model import read_jsonl_accepted
from leangrep_bench.verify.pipeline import verify_queries

app = typer.Typer(help="leangrep-bench CLI.", no_args_is_help=True)
corpus_app = typer.Typer(
    help="Build and inspect the declaration corpus.", no_args_is_help=True
)
extract_app = typer.Typer(
    help="Convert LeanDojo traces into proof-step records.",
    no_args_is_help=True,
)
generate_app = typer.Typer(
    help="Generate LLM queries against extracted proof steps.",
    no_args_is_help=True,
)
verify_app = typer.Typer(
    help="Run the verifier over generated queries.", no_args_is_help=True
)
benchmark_app = typer.Typer(
    help="Operate over the cross-project benchmark file.", no_args_is_help=True
)
app.add_typer(corpus_app, name="corpus")
app.add_typer(extract_app, name="extract")
app.add_typer(generate_app, name="generate")
app.add_typer(verify_app, name="verify")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(dojo_app, name="dojo")


def _project_dir(project: str) -> Path:
    """Per-project working directory under ``data/<project>/``.

    All per-project artifacts (proof_steps, queries, benchmark, audit)
    live under this directory. The top-level ``data/benchmark.jsonl`` and
    ``data/benchmark.csv`` are the union across projects, produced by
    ``benchmark merge``.
    """
    return Path("data") / project


def _manifest_lookup_mathlib_sha(project: str) -> str | None:
    """Read ``mathlib_sha`` for ``project`` from the build manifest, if
    available. Returns ``None`` if the manifest is missing or doesn't list
    this project — the extract pipeline will still emit ``ProofStep`` rows
    but without the visibility-filter hint."""
    manifest_path = Path("data") / "corpus" / "build_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = read_manifest(manifest_path)
    except Exception:
        # Best-effort lookup — any parse/IO error is just "use None".
        return None
    for entry in manifest.projects:
        if entry.project_name == project:
            return entry.mathlib_sha
    return None


@app.callback()
def _main() -> None:  # pyright: ignore[reportUnusedFunction]
    """leangrep-bench CLI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@corpus_app.command("build-mathlib")
def corpus_build_mathlib(
    mathlib_path: Path = typer.Option(
        ..., "--mathlib-path", help="Local Mathlib4 checkout."
    ),
    out: Path = typer.Option(..., "--out", help="Output JSONL path."),
    manifest: Path = typer.Option(
        Path("data/corpus/build_manifest.json"),
        "--manifest",
        help="Build manifest output path.",
    ),
) -> None:
    """Parse a Mathlib4 checkout into a JSONL of declarations."""
    n = build_corpus(mathlib_path, out, source="mathlib", sub_dir="Mathlib")
    typer.echo(f"wrote {n:,} declarations to {out}")
    write_manifest(manifest, mathlib_path=mathlib_path, pfr_path=None)
    typer.echo(f"updated manifest: {manifest}")


@corpus_app.command("build-project")
def corpus_build_project(
    project: str = typer.Option(
        ..., "--project", help="Project name, e.g. ``pnt``."
    ),
    repo_path: Path = typer.Option(
        ..., "--repo-path", help="Local checkout of the project."
    ),
    sub_dir: str = typer.Option(
        ...,
        "--sub-dir",
        help="Subdirectory under repo-path that holds the project's Lean "
        "source (e.g. ``PrimeNumberTheoremAnd`` for PNT).",
    ),
    out: Path | None = typer.Option(
        None,
        "--out",
        help="Output JSONL path. Defaults to "
        "``data/corpus/<project>_declarations.jsonl``.",
    ),
) -> None:
    """Parse an arbitrary Lean project into a JSONL of declarations.

    Used by the multi-project pipeline to add PNT / Carleson / FLT-regular
    without bespoke CLI commands. The manifest is updated separately —
    operators add the entry by hand or via ``corpus build-mathlib`` for
    the Mathlib SHA that pairs with this project.
    """
    if out is None:
        out = Path("data") / "corpus" / f"{project}_declarations.jsonl"
    n = build_corpus(
        repo_path,
        out,
        source=f"local:{project}",
        sub_dir=sub_dir,
    )
    typer.echo(f"wrote {n:,} declarations to {out}")


@corpus_app.command("build-union")
def corpus_build_union(
    manifest: Path = typer.Option(
        Path("data/corpus/build_manifest.json"),
        "--manifest",
        help="Build manifest listing projects with visibility info.",
    ),
    legacy_corpus_dir: Path = typer.Option(
        Path("data/corpus"),
        "--legacy-corpus-dir",
        help="Directory holding the per-source JSONLs (mathlib + project).",
    ),
    out_dir: Path = typer.Option(
        Path("data/corpus/union"),
        "--out-dir",
        help="Where to write the union corpus.",
    ),
) -> None:
    """Build the union corpus with per-decl visible_in tags from the manifest."""
    counts = build_union_corpus(
        manifest_path=manifest,
        legacy_corpus_dir=legacy_corpus_dir,
        out_dir=out_dir,
    )
    for fname, n in counts.items():
        typer.echo(f"{fname}: {n:,} declarations")


@corpus_app.command("stats")
def corpus_stats(
    jsonl: Path = typer.Option(
        ..., "--jsonl", help="JSONL corpus file to summarize."
    ),
) -> None:
    """Print summary stats for a corpus JSONL."""
    s = compute_stats(jsonl)
    typer.echo(format_stats(jsonl, s))


@extract_app.command("proof-steps")
def extract_proof_steps_cmd(
    project: str = typer.Option(
        ...,
        "--project",
        help="Project name. Used to stamp ProofStep.project, pick the trace "
        "directory (``data/dojo_trace_<project>``), and derive default "
        "output paths under ``data/<project>/``.",
    ),
    trace_dir: Path | None = typer.Option(
        None,
        "--trace-dir",
        help="Directory of LeanDojo trace JSONLs (or a single .jsonl file). "
        "Defaults to ``data/dojo_trace_<project>/``.",
    ),
    corpus_dir: Path = typer.Option(
        Path("data/corpus"),
        "--corpus-dir",
        help="Corpus root. Prefers the union corpus under "
        "``<corpus-dir>/union/``; falls back to the legacy two-file layout.",
    ),
    out: Path | None = typer.Option(
        None,
        "--out",
        help="Output JSONL path. Defaults to "
        "``data/<project>/proof_steps.jsonl``.",
    ),
    mathlib_sha: str | None = typer.Option(
        None,
        "--mathlib-sha",
        help="Mathlib SHA pinned by this project. If omitted, looked up "
        "from the build manifest; stamped on every emitted ProofStep so "
        "the eval-time visibility filter knows where to look.",
    ),
) -> None:
    """Convert LeanDojo traces into project-tagged proof-step records."""
    if trace_dir is None:
        trace_dir = Path("data") / f"dojo_trace_{project}"
    if out is None:
        out = _project_dir(project) / "proof_steps.jsonl"
    if mathlib_sha is None:
        mathlib_sha = _manifest_lookup_mathlib_sha(project)
        if mathlib_sha is not None:
            typer.echo(
                f"using mathlib_sha={mathlib_sha[:12]}… for project={project} "
                "(from manifest)"
            )

    # Restrict the index to declarations visible under this project's
    # (project, mathlib_sha) context. Without this filter, PNT extract could
    # spuriously resolve a cited name against a Mathlib decl that only lives
    # in PFR's snapshot (or vice versa), producing benchmark items whose
    # ground truth is invisible to the eval-time visibility filter.
    index = CorpusIndex.auto(
        corpus_dir, project=project, mathlib_sha=mathlib_sha
    )
    summary = extract_proof_steps(
        trace_dir,
        index=index,
        out_path=out,
        project=project,
        mathlib_sha=mathlib_sha,
    )
    typer.echo(summary.render())
    typer.echo(f"wrote {summary.kept:,} proof steps to {out}")


# Token-rate snapshot for cost preview. Updated occasionally; values are
# from OpenAI's published pricing at the time of writing.
_PRICE_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5": (1.25, 10.00),
}


def _estimate_cost(steps_path: Path, model: str) -> tuple[int, float]:
    """Build the user prompt for the first 5 steps, average char counts,
    extrapolate to all steps, and apply the model's input/output rate.
    Returns (n_steps, estimated_usd)."""
    steps = list(read_steps(steps_path))
    if not steps:
        return 0, 0.0
    sample = steps[: min(5, len(steps))]
    avg_prompt_chars = sum(len(build_user_prompt(s)) for s in sample) / len(
        sample
    )
    # ~4 chars / token is a coarse but stable approximation.
    avg_prompt_tokens = avg_prompt_chars / 4
    avg_completion_tokens = 30  # one-line query is short
    total_prompt = avg_prompt_tokens * len(steps)
    total_completion = avg_completion_tokens * len(steps)
    rate_in, rate_out = _PRICE_PER_1M.get(model, (0.0, 0.0))
    cost = total_prompt * rate_in / 1_000_000 + total_completion * rate_out / 1_000_000
    return len(steps), cost


@generate_app.command("queries")
def generate_queries_cmd(
    project: str = typer.Option(
        ...,
        "--project",
        help="Project name. Drives default paths for steps/out/audit.",
    ),
    steps: Path | None = typer.Option(
        None,
        "--steps",
        help="ProofStep JSONL produced by ``extract proof-steps``. "
        "Defaults to ``data/<project>/proof_steps.jsonl``.",
    ),
    out: Path | None = typer.Option(
        None,
        "--out",
        help="Output queries JSONL. Defaults to "
        "``data/<project>/queries.jsonl``.",
    ),
    model: str = typer.Option(
        "gpt-5-mini", "--model", help="OpenAI model identifier."
    ),
    seed: int = typer.Option(1, "--seed", help="Per-call generation seed."),
    temperature: float = typer.Option(0.7, "--temperature"),
    cache_dir: Path = typer.Option(
        Path(".cache/llm"), "--cache-dir", help="Disk cache for LLM responses."
    ),
    corpus_dir: Path = typer.Option(
        Path("data/corpus"),
        "--corpus-dir",
        help="Corpus dir. Prefers the union corpus for scenario classification.",
    ),
    audit_out: Path | None = typer.Option(
        None,
        "--audit-out",
        help="Audit markdown output path. Defaults to "
        "``data/<project>/queries_audit.md``.",
    ),
    concurrency: int = typer.Option(
        8, "--concurrency", help="Parallel API workers."
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip the cost-estimate confirmation."
    ),
) -> None:
    """Generate one query per proof step using an LLM. Resume-safe."""
    if steps is None:
        steps = _project_dir(project) / "proof_steps.jsonl"
    if out is None:
        out = _project_dir(project) / "queries.jsonl"
    if audit_out is None:
        audit_out = _project_dir(project) / "queries_audit.md"
    n_steps, est = _estimate_cost(steps, model)
    typer.echo(
        f"Cost estimate: ~${est:.2f} for {n_steps:,} steps "
        f"on {model} (cached calls free)."
    )
    if not yes and est > 1.0:
        confirm = typer.confirm("Proceed with generation?", default=True)
        if not confirm:
            raise typer.Exit(code=1)
    stats = generate_queries(
        steps_path=steps,
        out_path=out,
        cache_dir=cache_dir,
        corpus_dir=corpus_dir,
        model=model,
        seed=seed,
        temperature=temperature,
        concurrency=concurrency,
    )
    typer.echo("Generation summary:")
    typer.echo(stats.render())
    typer.echo(f"wrote {out}")
    write_query_audit(queries_path=out, steps_path=steps, out_path=audit_out)
    typer.echo(f"audit at {audit_out}")


@verify_app.command("queries")
def verify_queries_cmd(
    project: str = typer.Option(
        ...,
        "--project",
        help="Project name. Drives default paths.",
    ),
    queries: Path | None = typer.Option(
        None, "--queries", help="Generated queries JSONL."
    ),
    steps: Path | None = typer.Option(
        None, "--steps", help="ProofStep JSONL (used to recover context + goal)."
    ),
    corpus_dir: Path = typer.Option(
        Path("data/corpus"),
        "--corpus-dir",
        help="Corpus root. Prefers the union corpus under "
        "``<corpus-dir>/union/``.",
    ),
    out: Path | None = typer.Option(
        None,
        "--out",
        help="Accepted (benchmark) JSONL output path. Defaults to "
        "``data/<project>/benchmark.jsonl``.",
    ),
    rejected: Path | None = typer.Option(
        None,
        "--rejected",
        help="Rejected items JSONL output path. Defaults to "
        "``data/<project>/benchmark_rejected.jsonl``.",
    ),
    model: str = typer.Option(
        "gpt-5", "--model", help="Verifier OpenAI model identifier."
    ),
    seed: int = typer.Option(1, "--seed", help="Verifier call seed."),
    temperature: float = typer.Option(
        0.0, "--temperature", help="Verifier temperature (default 0)."
    ),
    cache_dir: Path = typer.Option(
        Path(".cache/llm"), "--cache-dir", help="Disk cache for LLM responses."
    ),
    audit_out: Path | None = typer.Option(
        None,
        "--audit-out",
        help="Audit markdown output path. Defaults to "
        "``data/<project>/benchmark_audit.md``.",
    ),
    concurrency: int = typer.Option(
        16, "--concurrency", help="Parallel API workers."
    ),
) -> None:
    """Run the verifier over generated queries; write the accepted benchmark."""
    pdir = _project_dir(project)
    if queries is None:
        queries = pdir / "queries.jsonl"
    if steps is None:
        steps = pdir / "proof_steps.jsonl"
    if out is None:
        out = pdir / "benchmark.jsonl"
    if rejected is None:
        rejected = pdir / "benchmark_rejected.jsonl"
    if audit_out is None:
        audit_out = pdir / "benchmark_audit.md"
    stats = verify_queries(
        queries_path=queries,
        steps_path=steps,
        corpus_dir=corpus_dir,
        out_path=out,
        rejected_path=rejected,
        cache_dir=cache_dir,
        model=model,
        seed=seed,
        temperature=temperature,
        concurrency=concurrency,
    )
    typer.echo("Verification summary:")
    typer.echo(stats.render())
    typer.echo(f"wrote benchmark to {out}")
    typer.echo(f"wrote rejects   to {rejected}")
    write_benchmark_audit(
        accepted_path=out, rejected_path=rejected, out_path=audit_out
    )
    typer.echo(f"audit at {audit_out}")


@benchmark_app.command("export-csv")
def benchmark_export_csv_cmd(
    inp: Path = typer.Option(
        Path("data/benchmark.jsonl"),
        "--input",
        "-i",
        help="Benchmark JSONL to export (defaults to the unified file).",
    ),
    out: Path = typer.Option(
        Path("data/benchmark.csv"),
        "--out",
        help="CSV output path.",
    ),
    max_len: int = typer.Option(
        500,
        "--max-len",
        help="Truncate long cells to this many characters. 0 = no truncation.",
    ),
) -> None:
    """Flatten the benchmark JSONL into a human-viewable CSV.

    Thin wrapper around ``scripts/convert_benchmark.py`` so the CSV stays
    in sync with the merged ``data/benchmark.jsonl`` via one CLI surface.
    """
    from leangrep_bench.benchmark_export import load_items, write_csv

    items = load_items(inp)
    write_csv(items, out, max_len if max_len > 0 else None)
    typer.echo(f"wrote {len(items):,} items to {out}")


@benchmark_app.command("merge")
def benchmark_merge_cmd(
    inputs: list[Path] = typer.Option(
        ...,
        "--input",
        "-i",
        help="One or more per-project benchmark JSONLs (the verifier "
        "writes these to data/<project>/benchmark.jsonl). Order matters "
        "only for deterministic logging.",
    ),
    out: Path = typer.Option(
        Path("data/benchmark.jsonl"),
        "--out",
        help="Merged benchmark JSONL output.",
    ),
) -> None:
    """Concatenate per-project benchmarks into the cross-project file.

    Validates that every input row is a well-formed ``BenchmarkItem`` and
    that IDs are unique across inputs (content-hash IDs collide only on
    truly identical items). Re-runs are deterministic: the same inputs
    in the same order always produce the same output.
    """
    seen_ids: dict[str, Path] = {}
    by_project: dict[str, int] = {}
    dropped_within_file = 0
    total = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for inp in inputs:
            rows = list(read_jsonl_accepted(inp))
            typer.echo(f"  {inp}: {len(rows):,} items")
            for row in rows:
                if row.id in seen_ids:
                    # Within-file dup is benign: verify-pipeline append-only
                    # writes both rows when two proof-steps share the same
                    # (project, goal, hypotheses, prior_tactics, cited)
                    # tuple. Cross-file dup is the structural error we care
                    # about — different benchmark drops claiming the same ID.
                    if seen_ids[row.id] == inp:
                        dropped_within_file += 1
                        continue
                    raise typer.BadParameter(
                        f"duplicate id {row.id!r}: first seen in "
                        f"{seen_ids[row.id]}, again in {inp}"
                    )
                seen_ids[row.id] = inp
                f.write(row.model_dump_json() + "\n")
                key = row.project or "(unset)"
                by_project[key] = by_project.get(key, 0) + 1
                total += 1
    typer.echo(f"wrote {total:,} merged items to {out}")
    if dropped_within_file:
        typer.echo(
            f"  (dropped {dropped_within_file:,} within-file duplicates "
            "— same content-hash on multiple rows of a single input file)"
        )
    typer.echo("by project:")
    for k, v in sorted(by_project.items()):
        typer.echo(f"  {k}: {v:,}")


@app.command("sanity-check")
def sanity_check_cmd(
    benchmark: Path = typer.Option(
        Path("data/benchmark.jsonl"), "--benchmark", help="Benchmark JSONL."
    ),
    corpus_dir: Path = typer.Option(
        Path("data/corpus"), "--corpus-dir", help="Corpus directory."
    ),
    adapters: list[str] = typer.Option(
        ["bm25", "minilm"],
        "--adapter",
        "-a",
        help=f"Adapter(s) to evaluate. Available: {', '.join(list_adapters())}",
    ),
) -> None:
    """End-to-end smoke test: index corpus, run baselines, print Recall@k."""
    scores = run_sanity_check(
        benchmark_path=benchmark,
        corpus_dir=corpus_dir,
        adapter_names=adapters,
    )
    typer.echo(render_table(scores))


@app.command("eval")
def eval_cmd(
    benchmark: Path = typer.Option(
        Path("data/benchmark.jsonl"), "--benchmark", help="Benchmark JSONL."
    ),
    corpus_dir: Path = typer.Option(
        Path("data/corpus"), "--corpus-dir", help="Corpus directory."
    ),
    adapters: list[str] = typer.Option(
        ["bm25", "minilm"],
        "--adapter",
        "-a",
        help=f"Adapter(s) to evaluate. Available: {', '.join(list_adapters())}",
    ),
    out_dir: Path = typer.Option(
        Path("results/run-001"),
        "--out-dir",
        help="Directory for predictions.jsonl, metrics.json, results.md.",
    ),
    k: int = typer.Option(10, "--k", help="Top-k cutoff for retrieval."),
) -> None:
    """Evaluate adapters against the benchmark and write results."""
    metrics = run_eval(
        benchmark_path=benchmark,
        corpus_dir=corpus_dir,
        adapter_names=adapters,
        out_dir=out_dir,
        k=k,
    )
    typer.echo(f"wrote {out_dir / 'predictions.jsonl'}")
    typer.echo(f"wrote {out_dir / 'metrics.json'}")
    typer.echo(f"wrote {out_dir / 'results.md'}")
    typer.echo("---")
    n = metrics.get("n_items", "?")
    typer.echo(f"items: {n}")


if __name__ == "__main__":
    app()

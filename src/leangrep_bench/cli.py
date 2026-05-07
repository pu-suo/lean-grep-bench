import logging
from pathlib import Path

import typer

from leangrep_bench import __version__
from leangrep_bench.adapters.registry import list_adapters
from leangrep_bench.corpus.build import build_corpus
from leangrep_bench.corpus.manifest import write_manifest
from leangrep_bench.corpus.stats import compute_stats, format_stats
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
app.add_typer(corpus_app, name="corpus")
app.add_typer(extract_app, name="extract")
app.add_typer(generate_app, name="generate")
app.add_typer(verify_app, name="verify")
app.add_typer(dojo_app, name="dojo")


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


@corpus_app.command("build-pfr")
def corpus_build_pfr(
    pfr_path: Path = typer.Option(
        ..., "--pfr-path", help="Local PFR checkout."
    ),
    out: Path = typer.Option(..., "--out", help="Output JSONL path."),
    manifest: Path = typer.Option(
        Path("data/corpus/build_manifest.json"),
        "--manifest",
        help="Build manifest output path.",
    ),
) -> None:
    """Parse a PFR checkout into a JSONL of declarations."""
    n = build_corpus(pfr_path, out, source="local:pfr", sub_dir="PFR")
    typer.echo(f"wrote {n:,} declarations to {out}")
    write_manifest(manifest, mathlib_path=None, pfr_path=pfr_path)
    typer.echo(f"updated manifest: {manifest}")


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
    trace_dir: Path = typer.Option(
        Path("data/dojo_trace"),
        "--trace-dir",
        help="Directory of LeanDojo trace JSONLs (or a single .jsonl file).",
    ),
    corpus_dir: Path = typer.Option(
        Path("data/corpus"),
        "--corpus-dir",
        help="Directory with mathlib_declarations.jsonl + pfr_declarations.jsonl.",
    ),
    out: Path = typer.Option(
        Path("data/proof_steps.jsonl"),
        "--out",
        help="Output JSONL path.",
    ),
) -> None:
    """Convert LeanDojo traces into proof-step records."""
    mathlib = corpus_dir / "mathlib_declarations.jsonl"
    pfr = corpus_dir / "pfr_declarations.jsonl"
    index = CorpusIndex.from_jsonls(
        mathlib_path=mathlib if mathlib.exists() else None,
        pfr_path=pfr if pfr.exists() else None,
    )
    summary = extract_proof_steps(trace_dir, index=index, out_path=out)
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
    steps: Path = typer.Option(
        Path("data/proof_steps.jsonl"),
        "--steps",
        help="ProofStep JSONL produced by `extract proof-steps`.",
    ),
    out: Path = typer.Option(
        Path("data/queries.jsonl"), "--out", help="Output queries JSONL."
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
        help="Corpus dir (used for shadowing scenario detection).",
    ),
    audit_out: Path = typer.Option(
        Path("data/queries_audit.md"),
        "--audit-out",
        help="Audit markdown output path.",
    ),
    concurrency: int = typer.Option(
        8, "--concurrency", help="Parallel API workers."
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip the cost-estimate confirmation."
    ),
) -> None:
    """Generate one query per proof step using an LLM. Resume-safe."""
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
    queries: Path = typer.Option(
        Path("data/queries.jsonl"), "--queries", help="Generated queries JSONL."
    ),
    steps: Path = typer.Option(
        Path("data/proof_steps.jsonl"),
        "--steps",
        help="ProofStep JSONL (used to recover context + goal).",
    ),
    corpus_dir: Path = typer.Option(
        Path("data/corpus"),
        "--corpus-dir",
        help="Directory with mathlib_declarations.jsonl + pfr_declarations.jsonl.",
    ),
    out: Path = typer.Option(
        Path("data/benchmark.jsonl"),
        "--out",
        help="Accepted (benchmark) JSONL output path.",
    ),
    rejected: Path = typer.Option(
        Path("data/benchmark_rejected.jsonl"),
        "--rejected",
        help="Rejected items JSONL output path.",
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
    audit_out: Path = typer.Option(
        Path("data/benchmark_audit.md"),
        "--audit-out",
        help="Audit markdown output path.",
    ),
    concurrency: int = typer.Option(
        16, "--concurrency", help="Parallel API workers."
    ),
) -> None:
    """Run the verifier over generated queries; write the accepted benchmark."""
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

from __future__ import annotations

from pathlib import Path

import typer

from leangrep_bench.dojo.load import TraceLoadError, iter_traces
from leangrep_bench.dojo.summarize import summarize as _summarize

dojo_app = typer.Typer(
    help="Inspect LeanDojo trace artifacts produced on a remote Linux box.",
    no_args_is_help=True,
)


@dojo_app.command("validate")
def validate_cmd(
    trace: Path = typer.Option(
        ..., "--trace", help="Path to a trace JSONL file or a directory of them."
    ),
) -> None:
    """Stream the trace through the TacticTrace schema; non-zero exit on failure.

    Use this after rsyncing trace data back from the trace box. The first
    invalid line aborts with file path + 1-based line number in the message.
    """
    try:
        n = 0
        for _ in iter_traces(trace):
            n += 1
    except TraceLoadError as e:
        typer.echo(f"validation failed: {e}", err=True)
        raise typer.Exit(code=1) from e
    typer.echo(f"validated {n:,} tactic traces")


@dojo_app.command("summarize")
def summarize_cmd(
    trace: Path = typer.Option(
        ..., "--trace", help="Path to a trace JSONL file or a directory of them."
    ),
) -> None:
    """Print summary stats for a trace JSONL (or directory of them)."""
    summary = _summarize(trace)
    typer.echo(summary.render())


__all__ = ["dojo_app"]

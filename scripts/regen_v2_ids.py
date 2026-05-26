"""Re-mint v1 benchmark item IDs as v2 content-hash IDs.

Reads ``data/benchmark.jsonl`` (v1 schema), writes:

  - ``data/benchmark.v1.jsonl``      — verbatim archive of the v1 file
  - ``data/benchmark.jsonl``         — same items, new IDs + project/mathlib_sha
  - ``data/id_migration_v1_to_v2.json`` — {old_id: new_id, ...}

The v2 corpus context is read from ``data/corpus/build_manifest.json``;
for Phase 13 the manifest has exactly one entry (PFR), so every item is
tagged with the PFR project + Mathlib SHA.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import typer

from leangrep_bench.corpus.manifest import read_manifest_v2
from leangrep_bench.verify.ids import mint_item_id

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_PATH = REPO_ROOT / "data" / "benchmark.jsonl"
ARCHIVE_PATH = REPO_ROOT / "data" / "benchmark.v1.jsonl"
MIGRATION_PATH = REPO_ROOT / "data" / "id_migration_v1_to_v2.json"
MANIFEST_PATH = REPO_ROOT / "data" / "corpus" / "build_manifest.json"


def _project_name_for_source(source: str, manifest_project_names: set[str]) -> str:
    """Map a v1 ground_truth_source ('mathlib' | 'pfr') back to the project
    the item came from. For Phase 13 every item is a PFR item regardless of
    whether its ground truth is Mathlib or PFR, because the only project
    being traced is PFR.
    """
    del source  # ignored — single-project case
    if len(manifest_project_names) != 1:
        raise NotImplementedError(
            "Phase 13 regen only handles a single-project manifest. "
            "Multi-project regen needs a per-item project field "
            "(added in Phase 15)."
        )
    return next(iter(manifest_project_names))


def regen(*, dry_run: bool = False) -> None:
    manifest = read_manifest_v2(MANIFEST_PATH)
    project_names = {p.project_name for p in manifest.projects}
    project_by_name = {p.project_name: p for p in manifest.projects}

    rows_in = [
        json.loads(line)
        for line in BENCHMARK_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    typer.echo(f"read {len(rows_in):,} v1 items from {BENCHMARK_PATH}")

    migration: dict[str, str] = {}
    rows_out: list[dict] = []
    seen_new_ids: dict[str, str] = {}  # new_id -> first old_id (for collision msgs)

    for row in rows_in:
        project = _project_name_for_source(row["ground_truth_source"], project_names)
        entry = project_by_name[project]
        ctx = row["context"]
        new_id = mint_item_id(
            project=project,
            goal=ctx.get("goal"),
            hypotheses=ctx.get("hypotheses", []),
            prior_tactics=ctx.get("prior_tactics", []),
            cited_lemma_qualified_name=row["ground_truth_name"],
        )
        old_id = row["id"]
        if new_id in seen_new_ids and seen_new_ids[new_id] != old_id:
            raise RuntimeError(
                f"content-hash collision: {seen_new_ids[new_id]!r} and "
                f"{old_id!r} both hash to {new_id!r}"
            )
        seen_new_ids[new_id] = old_id
        migration[old_id] = new_id

        new_row = dict(row)
        new_row["id"] = new_id
        new_row["project"] = project
        new_row["mathlib_sha"] = entry.mathlib_sha
        rows_out.append(new_row)

    typer.echo(f"minted {len(set(migration.values())):,} unique new IDs")
    if len(set(migration.values())) != len(rows_in):
        raise RuntimeError(
            "ID uniqueness failed; duplicates indicate content-identical items"
        )

    if dry_run:
        typer.echo("dry run; no files written")
        return

    if not ARCHIVE_PATH.exists():
        shutil.copy2(BENCHMARK_PATH, ARCHIVE_PATH)
        typer.echo(f"archived v1 file -> {ARCHIVE_PATH}")
    else:
        typer.echo(f"archive already exists at {ARCHIVE_PATH}, not overwriting")

    BENCHMARK_PATH.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows_out) + "\n",
        encoding="utf-8",
    )
    typer.echo(f"wrote v2 benchmark -> {BENCHMARK_PATH}")

    MIGRATION_PATH.write_text(
        json.dumps(migration, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    typer.echo(f"wrote id migration map -> {MIGRATION_PATH}")


def main(
    dry_run: bool = typer.Option(False, "--dry-run", help="Don't write files."),
) -> None:
    """Re-mint v1 benchmark IDs as v2 content-hash IDs."""
    regen(dry_run=dry_run)


if __name__ == "__main__":
    typer.run(main)

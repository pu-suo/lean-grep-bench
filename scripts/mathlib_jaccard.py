"""Print the pairwise Jaccard-overlap matrix over fully-qualified Mathlib
declaration names for each pair of Mathlib SHAs in the v2 manifest.

The matrix has a row/column for every project in the v2 plan, even when
that project hasn't been traced yet — Phase 13 ships with only PFR
populated, so the other rows print 'n/a'. Phase 15 (PNT) and Phase 16
(Carleson, FLT-regular) gradually fill these in.

Usage:

    python scripts/mathlib_jaccard.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import typer

from leangrep_bench.corpus.manifest import read_manifest_v2

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "data" / "corpus" / "build_manifest.json"
UNION_DIR = REPO_ROOT / "data" / "corpus" / "v2"

# v2 roadmap — keep aligned with v2_overview.md. Order matters: PFR first,
# then the planned additions. Phases that add projects also update this list.
V2_PROJECTS: list[str] = ["pfr", "pnt", "carleson", "flt_regular"]


@dataclass
class _ProjectInfo:
    project_name: str
    mathlib_sha: str | None
    mathlib_names: set[str]  # empty if not yet traced


def _load_mathlib_names_for_sha(sha: str) -> set[str]:
    path = UNION_DIR / f"mathlib__{sha}.jsonl"
    if not path.exists():
        return set()
    names: set[str] = set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            names.add(json.loads(line)["qualified_name"])
    return names


def _collect_projects() -> list[_ProjectInfo]:
    manifest = read_manifest_v2(MANIFEST_PATH)
    by_name = {p.project_name: p for p in manifest.projects}
    out: list[_ProjectInfo] = []
    for name in V2_PROJECTS:
        entry = by_name.get(name)
        if entry is None:
            out.append(_ProjectInfo(project_name=name, mathlib_sha=None, mathlib_names=set()))
            continue
        names = _load_mathlib_names_for_sha(entry.mathlib_sha)
        out.append(
            _ProjectInfo(
                project_name=name,
                mathlib_sha=entry.mathlib_sha,
                mathlib_names=names,
            )
        )
    return out


def _jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return float("nan")
    return len(a & b) / len(union)


def main() -> None:
    """Print the Mathlib-SHA Jaccard matrix."""
    projects = _collect_projects()

    col_w = max(len(p.project_name) for p in projects)
    typer.echo(
        "Mathlib SHA Jaccard overlap (rows = projects in v2 roadmap)\n"
    )
    typer.echo(" " * (col_w + 2) + "  ".join(p.project_name.ljust(8) for p in projects))
    for r in projects:
        row_cells: list[str] = []
        for c in projects:
            if not r.mathlib_names or not c.mathlib_names:
                row_cells.append("n/a     ")
                continue
            j = _jaccard(r.mathlib_names, c.mathlib_names)
            row_cells.append(f"{j:.4f}  ")
        typer.echo(r.project_name.ljust(col_w + 2) + "".join(row_cells))

    typer.echo("")
    typer.echo("Populated projects:")
    for p in projects:
        status = (
            f"mathlib_sha={p.mathlib_sha} ({len(p.mathlib_names):,} decls)"
            if p.mathlib_sha
            else "not traced yet"
        )
        typer.echo(f"  {p.project_name}: {status}")


if __name__ == "__main__":
    typer.run(main)

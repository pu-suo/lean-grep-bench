"""Union-corpus builder.

Reads the v2 build manifest and the per-source declaration JSONLs produced
by the legacy ``corpus build-mathlib`` / ``build-pfr`` commands, then writes
a union corpus under ``data/corpus/v2/`` in which every declaration carries
a ``visible_in`` tag identifying which ``(project_name, mathlib_sha)``
contexts can see it.

The shape of the union directory:

    data/corpus/v2/
      mathlib__<mathlib_sha>.jsonl   # one per unique Mathlib SHA
      <project_name>__local.jsonl    # one per project

For Phase 13 with PFR only, this produces exactly two files. The same code
handles N projects with shared or distinct Mathlib SHAs.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

from leangrep_bench.corpus.manifest import BuildManifestV2, read_manifest_v2
from leangrep_bench.corpus.model import (
    NormalizedDeclaration,
    read_jsonl,
    write_jsonl,
)

logger = logging.getLogger(__name__)


def _mathlib_path_for(legacy_corpus_dir: Path, project_name: str) -> Path:
    """Where to read this project's Mathlib snapshot from. Phase 13 keeps the
    pre-existing single Mathlib JSONL; later phases may produce
    per-mathlib-sha snapshots in their own subdirectories.
    """
    # PFR-era convention: one Mathlib JSONL at the root, shared across the
    # one and only project. Reused as-is.
    del project_name
    return legacy_corpus_dir / "mathlib_declarations.jsonl"


def _project_local_path(legacy_corpus_dir: Path, project_name: str) -> Path:
    return legacy_corpus_dir / f"{project_name}_declarations.jsonl"


def build_union_corpus(
    *,
    manifest_path: Path,
    legacy_corpus_dir: Path,
    out_dir: Path,
) -> dict[str, int]:
    """Build the union corpus from a v2 manifest.

    Returns ``{output_file_name: row_count}`` for logging / assertions.
    """
    manifest = read_manifest_v2(manifest_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Group projects by their pinned Mathlib SHA so we emit one Mathlib
    # JSONL per SHA with the union of visible_in tags.
    mathlib_visible_in: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for p in manifest.projects:
        mathlib_visible_in[p.mathlib_sha].append((p.project_name, p.mathlib_sha))

    counts: dict[str, int] = {}

    # --- Mathlib union, one file per Mathlib SHA. ---
    for mathlib_sha, visible_in in mathlib_visible_in.items():
        src = _mathlib_source_for_sha(manifest, mathlib_sha, legacy_corpus_dir)
        out_path = out_dir / f"mathlib__{mathlib_sha}.jsonl"
        n = _rewrite_with_visibility(src, out_path, visible_in=visible_in)
        counts[out_path.name] = n
        logger.info("wrote %s rows to %s", n, out_path)

    # --- Per-project local declarations. ---
    for p in manifest.projects:
        src = _project_local_path(legacy_corpus_dir, p.project_name)
        out_path = out_dir / f"{p.project_name}__local.jsonl"
        n = _rewrite_with_visibility(
            src, out_path, visible_in=[(p.project_name, p.mathlib_sha)]
        )
        counts[out_path.name] = n
        logger.info("wrote %s rows to %s", n, out_path)

        if n != p.decl_count:
            logger.warning(
                "manifest declares %s has decl_count=%d but on-disk JSONL has %d",
                p.project_name,
                p.decl_count,
                n,
            )

    return counts


def _mathlib_source_for_sha(
    manifest: BuildManifestV2,
    mathlib_sha: str,
    legacy_corpus_dir: Path,
) -> Path:
    """Phase 13 convention: only one Mathlib snapshot lives on disk, shared
    across all projects. Verify it matches the requested SHA via the manifest
    and return it.
    """
    matching = [p for p in manifest.projects if p.mathlib_sha == mathlib_sha]
    if not matching:
        raise ValueError(f"no project in manifest pins mathlib_sha={mathlib_sha}")
    project_name = matching[0].project_name
    src = _mathlib_path_for(legacy_corpus_dir, project_name)
    if not src.exists():
        raise FileNotFoundError(
            f"Mathlib JSONL for {project_name} not found at {src}"
        )
    return src


def _rewrite_with_visibility(
    src: Path,
    dst: Path,
    *,
    visible_in: list[tuple[str, str]],
) -> int:
    """Stream ``src`` JSONL into ``dst`` with the ``visible_in`` field set."""

    def _iter() -> Iterator[NormalizedDeclaration]:
        for decl in read_jsonl(src):
            decl.visible_in = list(visible_in)
            yield decl

    return write_jsonl(dst, _iter())


__all__ = ["build_union_corpus"]

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

from leangrep_bench.corpus.model import NormalizedDeclaration, write_jsonl
from leangrep_bench.corpus.parser import parse_file, walk_repo

logger = logging.getLogger(__name__)


def build_corpus(
    repo_root: Path,
    out_path: Path,
    *,
    source: str,
    sub_dir: str | None = None,
) -> int:
    """Walk ``repo_root`` (optionally restricted to ``sub_dir``), parse every
    Lean file, and stream NormalizedDeclaration rows to ``out_path``. Returns
    the number of declarations written.
    """
    repo_root = repo_root.expanduser().resolve()
    walk_root = repo_root if sub_dir is None else (repo_root / sub_dir)

    def _iter() -> Iterator[NormalizedDeclaration]:
        for files_seen, f in enumerate(walk_repo(walk_root), start=1):
            if files_seen % 500 == 0:
                logger.info("parsed %d files...", files_seen)
            try:
                yield from parse_file(f, source=source, repo_root=repo_root)
            except Exception as e:
                logger.warning("skip %s: %s", f, e)

    return write_jsonl(out_path, _iter())

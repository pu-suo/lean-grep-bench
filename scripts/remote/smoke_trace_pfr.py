"""Smoke-test LeanDojo by tracing a single PFR file. Run on the EC2 box only.

Use this BEFORE the full trace. Catches schema-mismatch problems and
environment issues before paying the cost of a multi-hour Mathlib build.

Default target file is ``PFR/HomPFR.lean`` (~14 apply/exact/use/refine
calls; a manageable smoke set). Runbook lists fallbacks if it's
unsuitable for any reason. PFR's commit pin lives in
``remote_trace_pfr.PFR_PINNED_COMMIT`` — both scripts share it.

Output: ``data/dojo_trace/_smoke.jsonl`` plus ``_smoke_failures.json`` if
the file failed to trace at all. Rsync this to the Mac and run
``leangrep-bench dojo validate --trace data/dojo_trace/_smoke.jsonl``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from lean_dojo import LeanGitRepo  # type: ignore[import-not-found]

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from scripts.remote.remote_trace_pfr import (  # noqa: E402
    PFR_PINNED_COMMIT,
    _load_traced_repo,
    _theorem_file,
    _theorem_full_name,
    _theorem_kind,
    _theorem_signature,
    _to_trace,
)

from leangrep_bench.dojo.model import TacticTrace, write_jsonl  # noqa: E402

logger = logging.getLogger("smoke_trace_pfr")
PFR_GITHUB_URL = "https://github.com/teorth/pfr"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--file",
        default="PFR/HomPFR.lean",
        help="PFR-relative source file to trace (e.g. PFR/HomPFR.lean).",
    )
    parser.add_argument(
        "--pfr-commit",
        default=PFR_PINNED_COMMIT,
        help=f"PFR commit SHA. Defaults to PFR_PINNED_COMMIT ({PFR_PINNED_COMMIT[:12]}).",
    )
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "data" / "dojo_trace" / "_smoke.jsonl"),
        help="Output JSONL path.",
    )
    parser.add_argument(
        "--dst-dir",
        default=None,
        help="Override LeanDojo's traced-repo output directory.",
    )
    args = parser.parse_args()

    pfr_commit = args.pfr_commit
    target_file = args.file
    out_path = Path(args.out)

    repo = LeanGitRepo(PFR_GITHUB_URL, pfr_commit)
    logger.info("smoke trace: %s @ %s, file=%s", PFR_GITHUB_URL, pfr_commit, target_file)
    if args.dst_dir:
        logger.warning(
            "--dst-dir is ignored when loading a cached trace; honoring CACHE_DIR env instead"
        )
    traced_repo = _load_traced_repo(repo)

    matches = [
        thm for thm in traced_repo.get_traced_theorems()
        if _theorem_file(thm) == target_file
    ]
    logger.info("found %d theorem(s) in %s", len(matches), target_file)

    if not matches:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sidecar = out_path.with_name("_smoke_failures.json")
        sidecar.write_text(
            json.dumps({target_file: "no theorems found"}, indent=2),
            encoding="utf-8",
        )
        logger.error("no theorems matched %s; wrote %s", target_file, sidecar)
        sys.exit(1)

    traces: list[TacticTrace] = []
    for thm in matches:
        for ti, tac in enumerate(thm.get_traced_tactics()):
            traces.append(
                _to_trace(
                    file_path=target_file,
                    enclosing_decl=_theorem_full_name(thm),
                    enclosing_kind=_theorem_kind(thm),
                    enclosing_signature=_theorem_signature(thm),
                    tac=tac,
                    trace_index=ti,
                )
            )

    n = write_jsonl(out_path, traces)
    logger.info("wrote %d tactic traces to %s", n, out_path)


if __name__ == "__main__":
    main()

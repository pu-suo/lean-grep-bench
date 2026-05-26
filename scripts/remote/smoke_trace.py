"""Smoke-test LeanDojo-v2 by tracing a single file from a Lean 4 repo. Run on
the EC2 trace box only.

The point of this script is to verify, BEFORE paying for a multi-hour full
trace, that:
  1. ``lean_dojo_v2`` installs and imports.
  2. The chosen repo + commit can be cloned and built by lake.
  3. ``trace()`` returns a usable ``TracedRepo``.
  4. ``get_traced_theorems()`` exposes the attributes our projection
     (``trace_repo.py:_to_trace``) expects.

Cost target: ~$1-2 on c7i.2xlarge in 30-60 minutes (most of the time is
elan + lake initial build; the smoke file itself traces in seconds).

Default Phase 15 target: PNT at the v4.28.0 tag, file PrimeNumberTheoremAnd/StrongPNT.lean.

Output: ``data/dojo_trace_pnt/_smoke.jsonl`` plus ``_smoke_failures.json``
on failure. Rsync back to the Mac and inspect with
``leangrep-bench dojo validate --trace data/dojo_trace_pnt/_smoke.jsonl``.

If any field comes through empty or malformed in the smoke output, that's
the signal to revisit ``trace_repo.py``'s defensive attribute probing.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from lean_dojo_v2.lean_dojo.data_extraction.lean import (  # type: ignore[import-not-found]
    LeanGitRepo,
)
from lean_dojo_v2.lean_dojo.data_extraction.trace import (  # type: ignore[import-not-found]
    trace as ld_trace,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from scripts.remote.trace_repo import (  # noqa: E402
    _theorem_file,
    _theorem_full_name,
    _theorem_kind,
    _theorem_signature,
    _to_trace,
)

from leangrep_bench.dojo.model import TacticTrace, write_jsonl  # noqa: E402

logger = logging.getLogger("smoke_trace_v2")

# Phase 15 target: PNT at v4.28.0 tag.
DEFAULT_URL = "https://github.com/AlexKontorovich/PrimeNumberTheoremAnd"
DEFAULT_COMMIT = "537705feac005939629f1ed5a011b50f96478051"  # v4.28.0 tag
DEFAULT_FILE = "PrimeNumberTheoremAnd/StrongPNT.lean"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--commit", default=DEFAULT_COMMIT)
    parser.add_argument("--file", default=DEFAULT_FILE, help="Repo-relative path.")
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "data" / "dojo_trace_pnt" / "_smoke.jsonl"),
    )
    parser.add_argument(
        "--build-deps",
        action="store_true",
        help="Trace Mathlib + transitive deps too. Default off (faster).",
    )
    parser.add_argument(
        "--dst-dir",
        default=None,
        help="LeanDojo-v2 traced-repo output directory.",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    dst_dir = Path(args.dst_dir) if args.dst_dir else None

    repo = LeanGitRepo(args.url, args.commit)
    logger.info(
        "smoke trace: %s @ %s, file=%s, build_deps=%s",
        args.url,
        args.commit,
        args.file,
        args.build_deps,
    )

    traced_repo = ld_trace(repo, dst_dir=dst_dir, build_deps=args.build_deps)
    logger.info("trace() complete")

    matches = [
        thm
        for thm in traced_repo.get_traced_theorems()
        if _theorem_file(thm) == args.file
    ]
    logger.info("found %d theorem(s) in %s", len(matches), args.file)

    if not matches:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sidecar = out_path.with_name("_smoke_failures.json")
        sidecar.write_text(
            json.dumps({args.file: "no theorems found"}, indent=2),
            encoding="utf-8",
        )
        logger.error("no theorems matched %s; wrote %s", args.file, sidecar)
        sys.exit(1)

    traces: list[TacticTrace] = []
    for thm in matches:
        for ti, tac in enumerate(thm.get_traced_tactics()):
            traces.append(
                _to_trace(
                    file_path=args.file,
                    enclosing_decl=_theorem_full_name(thm),
                    enclosing_kind=_theorem_kind(thm),
                    enclosing_signature=_theorem_signature(thm),
                    tac=tac,
                    traced_theorem=thm,
                    trace_index=ti,
                )
            )

    n = write_jsonl(out_path, traces)
    logger.info("wrote %d tactic traces to %s", n, out_path)

    if traces:
        sample = traces[0]
        logger.info("first trace field-health check:")
        logger.info("  tactic:           %r", sample.tactic[:80])
        logger.info("  annotated_tactic: %r", sample.annotated_tactic[:80])
        logger.info("  state_before_pp:  %r", sample.state_before_pp[:120])
        logger.info("  premises:         %d", len(sample.premises))
        if not sample.tactic:
            logger.warning("tactic text is empty — check _tactic_text attribute probing")
        if not sample.state_before_pp:
            logger.warning("state_before_pp is empty — check _state_before attribute probing")
        if not sample.premises:
            logger.warning(
                "no premises captured — LeanDojo-v2 may expose premises at the file level only; "
                "revisit _premises_from_tactic"
            )


if __name__ == "__main__":
    main()

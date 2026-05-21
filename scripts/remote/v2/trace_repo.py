"""Trace any Lean 4 GitHub repo with LeanDojo-v2. Run on the EC2 trace box only.

This is the LeanDojo-v2 successor to ``scripts/remote/remote_trace_pfr.py``.
The original lean-dojo PyPI package is deprecated (ceiling at Lean 4.20.1)
and cannot trace PNT (v4.28), Carleson (v4.30-rc2), or FLT-regular
(v4.30-rc2). LeanDojo-v2 is the actively-maintained replacement.

Generalized over the (url, commit) pair rather than hard-coded to PFR,
since Phase 16 will reuse this for Carleson and FLT-regular. PNT is the
first non-PFR project; Phase 15 smoke-tests this script on a single PNT
file before committing to the full ~$2 EC2 trace.

The output JSONL is the same schema (`leangrep_bench.dojo.model.TacticTrace`)
as v1, so the Mac-side ``leangrep-bench dojo validate`` / extract / generate /
verify pipeline consumes both v1 and v2 traces transparently.

**WHAT IS UNVERIFIED:** This script was written from reading LeanDojo-v2's
source and examples; it has not been executed against a real Lean repo.
Attribute names follow v1's defensive pattern (try several, fall back).
Expect the smoke test to reveal one or two field-name corrections.

Output layout under ``--out-dir``:

    <out_dir>/<safe_file_name>.jsonl
    <out_dir>/_progress.json     (completed files; resume-safe)
    <out_dir>/_failures.json     (per-file errors; non-fatal)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

# ``lean_dojo_v2`` is only importable on the EC2 trace box.
from lean_dojo_v2.lean_dojo.data_extraction.lean import (  # type: ignore[import-not-found]
    LeanGitRepo,
)
from lean_dojo_v2.lean_dojo.data_extraction.trace import (  # type: ignore[import-not-found]
    trace as ld_trace,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from leangrep_bench.dojo.model import (  # noqa: E402
    Premise,
    TacticTrace,
    write_jsonl,
)

logger = logging.getLogger("trace_repo_v2")


def _safe_filename(repo_relative_path: str) -> str:
    """``PNT/PrimeNumberTheoremAnd/StrongPNT.lean`` ->
    ``PNT__PrimeNumberTheoremAnd__StrongPNT.lean.jsonl``."""
    sanitized = repo_relative_path.replace("/", "__").replace("\\", "__")
    return f"{sanitized}.jsonl"


def _atomic_write_jsonl(out_path: Path, traces: list[TacticTrace]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=out_path.name + ".",
        suffix=".tmp",
        dir=str(out_path.parent),
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        write_jsonl(tmp_path, traces)
        os.replace(tmp_path, out_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _load_progress(out_dir: Path) -> set[str]:
    p = out_dir / "_progress.json"
    if not p.exists():
        return set()
    raw = json.loads(p.read_text(encoding="utf-8"))
    files = raw.get("completed_files", [])
    return {str(x) for x in files} if isinstance(files, list) else set()


def _save_progress(out_dir: Path, completed: set[str]) -> None:
    (out_dir / "_progress.json").write_text(
        json.dumps({"completed_files": sorted(completed)}, indent=2),
        encoding="utf-8",
    )


def _load_failures(out_dir: Path) -> dict[str, str]:
    p = out_dir / "_failures.json"
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in raw.items()}


def _save_failures(out_dir: Path, failures: dict[str, str]) -> None:
    (out_dir / "_failures.json").write_text(
        json.dumps(failures, indent=2, sort_keys=True), encoding="utf-8"
    )


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _theorem_file(thm: Any) -> str:
    val = (
        getattr(thm, "file_path", None)
        or getattr(thm, "path", None)
        or getattr(thm, "file", None)
    )
    return str(val) if val else "<unknown>"


def _theorem_full_name(thm: Any) -> str:
    direct = getattr(thm, "full_name", None)
    if direct:
        return str(direct)
    inner = getattr(thm, "theorem", None)
    if inner is not None:
        v = getattr(inner, "full_name", None)
        if v:
            return str(v)
    return ""


def _theorem_kind(thm: Any) -> str:
    """Derive theorem/lemma/example from the AST node class name. LeanDojo-v2's
    ast module defines explicit ``CommandTheoremNode``, ``LemmaNode``,
    ``MathlibTacticLemmaNode`` — same convention as v1."""
    direct = getattr(thm, "kind", None) or getattr(thm, "decl_kind", None)
    if direct:
        return str(direct)
    ast = getattr(thm, "ast", None)
    if ast is None:
        return ""
    type_name = type(ast).__name__
    lower = type_name.lower()
    if "theorem" in lower:
        return "theorem"
    if "lemma" in lower:
        return "lemma"
    if "example" in lower:
        return "example"
    return type_name


def _theorem_signature(thm: Any) -> str | None:
    """Best-effort signature lookup. Backfilled later from the corpus index
    keyed by ``enclosing_decl`` if not directly exposed."""
    for attr in ("signature", "decl_text"):
        v = getattr(thm, attr, None)
        if v:
            return str(v)
    ast = getattr(thm, "ast", None)
    if ast is not None:
        for attr in ("signature", "get_decl_text", "decl_text"):
            v = getattr(ast, attr, None)
            if callable(v):
                try:
                    v = v()
                except Exception:
                    v = None
            if v:
                return str(v)
    return None


def _tactic_text(tac: Any, traced_theorem: Any) -> str:
    """Reconstruct the tactic text. LeanDojo-v2's TacticTrace at the Lean
    level only stores byte positions; the Python-side ``TracedTactic`` should
    expose either ``.tactic`` or a way to slice the source file.
    """
    for attr in ("tactic", "text", "raw"):
        v = getattr(tac, attr, None)
        if v:
            return str(v)
    # Fallback: slice the source file by byte position.
    start = getattr(tac, "start", None) or getattr(tac, "start_pos", None)
    end = getattr(tac, "end", None) or getattr(tac, "end_pos", None)
    lean_file = getattr(traced_theorem, "lean_file", None) or getattr(
        tac, "lean_file", None
    )
    if lean_file is not None and start is not None and end is not None:
        try:
            return str(lean_file[start:end])
        except Exception:
            pass
    return ""


def _state_before(tac: Any) -> str:
    for attr in ("state_before", "stateBefore", "state_before_pp"):
        v = getattr(tac, attr, None)
        if v is not None:
            return str(v)
    return ""


def _state_after(tac: Any) -> str:
    for attr in ("state_after", "stateAfter", "state_after_pp"):
        v = getattr(tac, attr, None)
        if v is not None:
            return str(v)
    return ""


def _annotated_tactic(tac: Any) -> str:
    """LeanDojo-v2 may or may not expose annotated_tactic at the per-tactic
    level. v1 used it to determine which premise is "head"; if absent,
    leave as empty string. Phase 9 will fall back to the first premise in
    ``premises`` ordered by occurrence position.
    """
    for attr in ("annotated_tactic", "get_annotated_tactic"):
        v = getattr(tac, attr, None)
        if callable(v):
            try:
                result = v()
            except Exception:
                continue
            if isinstance(result, tuple) and result:
                return str(result[0])
            if isinstance(result, str):
                return result
        elif v:
            return str(v)
    return ""


def _premises_from_tactic(tac: Any) -> list[Premise]:
    """LeanDojo-v2 stores premises at the file level (PremiseTrace). The
    per-tactic premise list should be exposed via TracedTactic; probing
    several attribute names for compat."""
    out: list[Premise] = []
    seen: set[str] = set()
    candidates: list[Any] = []
    for attr in ("get_premises", "premises", "get_used_premises"):
        val = getattr(tac, attr, None)
        if val is None:
            continue
        if callable(val):
            try:
                val = val()
            except Exception:
                continue
        if isinstance(val, list):
            candidates.extend(val)
    for c in candidates:
        full_name = None
        def_path = None
        def_line: int | None = None
        if isinstance(c, dict):
            full_name = c.get("full_name") or c.get("fullName") or c.get("name")
            def_path = c.get("def_path") or c.get("defPath") or c.get("path")
            pos = c.get("def_pos") or c.get("defPos") or c.get("pos")
            if isinstance(pos, dict):
                def_line = _coerce_int(pos.get("line", pos.get("line_nb")), 0) or None
            elif isinstance(pos, (list, tuple)) and pos:
                def_line = _coerce_int(pos[0], 0) or None
        else:
            full_name = (
                getattr(c, "full_name", None)
                or getattr(c, "fullName", None)
                or getattr(c, "name", None)
            )
            def_path = (
                getattr(c, "def_path", None)
                or getattr(c, "defPath", None)
                or getattr(c, "path", None)
            )
            pos = (
                getattr(c, "def_pos", None)
                or getattr(c, "defPos", None)
                or getattr(c, "pos", None)
            )
            if pos is not None:
                line_attr = getattr(pos, "line_nb", None) or getattr(pos, "line", None)
                if line_attr is not None:
                    def_line = _coerce_int(line_attr, 0) or None
        if not full_name or full_name in seen:
            continue
        seen.add(full_name)
        out.append(
            Premise(
                full_name=str(full_name),
                def_path=str(def_path) if def_path else None,
                def_line=def_line,
            )
        )
    return out


def _to_trace(
    *,
    file_path: str,
    enclosing_decl: str,
    enclosing_kind: str,
    enclosing_signature: str | None,
    tac: Any,
    traced_theorem: Any,
    trace_index: int,
) -> TacticTrace:
    start = (
        getattr(tac, "start", None)
        or getattr(tac, "start_pos", None)
        or getattr(tac, "pos", None)
    )
    end = (
        getattr(tac, "end", None)
        or getattr(tac, "end_pos", None)
        or getattr(tac, "endPos", None)
    )

    def _coord(pos: Any, attr: str, default: int) -> int:
        if pos is None:
            return default
        if isinstance(pos, dict):
            return _coerce_int(pos.get(attr), default)
        return _coerce_int(getattr(pos, attr, default), default)

    line_start = _coord(start, "line_nb", _coord(start, "line", 0))
    line_end = _coord(end, "line_nb", _coord(end, "line", line_start))
    column_start = _coord(start, "column_nb", _coord(start, "column", 0))
    column_end = _coord(end, "column_nb", _coord(end, "column", column_start))

    return TacticTrace(
        file=file_path,
        enclosing_decl=enclosing_decl,
        enclosing_kind=enclosing_kind,
        enclosing_signature=enclosing_signature,
        line_start=line_start,
        line_end=line_end,
        column_start=column_start,
        column_end=column_end,
        tactic=_tactic_text(tac, traced_theorem),
        annotated_tactic=_annotated_tactic(tac),
        state_before_pp=_state_before(tac),
        state_after_pp=_state_after(tac),
        premises=_premises_from_tactic(tac),
        trace_index=trace_index,
    )


def trace_repo(
    *,
    url: str,
    commit: str,
    out_dir: Path,
    include_prefix: str,
    max_files: int | None,
    build_deps: bool,
    dst_dir: Path | None,
) -> tuple[int, int, int]:
    """Returns (files_processed, files_skipped_by_progress, total_tactics)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    progress = _load_progress(out_dir)
    failures = _load_failures(out_dir)

    repo = LeanGitRepo(url, commit)
    logger.info("LeanDojo-v2 trace: %s @ %s", url, commit)
    traced_repo = ld_trace(repo, dst_dir=dst_dir, build_deps=build_deps)
    logger.info("trace() complete; iterating theorems")

    by_file: dict[str, list[Any]] = {}
    total_seen = 0
    for thm in traced_repo.get_traced_theorems():
        total_seen += 1
        f = _theorem_file(thm)
        if not f.startswith(include_prefix):
            continue
        by_file.setdefault(f, []).append(thm)
    logger.info(
        "filtered theorems by prefix %r: %d files match (%d total theorems traced)",
        include_prefix,
        len(by_file),
        total_seen,
    )

    files_processed = 0
    files_skipped = 0
    total_tactics = 0
    for file_idx, file_path in enumerate(sorted(by_file)):
        if max_files is not None and files_processed >= max_files:
            break
        if file_path in progress:
            files_skipped += 1
            continue

        traces: list[TacticTrace] = []
        try:
            for thm in by_file[file_path]:
                enclosing_decl = _theorem_full_name(thm)
                enclosing_kind = _theorem_kind(thm)
                enclosing_signature = _theorem_signature(thm)
                for ti, tac in enumerate(thm.get_traced_tactics()):
                    traces.append(
                        _to_trace(
                            file_path=file_path,
                            enclosing_decl=enclosing_decl,
                            enclosing_kind=enclosing_kind,
                            enclosing_signature=enclosing_signature,
                            tac=tac,
                            traced_theorem=thm,
                            trace_index=ti,
                        )
                    )
        except Exception as e:
            failures[file_path] = f"{type(e).__name__}: {e}"
            _save_failures(out_dir, failures)
            logger.warning("file %s failed: %s", file_path, e)
            continue

        out_path = out_dir / _safe_filename(file_path)
        _atomic_write_jsonl(out_path, traces)
        progress.add(file_path)
        _save_progress(out_dir, progress)
        files_processed += 1
        total_tactics += len(traces)
        logger.info(
            "[%d/%d] %s -> %d tactics",
            file_idx + 1,
            len(by_file),
            file_path,
            len(traces),
        )

    return files_processed, files_skipped, total_tactics


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="GitHub repo URL.")
    parser.add_argument("--commit", required=True, help="Pinned commit SHA.")
    parser.add_argument(
        "--include-prefix",
        required=True,
        help=(
            "Only project theorems whose file path starts with this prefix. "
            "E.g. 'PrimeNumberTheoremAnd/' to keep only PNT files and "
            "exclude Mathlib + deps."
        ),
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Trace output directory. One JSONL per source file plus sidecars.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Stop after this many source files (testing only).",
    )
    parser.add_argument(
        "--build-deps",
        action="store_true",
        help="Also trace dependencies (Mathlib etc.). Default off.",
    )
    parser.add_argument(
        "--dst-dir",
        default=None,
        help="LeanDojo-v2 traced-repo output directory.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    dst_dir = Path(args.dst_dir) if args.dst_dir else None

    processed, skipped, tactics = trace_repo(
        url=args.url,
        commit=args.commit,
        out_dir=out_dir,
        include_prefix=args.include_prefix,
        max_files=args.max_files,
        build_deps=args.build_deps,
        dst_dir=dst_dir,
    )
    logger.info(
        "done: %d files processed (%d skipped), %d tactic invocations -> %s",
        processed,
        skipped,
        tactics,
        out_dir,
    )


if __name__ == "__main__":
    main()

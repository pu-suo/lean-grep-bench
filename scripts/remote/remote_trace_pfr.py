"""Trace the full PFR repo with LeanDojo. Run on the EC2 trace box only.

Pins the PFR commit via the ``PFR_PINNED_COMMIT`` constant below
(``--pfr-commit`` overrides). PFR rewrites master history occasionally, so
this constant is the one place to update when an old commit gets orphaned
upstream. The corpus build manifest is intentionally NOT used as a fallback;
it's a backward-looking record of what v1's corpus was built against, not a
forward-looking pin for tracing.

The script constructs a ``LeanGitRepo`` from ``https://github.com/teorth/pfr``,
runs ``trace()``, walks the traced repo, projects each tactic invocation
into the package's ``TacticTrace`` schema, and writes one JSONL per source
file under ``--out-dir``.

The on-disk layout is ``<out_dir>/<file_safe_name>.jsonl`` plus
``_progress.json`` (completed files) and ``_failures.json`` (per-file errors).
The Mac-side ``leangrep-bench dojo validate``/``summarize`` commands accept
this directory layout directly via ``iter_traces``.

Resume-safe: re-running with the same ``--out-dir`` skips any file already in
``_progress.json``. Single-file errors are logged into ``_failures.json``;
the script never aborts on one bad file.

Schema-drift note: the LeanDojo Python API field names below
(``state_before``, ``state_after``, ``tactic``, ``start_pos``, ``end_pos``,
``get_annotated_tactic``, premise resolution) are the documented names but
have changed across releases. After the smoke run, update :func:`_to_trace`
to match the actually-installed lean-dojo version. The Pydantic schema is
``ConfigDict(extra="ignore")`` so adding extra captured fields will not
break the Mac-side loader.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

# `lean_dojo` is only importable on the EC2 trace box.
from lean_dojo import LeanGitRepo  # type: ignore[import-not-found]
from lean_dojo.data_extraction.trace import (  # type: ignore[import-not-found]
    get_traced_repo_path,
)
from lean_dojo.data_extraction.traced_data import (  # type: ignore[import-not-found]
    TracedRepo,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from leangrep_bench.dojo.model import (  # noqa: E402
    Premise,
    TacticTrace,
    write_jsonl,
)

logger = logging.getLogger("remote_trace_pfr")

PFR_GITHUB_URL = "https://github.com/teorth/pfr"

# Pinned to the latest PFR commit on Lean 4.20.1 — the newest toolchain
# lean-dojo 4.20.0 can trace. PFR has since bumped to 4.21+, but
# lean-dojo's ExtractData.lean uses APIs (Substring, String.Pos, Unit
# universes) that changed in Lean 4.22+ and won't compile against newer
# toolchains. When lean-dojo releases support for newer Lean, bump this
# to a more recent PFR commit. Until then, this is the ceiling.
PFR_PINNED_COMMIT = "5192f5b2b144d0175ec65365e887a78c04733b28"


def _safe_filename(repo_relative_path: str) -> str:
    """``PFR/Mathlib/Foo/Bar.lean`` -> ``PFR__Mathlib__Foo__Bar.lean.jsonl``."""
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
    if not isinstance(files, list):
        return set()
    return {str(x) for x in files}


def _save_progress(out_dir: Path, completed: set[str]) -> None:
    p = out_dir / "_progress.json"
    p.write_text(
        json.dumps(
            {"completed_files": sorted(completed)},
            indent=2,
        ),
        encoding="utf-8",
    )


def _load_failures(out_dir: Path) -> dict[str, str]:
    p = out_dir / "_failures.json"
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in raw.items()}


def _save_failures(out_dir: Path, failures: dict[str, str]) -> None:
    p = out_dir / "_failures.json"
    p.write_text(json.dumps(failures, indent=2, sort_keys=True), encoding="utf-8")


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _premises_from_tactic(tac: Any) -> list[Premise]:
    """Extract premises from a TracedTactic. Best-effort; LeanDojo exposes
    premise info in several places depending on version."""
    out: list[Premise] = []
    seen: set[str] = set()
    candidates: list[Any] = []
    for attr in ("get_premises", "get_annotated_tactic", "premises"):
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
        elif isinstance(val, tuple) and len(val) == 2:
            # get_annotated_tactic returns (annotated_str, list[premise_dict])
            second = val[1]
            if isinstance(second, list):
                candidates.extend(second)
    for c in candidates:
        full_name = None
        def_path = None
        def_line: int | None = None
        if isinstance(c, dict):
            full_name = c.get("full_name") or c.get("name")
            def_path = c.get("def_path") or c.get("path")
            pos = c.get("def_pos") or c.get("pos")
            if isinstance(pos, dict):
                def_line = _coerce_int(pos.get("line", pos.get("line_nb")), 0) or None
            elif isinstance(pos, list | tuple) and pos:
                def_line = _coerce_int(pos[0], 0) or None
        else:
            full_name = getattr(c, "full_name", None) or getattr(c, "name", None)
            def_path = getattr(c, "def_path", None) or getattr(c, "path", None)
            pos = getattr(c, "def_pos", None) or getattr(c, "pos", None)
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


def _annotated(tac: Any) -> str:
    fn = getattr(tac, "get_annotated_tactic", None)
    if fn is None:
        return ""
    try:
        result = fn()
    except Exception:
        return ""
    if isinstance(result, tuple) and result:
        return str(result[0])
    if isinstance(result, str):
        return result
    return ""


def _to_trace(
    *,
    file_path: str,
    enclosing_decl: str,
    enclosing_kind: str,
    enclosing_signature: str | None,
    tac: Any,
    trace_index: int,
) -> TacticTrace:
    # In lean-dojo 4.20.0, TracedTactic exposes `start` / `end` properties
    # delegating to the underlying AST node. Older/newer versions used
    # `start_pos`/`start_`; we tolerate all three.
    start = (
        getattr(tac, "start", None)
        or getattr(tac, "start_pos", None)
        or getattr(tac, "start_", None)
    )
    end = (
        getattr(tac, "end", None)
        or getattr(tac, "end_pos", None)
        or getattr(tac, "end_", None)
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
        tactic=str(getattr(tac, "tactic", "")),
        annotated_tactic=_annotated(tac),
        state_before_pp=str(getattr(tac, "state_before", "")),
        state_after_pp=str(getattr(tac, "state_after", "")),
        premises=_premises_from_tactic(tac),
        trace_index=trace_index,
    )


def _theorem_file(thm: Any) -> str:
    val = (
        getattr(thm, "file_path", None)
        or getattr(thm, "path", None)
        or getattr(thm, "file", None)
    )
    return str(val) if val else "<unknown>"


def _theorem_kind(thm: Any) -> str:
    """Derive 'theorem' / 'lemma' / 'example' from the AST node class.

    lean-dojo 4.20.0's TracedTheorem doesn't expose a ``kind`` attribute;
    the AST node class name (e.g. ``CommandTheoremNode``, ``LemmaNode``,
    ``MathlibTacticLemmaNode``) is the source of truth.
    """
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
    """Best-effort signature lookup. lean-dojo 4.20.0 has no direct exposure;
    phase 9 backfills from the corpus index keyed by enclosing_decl."""
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


def _theorem_full_name(thm: Any) -> str:
    """Full qualified name. In lean-dojo 4.20.0 this lives on the inner
    ``Theorem`` (``thm.theorem.full_name``), not directly on TracedTheorem."""
    direct = getattr(thm, "full_name", None)
    if direct:
        return str(direct)
    inner = getattr(thm, "theorem", None)
    if inner is not None:
        v = getattr(inner, "full_name", None)
        if v:
            return str(v)
    return ""


def _make_repo_or_stub(name: str, url: str, rev: str) -> Any:
    """Construct a ``LeanGitRepo`` if GitHub validates it; otherwise a stub.

    Two things bite the GitHub validation: (1) lake-manifest URLs end with
    ``.git`` which lean-dojo's API call doesn't strip, returning 404; (2)
    some deps (e.g. ``LeanAPAP`` once renamed) genuinely 404. The stub is a
    SimpleNamespace with ``url``/``commit``/``name``, which is enough to
    satisfy lean-dojo's ``get_traced_theorems`` traversal — it only reads
    attributes off the dependency entry, never calls methods that need
    real network access.
    """
    clean_url = url[:-4] if url.endswith(".git") else url
    try:
        repo = LeanGitRepo(clean_url, rev)
        logger.info("backfilled missing dep: %s @ %s", name, rev[:12])
        return repo
    except Exception as e:
        logger.warning(
            "could not validate %s (%s @ %s): %s; using stub",
            name, clean_url, rev, e,
        )
        return SimpleNamespace(url=clean_url, commit=rev, name=name)


def _backfill_missing_deps(traced_repo: Any, cached_path: Path) -> None:
    """Patch ``traced_repo.dependencies`` from ``lake-manifest.json``.

    lean-dojo 4.20.0 only registers direct deps from ``lakefile.toml``;
    transitive deps (e.g. ``batteries`` pulled in via mathlib) are missing,
    causing ``check_sanity()`` and ``get_traced_theorems()`` to crash with
    ``KeyError`` during AST traversal. The lake-manifest that lake itself
    maintains lists every direct + transitive dep with their commits, so
    we backfill from it.
    """
    manifest_path = cached_path / "lake-manifest.json"
    if not manifest_path.exists():
        logger.warning("no lake-manifest.json at %s; cannot backfill deps", cached_path)
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for pkg in manifest.get("packages", []):
        name = pkg.get("name")
        url = pkg.get("url")
        rev = pkg.get("rev")
        if not (isinstance(name, str) and isinstance(url, str) and isinstance(rev, str)):
            continue
        if name in traced_repo.dependencies:
            continue
        traced_repo.dependencies[name] = _make_repo_or_stub(name, url, rev)


def _load_traced_repo(repo: Any) -> Any:
    """Load the cached TracedRepo, skipping ``trace()``'s strict ``check_sanity``.

    lean-dojo's ``trace(repo)`` does load + check_sanity in one call, and
    check_sanity blows up on missing transitive deps (see
    :func:`_backfill_missing_deps`). We split the steps so we can backfill
    deps between load and use, and skip check_sanity.
    """
    cached_path = Path(get_traced_repo_path(repo, True))
    traced_repo = TracedRepo.load_from_disk(cached_path, True)
    _backfill_missing_deps(traced_repo, cached_path)
    return traced_repo


def trace_pfr(
    *,
    pfr_commit: str,
    out_dir: Path,
    max_files: int | None,
    dst_dir: Path | None,
    include_prefix: str,
) -> tuple[int, int, int]:
    """Returns (files_processed, files_skipped_by_progress, total_tactics).

    ``include_prefix`` filters which traced files we project into JSONL.
    LeanDojo traces the project AND all transitive deps (PFR + Mathlib +
    aesop + ...), so without filtering the first alphabetical match is
    something like ``Aesop/BuiltinRules.lean``. Default ``"PFR/"`` keeps
    only PFR's own theorems.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    progress = _load_progress(out_dir)
    failures = _load_failures(out_dir)

    repo = LeanGitRepo(PFR_GITHUB_URL, pfr_commit)
    logger.info("starting trace of %s @ %s", PFR_GITHUB_URL, pfr_commit)
    if dst_dir is not None:
        logger.warning(
            "--dst-dir is ignored when loading a cached trace; honoring CACHE_DIR env instead"
        )
    traced_repo = _load_traced_repo(repo)
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
        include_prefix, len(by_file), total_seen,
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
    parser.add_argument(
        "--pfr-commit",
        default=PFR_PINNED_COMMIT,
        help=f"PFR commit SHA. Defaults to PFR_PINNED_COMMIT ({PFR_PINNED_COMMIT[:12]}).",
    )
    parser.add_argument(
        "--out-dir",
        default=str(REPO_ROOT / "data" / "dojo_trace"),
        help="Trace output directory. One JSONL per source file plus sidecars.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Stop after this many source files (testing only).",
    )
    parser.add_argument(
        "--include-prefix",
        default="PFR/",
        help=(
            "Only project theorems whose file path starts with this prefix. "
            "Default 'PFR/' keeps PFR's own files and excludes Mathlib + deps."
        ),
    )
    parser.add_argument(
        "--dst-dir",
        default=None,
        help="Override LeanDojo's traced-repo output directory.",
    )
    args = parser.parse_args()

    pfr_commit = args.pfr_commit
    out_dir = Path(args.out_dir)
    dst_dir = Path(args.dst_dir) if args.dst_dir else None

    processed, skipped, tactics = trace_pfr(
        pfr_commit=pfr_commit,
        out_dir=out_dir,
        max_files=args.max_files,
        dst_dir=dst_dir,
        include_prefix=args.include_prefix,
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

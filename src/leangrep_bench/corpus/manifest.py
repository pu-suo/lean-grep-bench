from __future__ import annotations

import json
import logging
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _git(args: list[str], cwd: Path) -> str:
    out = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def get_git_sha(repo_path: Path) -> str:
    return _git(["rev-parse", "HEAD"], cwd=repo_path)


def has_uncommitted(repo_path: Path) -> bool:
    return bool(_git(["status", "--porcelain"], cwd=repo_path))


def write_manifest(
    out_path: Path,
    *,
    mathlib_path: Path | None,
    pfr_path: Path | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write a build manifest covering whichever of (mathlib, pfr) is provided.

    If the manifest already exists, the new entry is merged into it so calling
    ``build-mathlib`` and ``build-pfr`` separately still produces a single
    manifest with both SHAs.
    """
    manifest: dict[str, Any] = {}
    if out_path.exists():
        try:
            manifest = json.loads(out_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}

    manifest["built_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    if extra:
        manifest.update(extra)

    for key, repo in (("mathlib", mathlib_path), ("pfr", pfr_path)):
        if repo is None:
            continue
        repo = repo.expanduser().resolve()
        try:
            sha = get_git_sha(repo)
        except subprocess.CalledProcessError:
            sha = "unknown"
        try:
            dirty = has_uncommitted(repo)
        except subprocess.CalledProcessError:
            dirty = False
        if dirty:
            logger.warning(
                "%s checkout has uncommitted changes; manifest SHA may be stale",
                repo,
            )
        manifest[key] = {"path": str(repo), "git_sha": sha, "dirty": dirty}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest

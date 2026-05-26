from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from leangrep_bench.corpus.manifest import read_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "data" / "corpus" / "build_manifest.json"
SCHEMA_PATH = REPO_ROOT / "data" / "corpus" / "build_manifest.schema.json"


def test_live_manifest_validates_against_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    instance = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=instance, schema=schema)


def test_live_manifest_parses_into_typed_model() -> None:
    """Phase 15 expanded the manifest from one project (pfr) to two (pfr +
    pnt). The test asserts on the pfr entry by name so adding a third
    project later (Carleson / FLT-regular) won't require a re-pin."""
    manifest = read_manifest(MANIFEST_PATH)
    assert manifest.schema_version == "v2"
    assert manifest.projects, "manifest must list at least one project"
    by_name = {p.project_name: p for p in manifest.projects}
    pfr = by_name["pfr"]
    assert pfr.project_sha == "80daaf135131403686badd2553dc9b2ca3aabdf8"
    assert pfr.mathlib_sha == "35638f90bcb53a4795506939d39dc5b73f1ac108"
    assert pfr.decl_count == 1077


def test_schema_rejects_missing_required_field(tmp_path: Path) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bad = {
        "schema_version": "v2",
        "built_at": "2026-05-19T00:00:00+00:00",
        "projects": [
            {
                "project_name": "pfr",
                "project_repo_url": "https://github.com/teorth/pfr",
                "project_sha": "80daaf135131403686badd2553dc9b2ca3aabdf8",
                "mathlib_sha": "35638f90bcb53a4795506939d39dc5b73f1ac108",
                "lean_toolchain": "leanprover/lean4:v4.28.0-rc1",
                "license": "Apache-2.0",
            }
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)


def test_schema_rejects_bad_sha_format() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bad = {
        "schema_version": "v2",
        "built_at": "2026-05-19T00:00:00+00:00",
        "projects": [
            {
                "project_name": "pfr",
                "project_repo_url": "https://github.com/teorth/pfr",
                "project_sha": "not-a-sha",
                "mathlib_sha": "35638f90bcb53a4795506939d39dc5b73f1ac108",
                "lean_toolchain": "leanprover/lean4:v4.28.0-rc1",
                "license": "Apache-2.0",
                "decl_count": 1077,
            }
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)

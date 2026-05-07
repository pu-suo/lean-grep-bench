from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from leangrep_bench.corpus.model import NormalizedDeclaration, read_jsonl


@dataclass(frozen=True)
class CorpusEntry:
    qualified_name: str
    short_name: str
    namespace: str | None
    signature: str
    source: Literal["mathlib", "pfr"]


class CorpusIndex:
    """Lookup tables for resolving cited names to corpus declarations."""

    def __init__(self, entries: Iterable[CorpusEntry]) -> None:
        self._by_qual: dict[str, CorpusEntry] = {}
        self._by_short: dict[str, list[CorpusEntry]] = defaultdict(list)
        for e in entries:
            # Last writer wins on qualified name collisions (rare; acceptable).
            self._by_qual[e.qualified_name] = e
            self._by_short[e.short_name].append(e)

    @classmethod
    def from_jsonls(
        cls, mathlib_path: Path | None, pfr_path: Path | None
    ) -> CorpusIndex:
        rows: list[CorpusEntry] = []
        for path, default_source in (
            (mathlib_path, "mathlib"),
            (pfr_path, "pfr"),
        ):
            if path is None or not path.exists():
                continue
            for d in read_jsonl(path):
                src: Literal["mathlib", "pfr"] = (
                    "mathlib" if d.source == "mathlib" else "pfr"
                )
                if default_source == "mathlib" and src != "mathlib":
                    continue
                if default_source == "pfr" and src != "pfr":
                    continue
                rows.append(_to_entry(d, src))
        return cls(rows)

    def lookup_qualified(self, name: str) -> CorpusEntry | None:
        return self._by_qual.get(name)

    def lookup_short(self, name: str) -> list[CorpusEntry]:
        return list(self._by_short.get(name, ()))

    def __contains__(self, name: str) -> bool:
        return name in self._by_qual


def _to_entry(
    d: NormalizedDeclaration, source: Literal["mathlib", "pfr"]
) -> CorpusEntry:
    return CorpusEntry(
        qualified_name=d.qualified_name,
        short_name=d.name,
        namespace=d.namespace,
        signature=d.signature,
        source=source,
    )

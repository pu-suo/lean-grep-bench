from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from leangrep_bench.corpus.model import NormalizedDeclaration, read_jsonl


@dataclass(frozen=True)
class CorpusEntry:
    qualified_name: str
    short_name: str
    namespace: str | None
    signature: str
    # v2 convention: ``"mathlib"`` or ``"local:<project>"``. Old corpus files
    # may carry the legacy bare ``"pfr"`` form — kept as-is.
    source: str


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
        """Legacy v1 loader: read the two separate ``mathlib`` / ``pfr``
        JSONLs. Kept for backward compatibility with v1 callers and tests.
        Prefer :meth:`from_v2_dir` for new code.
        """
        rows: list[CorpusEntry] = []
        for path, default_source in (
            (mathlib_path, "mathlib"),
            (pfr_path, "pfr"),
        ):
            if path is None or not path.exists():
                continue
            for d in read_jsonl(path):
                src = "mathlib" if d.source == "mathlib" else "pfr"
                if default_source == "mathlib" and src != "mathlib":
                    continue
                if default_source == "pfr" and src != "pfr":
                    continue
                rows.append(_to_entry(d, src))
        return cls(rows)

    @classmethod
    def from_v2_dir(
        cls,
        v2_dir: Path,
        *,
        project: str | None = None,
        mathlib_sha: str | None = None,
    ) -> CorpusIndex:
        """v2 loader: read every ``*.jsonl`` under the v2 union corpus dir.

        Each ``NormalizedDeclaration`` already carries its ``source`` field
        as either ``"mathlib"`` or ``"local:<project>"``; we preserve that
        on the resulting :class:`CorpusEntry`.

        When ``project`` and ``mathlib_sha`` are both supplied, the loader
        filters to the declarations visible under that context only — the
        same set the eval-time visibility filter applies. This is the right
        thing at extract time: if PNT cites a name that only PFR's Mathlib
        snapshot contains, that citation should be treated as unresolved
        rather than spuriously matched against an off-context declaration.
        """
        target_ctx: tuple[str, str] | None = None
        if project is not None and mathlib_sha is not None:
            target_ctx = (project, mathlib_sha)
        rows: list[CorpusEntry] = []
        for p in sorted(v2_dir.glob("*.jsonl")):
            for d in read_jsonl(p):
                if target_ctx is not None and not any(
                    (ctx[0], ctx[1]) == target_ctx for ctx in d.visible_in
                ):
                    continue
                rows.append(_to_entry(d, d.source))
        return cls(rows)

    @classmethod
    def auto(
        cls,
        corpus_dir: Path,
        *,
        project: str | None = None,
        mathlib_sha: str | None = None,
    ) -> CorpusIndex:
        """Pick v2 layout when present, else fall back to the v1 layout.

        Allows operator-side commands to stay layout-agnostic. When ``project``
        and ``mathlib_sha`` are supplied and the v2 layout is in use, the
        returned index is restricted to declarations visible under that
        context — see :meth:`from_v2_dir`.
        """
        v2_dir = corpus_dir / "v2"
        if v2_dir.is_dir() and any(v2_dir.glob("*.jsonl")):
            return cls.from_v2_dir(
                v2_dir, project=project, mathlib_sha=mathlib_sha
            )
        return cls.from_jsonls(
            mathlib_path=corpus_dir / "mathlib_declarations.jsonl",
            pfr_path=corpus_dir / "pfr_declarations.jsonl",
        )

    def lookup_qualified(self, name: str) -> CorpusEntry | None:
        return self._by_qual.get(name)

    def lookup_short(self, name: str) -> list[CorpusEntry]:
        return list(self._by_short.get(name, ()))

    def resolve(
        self, name: str, *, enclosing_decl: str | None = None
    ) -> CorpusEntry | None:
        """Resolve a cited name to a corpus entry, reconstructing the
        qualified form when LeanDojo handed us only a short name.

        LeanDojo-v1 ran every premise through Lean's elaborator and stored
        a fully-qualified ``full_name`` (``Real.log_nonneg``). LeanDojo-v2
        skipped that step, so premises like ``log_nonneg`` come through bare
        when the source code wrote them inside an ``open Real`` (or inside a
        ``namespace`` block that lets the short form resolve). Looking those
        up by qualified name alone would silently drop them; this method
        does what the elaborator would: tries the qualified form, then short
        forms biased toward the enclosing decl's namespace, then a unique
        short-name match across the whole corpus.

        Returns ``None`` if no resolution is unambiguous — *e.g.* a bare
        ``le_trans`` cited from a module with no namespace context and 50
        ``*.le_trans`` matches in Mathlib. Those stay unresolved by design;
        the alternative would be picking arbitrarily, which corrupts the
        ground truth.
        """
        # Fast path: qualified hit. Covers everything LeanDojo did elaborate.
        entry = self._by_qual.get(name)
        if entry is not None:
            return entry

        # Namespace-biased short-name resolution. If LeanDojo gave us
        # ``check_row_prop_of_bounds`` from inside ``BKLNW.table_14_check``,
        # try ``BKLNW.check_row_prop_of_bounds`` first — that's the rule Lean
        # itself uses when an identifier appears inside a ``namespace`` block.
        # Walk innermost-to-outermost so ``A.B.foo`` cited from ``A.B.C.thm``
        # is tried as ``A.B.C.foo`` → ``A.B.foo`` → ``A.foo``.
        if enclosing_decl:
            for prefix in _iter_namespace_prefixes(enclosing_decl):
                candidate = f"{prefix}.{name}"
                hit = self._by_qual.get(candidate)
                if hit is not None:
                    return hit

        # Unique short-name match across the whole corpus. This catches
        # ``log_nonneg`` → ``Real.log_nonneg`` when the proof is not inside
        # a ``Real`` namespace block but ``Real.log_nonneg`` is the only
        # ``log_nonneg`` in the corpus.
        short_matches = self._by_short.get(name)
        if short_matches and len(short_matches) == 1:
            return short_matches[0]

        return None

    def __contains__(self, name: str) -> bool:
        return name in self._by_qual


def _iter_namespace_prefixes(qualified_name: str) -> list[str]:
    """Yield the namespace prefixes of ``qualified_name`` from innermost to
    outermost. ``A.B.foo`` → ``["A.B", "A"]``. A bare name yields nothing.

    Matches Lean's identifier-resolution order inside a ``namespace`` block:
    the nearest enclosing namespace wins.
    """
    parts = qualified_name.split(".")
    if len(parts) <= 1:
        return []
    return [".".join(parts[:i]) for i in range(len(parts) - 1, 0, -1)]


def _to_entry(d: NormalizedDeclaration, source: str) -> CorpusEntry:
    return CorpusEntry(
        qualified_name=d.qualified_name,
        short_name=d.name,
        namespace=d.namespace,
        signature=d.signature,
        source=source,
    )

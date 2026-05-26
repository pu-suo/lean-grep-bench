from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from leangrep_bench.corpus.model import NormalizedDeclaration
from leangrep_bench.corpus.to_additive import guess_name, parse_to_additive_attr

DECL_KEYWORDS: tuple[str, ...] = (
    "theorem",
    "lemma",
    "def",
    "abbrev",
    "structure",
    "class",
    "instance",
    "inductive",
    "axiom",
    "opaque",
)

MODIFIERS: tuple[str, ...] = (
    "private",
    "protected",
    "noncomputable",
    "partial",
    "unsafe",
    # ``nonrec`` marks a non-recursive override of a definition that shadows an
    # outer namespace name (e.g. ``nonrec theorem HasDerivAt.comp`` in Mathlib's
    # ``Analysis/Calculus/Deriv/Comp.lean``). Without this we silently lose
    # ~590 decls per Mathlib snapshot.
    "nonrec",
)

SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {".lake", "build", "test", "tests", ".git"}
)

# Identifier characters: ASCII letters, digits, underscore, prime, dot.
# Lean 4 also allows many unicode letters in identifiers (Greek, etc.); the
# parser treats any non-whitespace, non-bracket character as part of an
# identifier when it follows the decl keyword. That is permissive but
# matches the practical reality of Mathlib/PFR code.
_IDENT_CHARS = re.compile(r"[A-Za-z0-9_'.À-￿]")

_DECL_START_RE = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<modifiers>(?:(?:" + "|".join(MODIFIERS) + r")\s+)*)"
    r"(?P<kw>" + "|".join(DECL_KEYWORDS) + r")\b"
    r"(?P<rest>.*)$"
)

_NAMESPACE_RE = re.compile(r"^\s*namespace\s+([^\s]+)\s*$")
_SECTION_RE = re.compile(r"^\s*section(?:\s+([^\s]+))?\s*$")
_END_RE = re.compile(r"^\s*end(?:\s+([^\s]+))?\s*$")


def strip_non_doc_comments(text: str) -> str:
    """Replace ``-- line`` and ``/- block -/`` comments with whitespace, preserving
    newlines and total length so line/column indices into the result correspond
    to those of the original text. ``/-- doc -/`` blocks are kept verbatim.
    ``/-! module-doc -/`` blocks are dropped like normal block comments.
    """
    n = len(text)
    out: list[str] = []
    i = 0
    in_string = False
    block_depth = 0

    while i < n:
        if block_depth > 0:
            if i + 1 < n and text[i] == "/" and text[i + 1] == "-":
                block_depth += 1
                out.append("  ")
                i += 2
                continue
            if i + 1 < n and text[i] == "-" and text[i + 1] == "/":
                block_depth -= 1
                out.append("  ")
                i += 2
                continue
            out.append("\n" if text[i] == "\n" else " ")
            i += 1
            continue

        c = text[i]

        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
            continue

        # /-- docstring start: preserve verbatim until matching -/
        if (
            i + 2 < n
            and text[i] == "/"
            and text[i + 1] == "-"
            and text[i + 2] == "-"
            and (i + 3 >= n or text[i + 3] != "-")
        ):
            j = i + 3
            depth = 1
            while j < n:
                if j + 1 < n and text[j] == "/" and text[j + 1] == "-":
                    depth += 1
                    j += 2
                    continue
                if j + 1 < n and text[j] == "-" and text[j + 1] == "/":
                    depth -= 1
                    j += 2
                    if depth == 0:
                        break
                    continue
                j += 1
            out.append(text[i:j])
            i = j
            continue

        # /-! module doc: treat as block comment
        if i + 2 < n and text[i] == "/" and text[i + 1] == "-" and text[i + 2] == "!":
            block_depth = 1
            out.append("   ")
            i += 3
            continue

        # /- block comment
        if i + 1 < n and text[i] == "/" and text[i + 1] == "-":
            block_depth = 1
            out.append("  ")
            i += 2
            continue

        # -- line comment
        if i + 1 < n and text[i] == "-" and text[i + 1] == "-":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
            continue

        if c == '"':
            in_string = True
            out.append(c)
            i += 1
            continue

        out.append(c)
        i += 1

    return "".join(out)


def _read_docstring_block(lines: list[str], start_idx: int) -> tuple[str, int] | None:
    """If ``lines[start_idx]`` opens a ``/-- ... -/`` block, return (content, end_idx)
    where ``end_idx`` is the index of the line *after* the closing ``-/``.
    Otherwise return None.
    """
    line = lines[start_idx]
    stripped = line.lstrip()
    if not stripped.startswith("/--"):
        return None

    # Look for closing -/ from start_idx onward.
    text = "\n".join(lines[start_idx:])
    open_pos = line.find("/--")
    rest = text[open_pos + 3 :]
    close_pos = rest.find("-/")
    if close_pos < 0:
        return None

    content = rest[:close_pos].strip()
    consumed_chars = open_pos + 3 + close_pos + 2
    consumed_text = text[:consumed_chars]
    end_idx = start_idx + consumed_text.count("\n") + 1
    return content, end_idx


def _read_attribute_block(
    lines: list[str], start_idx: int
) -> tuple[int, int] | None:
    """Locate the end of an ``@[...]`` attribute block beginning at
    ``lines[start_idx]``.

    Returns ``(end_line, end_col)`` where ``end_line`` is the line index
    containing the closing ``]`` and ``end_col`` is the column immediately
    after it. The caller may then re-process ``lines[end_line][end_col:]``
    so that same-line ``@[simp] theorem foo : ...`` declarations are not
    silently dropped.

    For bare ``@something`` attributes (no brackets) the block is the
    entire current line. Returns ``None`` if the line is not an attribute.
    """
    line = lines[start_idx]
    stripped = line.lstrip()
    if not stripped.startswith("@"):
        return None
    text = "\n".join(lines[start_idx:])
    bracket_pos = text.find("[")
    if bracket_pos < 0 or bracket_pos > len(line):
        # `@something` without brackets — single-line attribute. Treat the
        # whole line as the consumed block.
        return start_idx, len(line)
    depth = 0
    i = bracket_pos
    while i < len(text):
        ch = text[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                consumed = text[: i + 1]
                end_line = start_idx + consumed.count("\n")
                last_nl = consumed.rfind("\n")
                end_col = (
                    len(consumed) if last_nl < 0 else len(consumed) - last_nl - 1
                )
                return end_line, end_col
        i += 1
    # Unterminated — treat the start line as the consumed block so the
    # scanner can recover at the next line.
    return start_idx, len(line)


def _extract_name(rest: str) -> tuple[str | None, str]:
    """Given the text after a declaration keyword (the same line), pull off the
    declaration's short name (which may contain dots) and return (name, remainder).
    Returns (None, rest) for anonymous declarations (e.g. ``instance : Foo``).
    """
    s = rest.lstrip()
    if not s:
        return None, ""

    # Anonymous instance / def-level declaration with leading ``:``.
    if s.startswith(":") or s.startswith("(") or s.startswith("{") or s.startswith("["):
        return None, s

    # Collect identifier characters.
    j = 0
    while j < len(s) and _IDENT_CHARS.match(s[j]):
        j += 1
    if j == 0:
        return None, s
    name = s[:j].rstrip(".")
    return (name or None, s[j:])


def _read_signature(
    lines: list[str], start_idx: int, signature_start_col: int
) -> tuple[str, int]:
    """Read the declaration's signature starting at line ``start_idx``,
    column ``signature_start_col`` of the (comment-stripped) text.

    The signature ends at the first occurrence of ``:=`` (definition body)
    or the ``where`` keyword (introducing a body), or end-of-file. We balance
    parens/brackets/braces so that `` :=`` inside binders or types doesn't
    trip the scan.

    Returns the trimmed signature text and the line index *after* the line
    on which the terminator was found (or after the last line scanned).
    """
    paren = 0
    bracket = 0
    brace = 0
    pieces: list[str] = []
    i = start_idx
    first = True
    while i < len(lines):
        line = lines[i]
        if first:
            seg = line[signature_start_col:]
            first = False
        else:
            seg = line
        # Walk seg looking for terminators while tracking brackets.
        j = 0
        L = len(seg)
        terminator_pos = -1
        while j < L:
            ch = seg[j]
            if paren == 0 and bracket == 0 and brace == 0:
                # ``:=``
                if ch == ":" and j + 1 < L and seg[j + 1] == "=":
                    terminator_pos = j
                    break
                # ``where`` as a standalone keyword
                if ch == "w" and seg[j : j + 5] == "where":
                    before = seg[j - 1] if j > 0 else " "
                    after = seg[j + 5] if j + 5 < L else " "
                    if (
                        not before.isalnum()
                        and before != "_"
                        and not after.isalnum()
                        and after != "_"
                    ):
                        terminator_pos = j
                        break
                # ``deriving`` — also ends a signature for inductive/structure
                if ch == "d" and seg[j : j + 8] == "deriving":
                    before = seg[j - 1] if j > 0 else " "
                    after = seg[j + 8] if j + 8 < L else " "
                    if (
                        not before.isalnum()
                        and before != "_"
                        and not after.isalnum()
                        and after != "_"
                    ):
                        terminator_pos = j
                        break
            if ch == "(":
                paren += 1
            elif ch == ")":
                paren = max(0, paren - 1)
            elif ch == "[":
                bracket += 1
            elif ch == "]":
                bracket = max(0, bracket - 1)
            elif ch == "{":
                brace += 1
            elif ch == "}":
                brace = max(0, brace - 1)
            j += 1

        if terminator_pos >= 0:
            pieces.append(seg[:terminator_pos])
            return _normalize_signature("\n".join(pieces)), i + 1
        pieces.append(seg)
        i += 1
        # Sanity bound — declarations spanning >400 lines are almost certainly
        # parser confusion.
        if i - start_idx > 400:
            break
    return _normalize_signature("\n".join(pieces)), i


def _normalize_signature(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_file(
    path: Path, source: str, repo_root: Path
) -> Iterator[NormalizedDeclaration]:
    """Yield NormalizedDeclaration for every top-level declaration in ``path``.

    ``source`` is the corpus tag (``"mathlib"`` or ``"local:pfr"``) and
    ``repo_root`` is used to compute the file path stored in the row.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    cleaned = strip_non_doc_comments(text)
    lines = cleaned.split("\n")

    rel_path = str(path.relative_to(repo_root))

    # Stack entries: (kind, name) where kind in {"namespace", "section"}.
    scope_stack: list[tuple[str, str | None]] = []
    pending_doc: str | None = None
    # Set when a ``@[to_additive ...]`` is in flight on the next decl.
    # Tuple is (explicit_name_or_None,).
    pending_to_additive: tuple[str | None] | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Docstring block — capture and continue.
        doc = _read_docstring_block(lines, i)
        if doc is not None:
            pending_doc, end_idx = doc
            i = end_idx
            continue

        # Attribute block (``@[...]`` possibly multi-line) — skip but keep doc.
        if stripped.startswith("@"):
            block = _read_attribute_block(lines, i)
            if block is not None:
                end_line, end_col = block
                # Capture the bracket payload before blanking it out so we
                # can detect a ``@[to_additive]`` clause on the next decl.
                attr_text = _slice_attribute_payload(lines, i, end_line, end_col)
                if attr_text is not None:
                    is_ta, explicit = parse_to_additive_attr(attr_text)
                    if is_ta:
                        pending_to_additive = (explicit,)
                # Blank out the attribute span. Replacing with whitespace
                # preserves column offsets so that ``signature_start_col``
                # arithmetic in ``_read_signature`` still aligns when a
                # declaration follows on the same line.
                for k in range(i, end_line):
                    lines[k] = " " * len(lines[k])
                tail = lines[end_line][end_col:]
                if tail.strip():
                    lines[end_line] = " " * end_col + tail
                    i = end_line
                else:
                    i = end_line + 1
                continue

        # Namespace/section/end tracking.
        m_ns = _NAMESPACE_RE.match(line)
        if m_ns is not None:
            scope_stack.append(("namespace", m_ns.group(1)))
            pending_doc = None
            pending_to_additive = None
            i += 1
            continue
        m_sec = _SECTION_RE.match(line)
        if m_sec is not None:
            scope_stack.append(("section", m_sec.group(1)))
            pending_doc = None
            pending_to_additive = None
            i += 1
            continue
        m_end = _END_RE.match(line)
        if m_end is not None:
            target = m_end.group(1)
            if target is None:
                if scope_stack:
                    scope_stack.pop()
            else:
                # Pop until the matching named entry.
                for idx in range(len(scope_stack) - 1, -1, -1):
                    if scope_stack[idx][1] == target:
                        del scope_stack[idx:]
                        break
                else:
                    # Dotted form like ``end Foo.Bar`` — pop matching prefix.
                    parts = target.split(".")
                    if len(parts) > 1:
                        for idx in range(len(scope_stack) - len(parts), -1, -1):
                            if idx < 0:
                                break
                            names = [
                                e[1] for e in scope_stack[idx : idx + len(parts)]
                            ]
                            if names == parts:
                                del scope_stack[idx:]
                                break
            pending_doc = None
            pending_to_additive = None
            i += 1
            continue

        # Declaration?
        m = _DECL_START_RE.match(line)
        if m is None:
            # Other top-level forms (variable, open, import, etc.) — clear
            # pending docstring only on truly non-attribute non-blank content.
            if not stripped.startswith("/--") and not stripped.startswith("@"):
                pending_doc = None
                pending_to_additive = None
            i += 1
            continue

        kw = m.group("kw")
        rest_text = m.group("rest")
        # Compute column where ``rest_text`` begins in the original line.
        rest_col = m.end("kw")

        name, after_name = _extract_name(rest_text)
        # Compute column where the signature begins (after the name).
        sig_col = rest_col + (len(rest_text) - len(after_name))

        if kw == "example":
            pending_doc = None
            pending_to_additive = None
            i += 1
            continue

        # Skip if the entire token isn't actually a declaration (e.g. ``def`` as
        # a substring inside another keyword would have been excluded by the
        # word boundary, so this is mostly defensive).
        if not name and kw not in {"instance"}:
            pending_doc = None
            pending_to_additive = None
            i += 1
            continue

        signature, next_i = _read_signature(lines, i, sig_col)

        # Build qualified name.
        ns_parts = [s[1] for s in scope_stack if s[0] == "namespace" and s[1]]
        ns_prefix = ".".join(ns_parts) if ns_parts else None

        if name is None:
            # Anonymous instance — synthesize a stable name from file:line.
            base = path.stem
            anon = f"_inst_{base}_{i + 1}"
            short = anon
            qualified = f"{ns_prefix}.{anon}" if ns_prefix else anon
        else:
            short = name.split(".")[-1]
            qualified = f"{ns_prefix}.{name}" if ns_prefix else name

        namespace = (
            qualified[: -(len(short) + 1)] if qualified.endswith("." + short) else None
        )

        docstring = pending_doc if pending_doc else None
        signature_clean = signature.strip()
        missing: list[str] = []
        if not signature_clean:
            missing.append("signature")
        if not docstring:
            missing.append("docstring")
        has_complete_info = bool(signature_clean)

        yield NormalizedDeclaration(
            id=f"{source}::{qualified}",
            source=source,
            qualified_name=qualified,
            name=short,
            namespace=namespace,
            kind=kw,
            signature=signature_clean,
            docstring=docstring,
            informal=None,
            file=rel_path,
            line=i + 1,
            has_complete_info=has_complete_info,
            missing_fields=missing,
        )

        # If this decl carried a ``@[to_additive]`` attribute, synthesize the
        # additive twin so the corpus indexes both names. The signature/
        # docstring carry over verbatim; only the name and qualified name
        # are mangled. ``to_additive`` doesn't apply to anonymous instances.
        if pending_to_additive is not None and name is not None:
            (explicit,) = pending_to_additive
            # Use the *full* namespace of the original — including any dotted
            # prefix that appeared in the decl name itself (e.g.
            # ``theorem List.measurable_prod`` declared at file scope still
            # belongs to the ``List`` namespace).
            twin_qual, twin_short, twin_ns = _resolve_to_additive_name(
                explicit=explicit,
                original_short=short,
                original_namespace=namespace,
            )
            yield NormalizedDeclaration(
                id=f"{source}::{twin_qual}",
                source=source,
                qualified_name=twin_qual,
                name=twin_short,
                namespace=twin_ns,
                kind=kw,
                signature=signature_clean,
                docstring=docstring,
                informal=None,
                file=rel_path,
                line=i + 1,
                has_complete_info=has_complete_info,
                missing_fields=missing,
            )

        pending_doc = None
        pending_to_additive = None
        i = max(next_i, i + 1)


def _slice_attribute_payload(
    lines: list[str], start_line: int, end_line: int, end_col: int
) -> str | None:
    """Return the text *between* ``@[`` and the matching ``]`` for an
    attribute whose closing bracket is at ``lines[end_line][end_col-1]``.
    Returns ``None`` for bracketless ``@something`` attributes (which can
    never be ``@to_additive``)."""
    if start_line == end_line:
        line = lines[start_line]
        bracket_pos = line.find("[")
        if bracket_pos < 0 or bracket_pos >= end_col - 1:
            return None
        return line[bracket_pos + 1 : end_col - 1]
    first = lines[start_line]
    bracket_pos = first.find("[")
    if bracket_pos < 0:
        return None
    middle = "\n".join(lines[start_line + 1 : end_line])
    last = lines[end_line][: end_col - 1]
    pieces = [first[bracket_pos + 1 :]]
    if middle:
        pieces.append(middle)
    pieces.append(last)
    return "\n".join(pieces)


def _resolve_to_additive_name(
    *,
    explicit: str | None,
    original_short: str,
    original_namespace: str | None,
) -> tuple[str, str, str | None]:
    """Compute (qualified, short, namespace) for an additive twin.

    Rules (mirroring ``to_additive``'s argument handling):
      * Explicit qualified names (containing a ``.``) are taken verbatim.
      * Explicit unqualified names live in the original's namespace.
      * No explicit name → mangle the original short name via ``guess_name``
        and prepend the original's namespace.
    """
    if explicit is not None and "." in explicit:
        qualified = explicit
        short = explicit.rsplit(".", 1)[-1]
        ns = explicit[: -(len(short) + 1)] or None
        return qualified, short, ns
    short = explicit if explicit is not None else guess_name(original_short)
    qualified = (
        f"{original_namespace}.{short}" if original_namespace else short
    )
    ns = original_namespace
    return qualified, short, ns


def walk_repo(root: Path) -> Iterator[Path]:
    """Yield .lean files under ``root``, skipping build/test/hidden directories."""
    root = root.resolve()
    for p in root.rglob("*.lean"):
        # Skip files under any excluded directory.
        rel = p.relative_to(root)
        parts = rel.parts
        if any(part.startswith(".") for part in parts[:-1]):
            continue
        if any(part in SKIP_DIR_NAMES for part in parts):
            continue
        yield p

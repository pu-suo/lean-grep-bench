from __future__ import annotations

from pathlib import Path

from leangrep_bench.corpus.parser import parse_file, strip_non_doc_comments

FIXTURE = Path(__file__).parent / "fixtures" / "sample.lean"


def test_parser_finds_all_decls_in_fixture() -> None:
    decls = list(parse_file(FIXTURE, source="test", repo_root=FIXTURE.parent))
    by_qname = {d.qualified_name: d for d in decls}

    # 5 declarations: theorem, lemma, def, structure, anonymous instance.
    assert len(decls) == 5

    thm = by_qname["Foo.Bar.id_thm"]
    assert thm.kind == "theorem"
    assert thm.namespace == "Foo.Bar"
    assert thm.name == "id_thm"
    assert "x = x" in thm.signature
    assert thm.docstring == "The classic identity lemma."
    assert thm.has_complete_info
    assert thm.missing_fields == []

    lem = by_qname["Foo.Bar.succ_lemma"]
    assert lem.kind == "lemma"
    assert "n + 1 = Nat.succ n" in lem.signature
    assert lem.docstring is None
    assert "docstring" in lem.missing_fields

    df = by_qname["Foo.Bar.double"]
    assert df.kind == "def"
    assert df.name == "double"

    s = by_qname["Foo.Bar.Point"]
    assert s.kind == "structure"

    inst = next(d for d in decls if d.kind == "instance")
    assert inst.namespace == "Foo.Bar"
    assert inst.name.startswith("_inst_")


def test_strip_comments_preserves_docstrings_and_lengths() -> None:
    text = "/-- doc -/\n-- line\n/- block -/\nfoo\n"
    out = strip_non_doc_comments(text)
    assert len(out) == len(text)
    assert "/-- doc -/" in out
    # Line and block comments replaced with whitespace.
    assert "-- line" not in out
    assert "block" not in out
    # Newlines preserved so line numbers still align.
    assert out.count("\n") == text.count("\n")


def test_namespace_pop_on_end_with_dotted_name(tmp_path: Path) -> None:
    src = tmp_path / "x.lean"
    src.write_text(
        "namespace Foo\n"
        "namespace Bar\n"
        "theorem inside : True := trivial\n"
        "end Foo.Bar\n"
        "theorem outside : True := trivial\n",
        encoding="utf-8",
    )
    decls = list(parse_file(src, source="test", repo_root=tmp_path))
    by_q = {d.qualified_name for d in decls}
    assert "Foo.Bar.inside" in by_q
    assert "outside" in by_q


def test_same_line_attribute_does_not_swallow_decl(tmp_path: Path) -> None:
    """``@[simp] theorem foo`` on a single line was previously dropped because
    ``_read_attribute_block`` advanced past the entire line. Regression check."""
    src = tmp_path / "x.lean"
    src.write_text(
        "namespace N\n"
        "@[simp] theorem fst_smul (a : Nat) : a + 0 = a := by simp\n"
        "@[simp, gcongr] lemma snd_smul (a : Nat) : 0 + a = a := by simp\n"
        "@[reducible] def triple (n : Nat) : Nat := 3 * n\n"
        "end N\n",
        encoding="utf-8",
    )
    decls = list(parse_file(src, source="test", repo_root=tmp_path))
    by_q = {d.qualified_name: d for d in decls}
    assert "N.fst_smul" in by_q
    assert by_q["N.fst_smul"].kind == "theorem"
    assert "a + 0 = a" in by_q["N.fst_smul"].signature
    assert "N.snd_smul" in by_q
    assert by_q["N.snd_smul"].kind == "lemma"
    assert "N.triple" in by_q
    assert by_q["N.triple"].kind == "def"


def test_multiline_attribute_followed_by_decl(tmp_path: Path) -> None:
    """A ``@[...]`` block that spans multiple lines should not lose the
    declaration that follows."""
    src = tmp_path / "x.lean"
    src.write_text(
        "namespace N\n"
        "@[simp,\n"
        "  inline]\n"
        "theorem multi (a : Nat) : a = a := rfl\n"
        "end N\n",
        encoding="utf-8",
    )
    decls = list(parse_file(src, source="test", repo_root=tmp_path))
    by_q = {d.qualified_name for d in decls}
    assert "N.multi" in by_q


def test_attribute_with_decl_on_closing_line(tmp_path: Path) -> None:
    """``@[\\n attr\\n] theorem foo`` — closing ``]`` on a line that also
    contains the declaration should still be picked up."""
    src = tmp_path / "x.lean"
    src.write_text(
        "namespace N\n"
        "@[simp\n"
        "  ] theorem trailing (a : Nat) : a = a := rfl\n"
        "end N\n",
        encoding="utf-8",
    )
    decls = list(parse_file(src, source="test", repo_root=tmp_path))
    by_q = {d.qualified_name for d in decls}
    assert "N.trailing" in by_q


def test_to_additive_synthesizes_twin_via_mangling(tmp_path: Path) -> None:
    src = tmp_path / "x.lean"
    src.write_text(
        "namespace Finset\n"
        "@[to_additive (attr := congr)]\n"
        "theorem prod_congr (h : s = t) : True := trivial\n"
        "end Finset\n",
        encoding="utf-8",
    )
    by_q = {
        d.qualified_name: d
        for d in parse_file(src, source="test", repo_root=tmp_path)
    }
    assert "Finset.prod_congr" in by_q
    assert "Finset.sum_congr" in by_q
    twin = by_q["Finset.sum_congr"]
    assert twin.namespace == "Finset"
    assert twin.signature == by_q["Finset.prod_congr"].signature


def test_to_additive_uses_explicit_name(tmp_path: Path) -> None:
    src = tmp_path / "x.lean"
    src.write_text(
        "namespace Finset\n"
        "@[to_additive (attr := gcongr) sum_le_sum]\n"
        "theorem prod_le_prod' (h : ∀ i, f i ≤ g i) : True := trivial\n"
        "end Finset\n",
        encoding="utf-8",
    )
    by_q = {
        d.qualified_name
        for d in parse_file(src, source="test", repo_root=tmp_path)
    }
    assert "Finset.prod_le_prod'" in by_q
    assert "Finset.sum_le_sum" in by_q
    # The mangled (no-explicit-name) form is *not* emitted when an explicit
    # name overrides it.
    assert "Finset.sum_le_sum'" not in by_q


def test_to_additive_explicit_qualified_name_skips_namespace(tmp_path: Path) -> None:
    src = tmp_path / "x.lean"
    src.write_text(
        "namespace Foo\n"
        "@[to_additive Bar.add_le_add]\n"
        "theorem mul_le_mul (h : a ≤ b) : True := trivial\n"
        "end Foo\n",
        encoding="utf-8",
    )
    by_q = {
        d.qualified_name: d
        for d in parse_file(src, source="test", repo_root=tmp_path)
    }
    twin = by_q["Bar.add_le_add"]
    assert twin.namespace == "Bar"
    assert twin.name == "add_le_add"


def test_to_additive_with_dotted_decl_name_preserves_namespace(tmp_path: Path) -> None:
    """``theorem List.measurable_prod`` declared at file scope still belongs
    to the ``List`` namespace. The additive twin must be ``List.measurable_sum``,
    not just ``measurable_sum`` — preserving the dotted prefix from the
    multiplicative source name."""
    src = tmp_path / "x.lean"
    src.write_text(
        "@[to_additive]\n"
        "theorem List.measurable_prod (l : List Nat) : True := trivial\n",
        encoding="utf-8",
    )
    by_q = {
        d.qualified_name: d
        for d in parse_file(src, source="test", repo_root=tmp_path)
    }
    assert "List.measurable_prod" in by_q
    assert "List.measurable_sum" in by_q
    twin = by_q["List.measurable_sum"]
    assert twin.namespace == "List"
    assert twin.name == "measurable_sum"


def test_to_additive_does_not_leak_across_decls(tmp_path: Path) -> None:
    src = tmp_path / "x.lean"
    src.write_text(
        "namespace N\n"
        "@[to_additive]\n"
        "theorem prod_one : True := trivial\n"
        "theorem unrelated : True := trivial\n"
        "end N\n",
        encoding="utf-8",
    )
    decls = list(parse_file(src, source="test", repo_root=tmp_path))
    by_q = {d.qualified_name for d in decls}
    assert "N.prod_one" in by_q
    assert "N.sum_zero" in by_q
    assert "N.unrelated" in by_q
    # No twin for the unrelated decl.
    assert sum(d.name == "unrelated" for d in decls) == 1


def test_anonymous_instance_gets_synthetic_name(tmp_path: Path) -> None:
    src = tmp_path / "x.lean"
    src.write_text(
        "namespace N\n"
        "instance : Inhabited Nat := ⟨0⟩\n"
        "end N\n",
        encoding="utf-8",
    )
    decls = list(parse_file(src, source="test", repo_root=tmp_path))
    assert len(decls) == 1
    assert decls[0].kind == "instance"
    assert decls[0].namespace == "N"
    assert decls[0].name.startswith("_inst_")

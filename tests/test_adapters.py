from __future__ import annotations

from pathlib import Path
from typing import cast

import numpy as np
import pytest

from leangrep_bench.adapters.base import RetrievalResult
from leangrep_bench.adapters.bm25 import BM25Adapter, tokenize
from leangrep_bench.adapters.dense import DenseAdapter
from leangrep_bench.adapters.registry import build_adapter, list_adapters
from leangrep_bench.corpus.model import NormalizedDeclaration


def _decl(qual: str, sig: str, doc: str | None = None) -> NormalizedDeclaration:
    return NormalizedDeclaration(
        id=f"test::{qual}",
        source="mathlib",
        qualified_name=qual,
        name=qual.split(".")[-1],
        namespace=".".join(qual.split(".")[:-1]) or None,
        kind="theorem",
        signature=sig,
        docstring=doc,
        informal=None,
        file="X.lean",
        line=1,
        has_complete_info=True,
        missing_fields=[],
    )


def _fixture_corpus() -> list[NormalizedDeclaration]:
    return [
        _decl(
            "Foo.add_comm",
            "(a b : Nat) : a + b = b + a",
            "Addition is commutative.",
        ),
        _decl(
            "Foo.mul_comm",
            "(a b : Nat) : a * b = b * a",
            "Multiplication is commutative.",
        ),
        _decl(
            "Foo.add_assoc",
            "(a b c : Nat) : a + b + c = a + (b + c)",
            "Addition is associative.",
        ),
        _decl(
            "Foo.zero_add",
            "(a : Nat) : 0 + a = a",
            "Zero is left identity for addition.",
        ),
    ]


def test_tokenize_basics() -> None:
    assert tokenize("Foo.bar baz_qux") == ["foo", "bar", "baz_qux"]
    assert tokenize("a, b, c") == []  # too short
    assert tokenize("HELLO world") == ["hello", "world"]


def test_bm25_finds_expected_top_match() -> None:
    adapter = BM25Adapter()
    adapter.index(_fixture_corpus())
    results = adapter.search("addition is commutative", k=4)
    assert len(results) == 4
    # Top result should be add_comm.
    assert results[0].name == "Foo.add_comm"


def test_bm25_falls_back_to_signature_when_doc_missing() -> None:
    decls = [
        _decl("Bar.solo_lemma", "(a : Nat) : a = a", None),
        _decl("Bar.unrelated", "(b : Nat) : b + 1 > 0", None),
    ]
    adapter = BM25Adapter()
    adapter.index(decls)
    results = adapter.search("a equals a", k=2)
    assert results[0].name == "Bar.solo_lemma"


def test_bm25_search_before_index_raises() -> None:
    with pytest.raises(RuntimeError):
        BM25Adapter().search("anything")


def test_registry_lists_adapters() -> None:
    names = list_adapters()
    assert "bm25" in names
    assert "minilm" in names


def test_registry_unknown_raises() -> None:
    with pytest.raises(KeyError):
        build_adapter("nonexistent")


def test_dense_index_caches_and_uses_stub_model(tmp_path: Path) -> None:
    """Bypass the real sentence-transformer to keep tests offline-fast."""

    class _StubModel:
        def __init__(self) -> None:
            self.encode_calls = 0

        def encode(
            self,
            texts: list[str],
            batch_size: int = 64,
            show_progress_bar: bool = False,
            convert_to_numpy: bool = True,
            normalize_embeddings: bool = True,
        ) -> np.ndarray:
            del batch_size, show_progress_bar, convert_to_numpy, normalize_embeddings
            self.encode_calls += 1
            # Deterministic tiny embedding: hash text -> 4 floats, normalized.
            out = np.zeros((len(texts), 4), dtype=np.float32)
            for i, t in enumerate(texts):
                seed = abs(hash(t)) % (2**31)
                rng = np.random.default_rng(seed)
                v = rng.standard_normal(4).astype(np.float32)
                v /= float(np.linalg.norm(v) + 1e-9)
                out[i] = v
            return out

    adapter = DenseAdapter(model_name="stub/test-model", cache_dir=tmp_path)
    stub = _StubModel()
    adapter._model = stub  # inject

    decls = _fixture_corpus()
    adapter.index(decls)
    n_first = stub.encode_calls

    # Re-index: cache should hit, no re-encoding.
    adapter2 = DenseAdapter(model_name="stub/test-model", cache_dir=tmp_path)
    stub2 = _StubModel()
    adapter2._model = stub2
    adapter2.index(decls)
    assert stub2.encode_calls == 0
    assert n_first == 1  # one batch encode for the corpus

    # Search uses query-time encoding (1 call).
    results = cast(
        list[RetrievalResult], adapter2.search("addition is commutative", k=2)
    )
    assert len(results) == 2
    assert stub2.encode_calls == 1

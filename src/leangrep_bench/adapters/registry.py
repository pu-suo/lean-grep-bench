from __future__ import annotations

from collections.abc import Callable

from leangrep_bench.adapters.base import RetrievalAdapter
from leangrep_bench.adapters.bm25 import BM25Adapter
from leangrep_bench.adapters.dense import DenseAdapter
from leangrep_bench.adapters.external.leanfinder import LeanFinderAdapter
from leangrep_bench.adapters.external.leangrep import LeanGrepAdapter
from leangrep_bench.adapters.external.leansearch import LeanSearchAdapter
from leangrep_bench.adapters.external.moogle import MoogleAdapter

_BUILDERS: dict[str, Callable[[], RetrievalAdapter]] = {
    "bm25": BM25Adapter,
    "minilm": lambda: DenseAdapter(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    ),
    "bge-large": lambda: DenseAdapter(model_name="BAAI/bge-large-en-v1.5"),
    "leansearch": LeanSearchAdapter,
    "lean_finder": LeanFinderAdapter,
    "moogle": MoogleAdapter,
    "lean_grep": LeanGrepAdapter,
}


def list_adapters() -> list[str]:
    return sorted(_BUILDERS.keys())


def build_adapter(name: str) -> RetrievalAdapter:
    if name not in _BUILDERS:
        raise KeyError(
            f"unknown adapter {name!r}. Available: {list_adapters()}"
        )
    return _BUILDERS[name]()

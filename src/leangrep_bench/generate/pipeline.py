"""Run-and-cache loop for query generation.

Resume-safe (skips proof-step IDs already in the output JSONL),
threadpool-parallel, on-disk LLM cache keyed by request hash. Tracks
two leakage flags per query: cited-name leakage (the query mentions
the ground-truth declaration's name) and goal-restatement leakage
(the query copies a long verbatim substring of the goal text).

Phase 15 routed scenario classification through the v2 union corpus.
When ``data/corpus/v2/`` is present the pipeline builds a single
:class:`ScenarioIndex` from it and dispatches each step to
:func:`classify_scenario` with the step's ``(project, mathlib_sha)``
context — the same logic the eval-time visibility filter uses. The
legacy v1 binary classifier is kept as the fallback for older corpora
that pre-date Phase 13.
"""

from __future__ import annotations

import logging
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from leangrep_bench.corpus.model import read_jsonl as read_corpus
from leangrep_bench.corpus.scenarios import (
    CitedLemmaNotInCorpus,
    ScenarioIndex,
    build_scenario_index,
    classify_scenario,
)
from leangrep_bench.extract.model import ProofStep
from leangrep_bench.extract.model import read_jsonl as read_steps
from leangrep_bench.generate.model import (
    GeneratedQuery,
    Scenario,
    read_jsonl_raw,
)
from leangrep_bench.generate.prompt import (
    SYSTEM_PROMPT,
    build_user_prompt,
    cited_name_leakage_check,
    goal_leakage_check,
)
from leangrep_bench.llm import ChatRequest, LLMClient

logger = logging.getLogger(__name__)


@dataclass
class GenerationStats:
    total_steps: int = 0
    generated: int = 0
    skipped_existing: int = 0
    cache_hits: int = 0
    api_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cited_name_leakage_count: int = 0
    goal_leakage_count: int = 0
    any_leakage_count: int = 0
    by_scenario: Counter[str] = field(default_factory=lambda: Counter[str]())

    def render(self) -> str:
        return (
            f"  steps:          {self.total_steps:,}\n"
            f"  generated:      {self.generated:,}\n"
            f"  resumed:        {self.skipped_existing:,}\n"
            f"  cache hits:     {self.cache_hits:,}\n"
            f"  API calls:      {self.api_calls:,}\n"
            f"  tokens:         prompt={self.prompt_tokens:,} "
            f"completion={self.completion_tokens:,}\n"
            f"  cited leakage:  {self.cited_name_leakage_count:,}\n"
            f"  goal leakage:   {self.goal_leakage_count:,}\n"
            f"  any leakage:    {self.any_leakage_count:,}\n"
            f"  scenarios:      "
            + ", ".join(f"{k}={v}" for k, v in self.by_scenario.most_common())
        )


@dataclass
class _Classifier:
    """Pick a scenario for a proof step.

    Prefers the v2 union-corpus classifier (Phase 14). When no v2 corpus is
    available (legacy callers, tests with minimal fixtures), falls back to
    the v1 short-name-shadow heuristic so downstream code keeps working.
    """

    v2_index: ScenarioIndex | None
    legacy_shadowed: frozenset[str]

    def classify(self, step: ProofStep) -> Scenario:
        if self.v2_index is not None:
            project = step.project
            mathlib_sha = step.mathlib_sha or ""
            try:
                return classify_scenario(
                    project=project,
                    mathlib_sha=mathlib_sha,
                    cited_lemma_qualified_name=step.cited_name,
                    index=self.v2_index,
                )
            except CitedLemmaNotInCorpus:
                # Data-integrity issue (cited lemma is in neither Mathlib nor
                # project locals under this context). Fall through to the
                # legacy heuristic so the pipeline doesn't crash mid-run; the
                # downstream verify step will reject the row anyway because
                # the lookup will miss.
                logger.warning(
                    "step %s: cited %s not in v2 corpus under "
                    "project=%s mathlib_sha=%s; using legacy heuristic",
                    step.id,
                    step.cited_name,
                    project,
                    mathlib_sha,
                )
        # Legacy path (v1 binary classifier).
        if step.cited_source == "mathlib":
            return "mathlib_only"
        short = step.cited_name.split(".")[-1]
        if short in self.legacy_shadowed:
            return "mixed"
        return "local_only"


def _legacy_shadowed_short_names(corpus_dir: Path) -> frozenset[str]:
    mathlib = corpus_dir / "mathlib_declarations.jsonl"
    pfr = corpus_dir / "pfr_declarations.jsonl"
    if not mathlib.exists() or not pfr.exists():
        return frozenset()
    mathlib_short: set[str] = set()
    for d in read_corpus(mathlib):
        mathlib_short.add(d.name)
    pfr_short: set[str] = set()
    for d in read_corpus(pfr):
        pfr_short.add(d.name)
    return frozenset(mathlib_short & pfr_short)


def _build_classifier(corpus_dir: Path) -> _Classifier:
    """Prefer the v2 union corpus when available; fall back to v1 layout."""
    v2_dir = corpus_dir / "v2"
    if v2_dir.is_dir() and any(v2_dir.glob("*.jsonl")):

        def _iter_v2() -> object:
            for p in sorted(v2_dir.glob("*.jsonl")):
                yield from read_corpus(p)

        index = build_scenario_index(_iter_v2())  # type: ignore[arg-type]
        logger.info(
            "scenarios: built v2 index "
            "(mathlib contexts=%d, project locals=%d)",
            len(index.mathlib_qnames),
            len(index.local_qnames),
        )
        return _Classifier(v2_index=index, legacy_shadowed=frozenset())
    return _Classifier(
        v2_index=None,
        legacy_shadowed=_legacy_shadowed_short_names(corpus_dir),
    )


def _generate_one(
    step: ProofStep,
    *,
    classifier: _Classifier,
    client: LLMClient,
    model: str,
    seed: int,
    temperature: float,
) -> tuple[GeneratedQuery, bool, int, int]:
    scenario = classifier.classify(step)
    req = ChatRequest(
        model=model,
        system=SYSTEM_PROMPT,
        user=build_user_prompt(step),
        temperature=temperature,
        seed=seed,
    )
    resp = client.chat(req)
    query = resp.text.strip().splitlines()[0].strip() if resp.text else ""
    cited_leak = cited_name_leakage_check(query, step.cited_name)
    goal_leak = goal_leakage_check(query, step.goal_text)
    row = GeneratedQuery(
        id=f"{step.id}.q{seed}",
        proof_step_id=step.id,
        query=query,
        scenario=scenario,
        generator_model=model,
        seed=seed,
        cited_name_leakage=cited_leak,
        goal_leakage=goal_leak,
        leakage_flag=cited_leak or goal_leak,
    )
    return row, resp.cached, resp.prompt_tokens, resp.completion_tokens


def generate_queries(
    *,
    steps_path: Path,
    out_path: Path,
    cache_dir: Path,
    corpus_dir: Path,
    model: str,
    seed: int,
    temperature: float = 0.7,
    client: LLMClient | None = None,
    concurrency: int = 8,
) -> GenerationStats:
    if client is None:
        client = LLMClient(cache_dir=cache_dir)

    classifier = _build_classifier(corpus_dir)
    existing_ids: set[str] = set()
    for raw in read_jsonl_raw(out_path):
        sid = raw.get("proof_step_id")
        if isinstance(sid, str):
            existing_ids.add(sid)

    stats = GenerationStats()
    pending: list[ProofStep] = []
    for step in read_steps(steps_path):
        stats.total_steps += 1
        if step.id in existing_ids:
            stats.skipped_existing += 1
            continue
        pending.append(step)

    if not pending:
        return stats

    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_lock = threading.Lock()
    out_file = out_path.open("a", encoding="utf-8")
    try:
        if concurrency <= 1:
            for step in pending:
                row, cached, ptok, ctok = _generate_one(
                    step,
                    classifier=classifier,
                    client=client,
                    model=model,
                    seed=seed,
                    temperature=temperature,
                )
                _record(stats, row, cached, ptok, ctok)
                out_file.write(row.model_dump_json() + "\n")
                out_file.flush()
        else:
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                futures = {
                    pool.submit(
                        _generate_one,
                        step,
                        classifier=classifier,
                        client=client,
                        model=model,
                        seed=seed,
                        temperature=temperature,
                    ): step
                    for step in pending
                }
                for fut in as_completed(futures):
                    row, cached, ptok, ctok = fut.result()
                    with write_lock:
                        _record(stats, row, cached, ptok, ctok)
                        out_file.write(row.model_dump_json() + "\n")
                        out_file.flush()
                        if stats.generated % 25 == 0:
                            logger.info(
                                "generated %d/%d (api=%d cached=%d)",
                                stats.generated,
                                len(pending),
                                stats.api_calls,
                                stats.cache_hits,
                            )
    finally:
        out_file.close()
    return stats


def _record(
    stats: GenerationStats,
    row: GeneratedQuery,
    cached: bool,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    stats.generated += 1
    stats.by_scenario[row.scenario] += 1
    if row.cited_name_leakage:
        stats.cited_name_leakage_count += 1
    if row.goal_leakage:
        stats.goal_leakage_count += 1
    if row.leakage_flag:
        stats.any_leakage_count += 1
    if cached:
        stats.cache_hits += 1
    else:
        stats.api_calls += 1
        stats.prompt_tokens += prompt_tokens
        stats.completion_tokens += completion_tokens


__all__ = ["GenerationStats", "generate_queries"]

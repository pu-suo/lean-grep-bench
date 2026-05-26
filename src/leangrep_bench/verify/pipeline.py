"""Resume-safe verification pipeline.

For each generated query, look the cited declaration up in the corpus,
ask the verifier whether the query plausibly retrieves it, and write
the result to either the accepted-benchmark JSONL or the rejected
JSONL.
"""

from __future__ import annotations

import logging
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from leangrep_bench.corpus.model import read_jsonl as read_corpus
from leangrep_bench.extract.model import read_jsonl as read_steps
from leangrep_bench.generate.model import read_jsonl as read_queries
from leangrep_bench.llm import ChatRequest, LLMClient
from leangrep_bench.verify.ids import mint_item_id
from leangrep_bench.verify.model import (
    BenchmarkContext,
    BenchmarkItem,
    GenerationMeta,
    Provenance,
    RejectedItem,
    Scenario,
    read_jsonl_raw,
)
from leangrep_bench.verify.prompt import (
    SYSTEM_PROMPT,
    Verdict,
    build_user_prompt,
    parse_verdict,
)

logger = logging.getLogger(__name__)


@dataclass
class VerifyStats:
    total_queries: int = 0
    skipped_existing: int = 0
    accepted: int = 0
    rejected: int = 0
    parse_errors: int = 0
    cache_hits: int = 0
    api_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    by_scenario_total: Counter[str] = field(default_factory=lambda: Counter[str]())
    by_scenario_pass: Counter[str] = field(default_factory=lambda: Counter[str]())

    def render(self) -> str:
        rate = (
            (self.accepted / (self.accepted + self.rejected) * 100.0)
            if (self.accepted + self.rejected) > 0
            else 0.0
        )
        scenario_lines: list[str] = []
        for scen, total in self.by_scenario_total.most_common():
            passed = self.by_scenario_pass.get(scen, 0)
            sr = (passed / total * 100.0) if total else 0.0
            scenario_lines.append(f"    {scen}: {passed}/{total} ({sr:.1f}%)")
        return (
            f"  queries:     {self.total_queries:,}\n"
            f"  resumed:     {self.skipped_existing:,}\n"
            f"  accepted:    {self.accepted:,}\n"
            f"  rejected:    {self.rejected:,}\n"
            f"  parse errs:  {self.parse_errors:,}\n"
            f"  pass rate:   {rate:.2f}%\n"
            f"  by scenario:\n" + "\n".join(scenario_lines) + "\n"
            f"  cache hits:  {self.cache_hits:,}\n"
            f"  API calls:   {self.api_calls:,}\n"
            f"  tokens:      prompt={self.prompt_tokens:,} "
            f"completion={self.completion_tokens:,}"
        )


@dataclass
class _Job:
    query_id: str
    proof_step_id: str
    query: str
    scenario: str
    cited_name: str
    cited_source: str
    kind: str
    signature: str
    docstring: str | None
    enclosing_decl: str
    enclosing_signature: str | None
    goal: str | None
    hypotheses: list[str]
    prior_tactics: list[str]
    source_file: str
    line: int
    tactic_kind: str
    generator_model: str
    seed: int
    project: str
    mathlib_sha: str | None


# The pipeline body accesses ``step`` and ``q`` via attribute access only,
# so we type the records as ``dict[str, Any]`` and rely on the attribute
# set defined by ``ProofStep`` / ``GeneratedQuery`` rather than declaring
# a Protocol.


def _build_corpus_lookup(corpus_dir: Path) -> dict[str, tuple[str, str, str | None]]:
    """Map qualified_name -> (kind, signature, docstring).

    Prefers the v2 union corpus at ``corpus_dir/v2/*.jsonl``; falls back to
    the v1 two-file layout (``mathlib_declarations.jsonl`` +
    ``pfr_declarations.jsonl``) so legacy tests still pass without v2 data.
    """
    out: dict[str, tuple[str, str, str | None]] = {}
    v2_dir = corpus_dir / "v2"
    if v2_dir.is_dir() and any(v2_dir.glob("*.jsonl")):
        for p in sorted(v2_dir.glob("*.jsonl")):
            for d in read_corpus(p):
                # Last writer wins on collisions. Mathlib + project locals
                # share qualified-name space only on PFR/Mathlib staging
                # copies; either entry is acceptable for the verifier prompt.
                out[d.qualified_name] = (d.kind, d.signature, d.docstring)
        return out
    for fname in ("mathlib_declarations.jsonl", "pfr_declarations.jsonl"):
        p = corpus_dir / fname
        if not p.exists():
            continue
        for d in read_corpus(p):
            out[d.qualified_name] = (d.kind, d.signature, d.docstring)
    return out


def _verdict_for(
    job: _Job,
    *,
    client: LLMClient,
    model: str,
    seed: int,
    temperature: float,
) -> tuple[Verdict | None, bool, int, int, str]:
    """Returns (verdict, cached?, ptokens, ctokens, raw_text)."""
    user = build_user_prompt(
        query=job.query,
        qualified_name=job.cited_name,
        kind=job.kind,
        signature=job.signature,
        docstring=job.docstring,
    )
    req = ChatRequest(
        model=model,
        system=SYSTEM_PROMPT,
        user=user,
        temperature=temperature,
        seed=seed,
    )
    resp = client.chat(req)
    try:
        verdict = parse_verdict(resp.text)
    except ValueError:
        verdict = None
    return verdict, resp.cached, resp.prompt_tokens, resp.completion_tokens, resp.text


def verify_queries(
    *,
    queries_path: Path,
    steps_path: Path,
    corpus_dir: Path,
    out_path: Path,
    rejected_path: Path,
    cache_dir: Path,
    model: str,
    seed: int = 1,
    temperature: float = 0.0,
    concurrency: int = 8,
    client: LLMClient | None = None,
) -> VerifyStats:
    if client is None:
        client = LLMClient(cache_dir=cache_dir)

    # Load supporting indices.
    corpus_lookup = _build_corpus_lookup(corpus_dir)
    steps_by_id: dict[str, Any] = {s.id: s for s in read_steps(steps_path)}

    accepted_existing: set[str] = set()
    for raw in read_jsonl_raw(out_path):
        rid = raw.get("id")
        if isinstance(rid, str):
            accepted_existing.add(rid)
    rejected_existing: set[str] = set()
    for raw in read_jsonl_raw(rejected_path):
        rid = raw.get("id")
        if isinstance(rid, str):
            rejected_existing.add(rid)

    stats = VerifyStats()
    pending: list[_Job] = []

    for q in read_queries(queries_path):
        stats.total_queries += 1
        step = steps_by_id.get(q.proof_step_id)
        if step is None:
            logger.warning("query %s has no matching proof step; skipping", q.id)
            continue
        # v2: the accepted-side ID is a content hash over (project, goal,
        # hypotheses, prior_tactics, cited_lemma). Compute it up-front so we
        # can short-circuit if this row already landed on the accepted JSONL.
        would_be_accepted_id = mint_item_id(
            project=step.project,
            goal=step.goal_text,
            hypotheses=step.hypotheses,
            prior_tactics=step.prior_tactics,
            cited_lemma_qualified_name=step.cited_name,
        )
        if (
            would_be_accepted_id in accepted_existing
            or q.id in rejected_existing
        ):
            stats.skipped_existing += 1
            continue
        info = corpus_lookup.get(step.cited_name)
        if info is None:
            logger.warning(
                "query %s cites %s which is not in the corpus; skipping",
                q.id,
                step.cited_name,
            )
            continue
        kind, signature, docstring = info
        pending.append(
            _Job(
                query_id=q.id,
                proof_step_id=q.proof_step_id,
                query=q.query,
                scenario=q.scenario,
                cited_name=step.cited_name,
                cited_source=step.cited_source,
                kind=kind,
                signature=signature,
                docstring=docstring,
                enclosing_decl=step.enclosing_decl,
                enclosing_signature=step.enclosing_signature,
                goal=step.goal_text,
                hypotheses=step.hypotheses,
                prior_tactics=step.prior_tactics,
                source_file=step.source_file,
                line=step.line,
                tactic_kind=step.tactic_kind,
                generator_model=q.generator_model,
                seed=q.seed,
                project=step.project,
                mathlib_sha=step.mathlib_sha,
            )
        )

    if not pending:
        return stats

    out_path.parent.mkdir(parents=True, exist_ok=True)
    rejected_path.parent.mkdir(parents=True, exist_ok=True)
    out_file = out_path.open("a", encoding="utf-8")
    rej_file = rejected_path.open("a", encoding="utf-8")
    write_lock = threading.Lock()

    def _process(job: _Job) -> tuple[_Job, Verdict | None, bool, int, int]:
        verdict, cached, ptok, ctok, _raw = _verdict_for(
            job,
            client=client,
            model=model,
            seed=seed,
            temperature=temperature,
        )
        return job, verdict, cached, ptok, ctok

    try:
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            futures = [pool.submit(_process, j) for j in pending]
            for fut in as_completed(futures):
                job, verdict, cached, ptok, ctok = fut.result()
                with write_lock:
                    stats.by_scenario_total[job.scenario] += 1
                    if cached:
                        stats.cache_hits += 1
                    else:
                        stats.api_calls += 1
                        stats.prompt_tokens += ptok
                        stats.completion_tokens += ctok
                    # v2: mint the accepted-item ID from the proof-step content
                    # tuple so the same step always lands on the same ID
                    # across regenerations and across projects. Rejections keep
                    # the query ID because they're keyed by attempt, not by
                    # an accepted artifact.
                    accepted_id = mint_item_id(
                        project=job.project,
                        goal=job.goal,
                        hypotheses=job.hypotheses,
                        prior_tactics=job.prior_tactics,
                        cited_lemma_qualified_name=job.cited_name,
                    )
                    if verdict is None:
                        stats.parse_errors += 1
                        # Treat unparseable as a rejection with explicit reason.
                        rej = RejectedItem(
                            id=job.query_id,
                            proof_step_id=job.proof_step_id,
                            query=job.query,
                            ground_truth_name=job.cited_name,
                            ground_truth_source=job.cited_source,
                            scenario=_normalize_scenario(job.scenario),
                            verifier_model=model,
                            reason="(verifier output unparseable)",
                        )
                        rej_file.write(rej.model_dump_json() + "\n")
                        rej_file.flush()
                        stats.rejected += 1
                        continue
                    if verdict.is_yes:
                        item = BenchmarkItem(
                            id=accepted_id,
                            scenario=_normalize_scenario(job.scenario),
                            query=job.query,
                            ground_truth_name=job.cited_name,
                            ground_truth_source=job.cited_source,
                            context=BenchmarkContext(
                                enclosing_decl=job.enclosing_decl,
                                enclosing_signature=job.enclosing_signature,
                                goal=job.goal,
                                hypotheses=job.hypotheses,
                                prior_tactics=job.prior_tactics,
                            ),
                            provenance=Provenance(
                                source_file=job.source_file,
                                line=job.line,
                                tactic_kind=job.tactic_kind,
                            ),
                            generation=GenerationMeta(
                                generator_model=job.generator_model,
                                verifier_model=model,
                                seed=job.seed,
                            ),
                            project=job.project,
                            mathlib_sha=job.mathlib_sha,
                        )
                        out_file.write(item.model_dump_json() + "\n")
                        out_file.flush()
                        stats.accepted += 1
                        stats.by_scenario_pass[job.scenario] += 1
                    else:
                        rej = RejectedItem(
                            id=job.query_id,
                            proof_step_id=job.proof_step_id,
                            query=job.query,
                            ground_truth_name=job.cited_name,
                            ground_truth_source=job.cited_source,
                            scenario=_normalize_scenario(job.scenario),
                            verifier_model=model,
                            reason=verdict.reason,
                        )
                        rej_file.write(rej.model_dump_json() + "\n")
                        rej_file.flush()
                        stats.rejected += 1
                    if (stats.accepted + stats.rejected) % 50 == 0:
                        logger.info(
                            "verified %d/%d (accept=%d reject=%d)",
                            stats.accepted + stats.rejected,
                            len(pending),
                            stats.accepted,
                            stats.rejected,
                        )
    finally:
        out_file.close()
        rej_file.close()
    return stats


def _normalize_scenario(s: str) -> Scenario:
    if s == "local_only" or s == "mathlib_only" or s == "mixed":
        return s
    raise ValueError(f"unexpected scenario: {s!r}")

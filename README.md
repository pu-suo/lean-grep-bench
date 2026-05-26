# lean-grep-bench

A retrieval benchmark for Lean 4 lemma search. Each item is a real proof
step from a Lean project: an elaborator-captured goal, the local
hypotheses in scope, the prior tactics in the proof block, and the lemma
the step actually applied. Retrieval systems are scored on whether they
surface that lemma when given a natural-language description of the
proof situation.

The pipeline traces each project with
[LeanDojo-v2](https://github.com/lean-dojo/LeanDojo-v2), filters the
trace for single-citation tactics (`apply` / `exact` / `use` / `refine`),
and runs each step through an LLM generator + LLM verifier to produce a
paired `(query, ground_truth_lemma)` row. Adding a new project is
plumbing — same commands, same schema, different `--project` flag.

## Headline numbers

- **Benchmark size:** **2,520 verified items** (PFR 637, PNT 1,883)
- **Scenario breakdown:** mathlib_only=1,815, local_only=685, mixed=22
- **Corpus indexed:** Mathlib at two snapshots (PFR's `35638f90…`,
  PNT's `8f9d9cff…`) + PFR locals (1,077) + PNT locals (2,129)
- **Retrieval baselines** (Recall@10 over the unified 2,520-item set):
  BM25 4.2% / Dense (MiniLM-L6) 19.6% overall

Per-project verifier pass rates: PFR 67.8% (637 of 940), PNT 68.8%
(1,885 of 2,740). Full eval at
[results/run-001/results.md](results/run-001/results.md); per-project
verifier audits at
[data/pfr/benchmark_audit.md](data/pfr/benchmark_audit.md) and
[data/pnt/benchmark_audit.md](data/pnt/benchmark_audit.md).

## Repo layout

```
src/leangrep_bench/
  corpus/          parse Mathlib + project source into corpus JSONL
                   (handles `@[to_additive]` macro twins; recovers
                   bare premise names from LeanDojo-v2 traces)
  dojo/            consume LeanDojo trace JSONL
  extract/         trace -> (tactic, cited declaration) ProofStep records
  generate/        LLM query generator (gpt-5-mini)
  verify/          LLM verifier of (query, declaration) pairs (gpt-5)
  adapters/        retrieval baselines: BM25, dense (sentence-tx),
                   plus external services: leansearch, leanfinder, ...
  eval/            run adapters against the benchmark, compute R@k
  benchmark_export.py     flatten benchmark.jsonl into CSV

scripts/
  convert_benchmark.py   benchmark.jsonl -> HTML viewer (CSV path lives
                         in `leangrep_bench.benchmark_export`)
  mathlib_jaccard.py     similarity of two Mathlib snapshots
  remote/                EC2-side scripts that run LeanDojo-v2 against
                         a project (see specs/phase_15_remote_runbook.md)

data/
  benchmark.jsonl        UNIFIED benchmark across all projects
  benchmark.csv          flat human-viewable export (truncated cells)

  pfr/                   PFR-specific artifacts
    proof_steps.jsonl    one row per traced tactic invocation
    queries.jsonl        one LLM-generated query per proof step
    benchmark.jsonl      verified items (PFR-only slice)
    benchmark_rejected.jsonl    verifier-rejected items + reasons
    queries_audit.md     generation summary + spot-checks
    benchmark_audit.md   verification summary + acc/rej samples
  pnt/                   PNT-specific artifacts (same shape)
  <project>/             same shape for every additional project

  corpus/
    union/                       union corpus, per-decl visible_in tags
      mathlib__<sha>.jsonl       one per pinned Mathlib SHA (gitignored)
      <project>__local.jsonl     one per project (tracked)
    mathlib__<sha>.jsonl         per-SHA Mathlib export (gitignored)
    <project>_declarations.jsonl per-project local export (tracked)
    build_manifest.json          schema-checked list of projects, SHAs,
                                 decl counts

  dojo_trace_<project>/  LeanDojo trace JSONLs (multi-GB; gitignored;
                         capture on EC2 per the phase 15 runbook)

results/run-001/         eval results (BM25 by default; re-run with
                         `leangrep-bench eval`)
```

## How an item is built

```
<project> source  -->  [LeanDojo-v2 trace]  -->  TacticTrace JSONL
                                                  (data/dojo_trace_<project>/)
                                                          |
                                  +-----------------------+
                                  v
   `apply Real.log_nonneg`        ProofStep record:
   in PrimeNumberTheoremAnd/        project:      "pnt"
   Wiener.lean                      mathlib_sha:  "8f9d9cff…"
                                    goal_text:    "⊢ 0 ≤ Real.log (x + 1)"
                                    hypotheses:   ["x : ℝ", "hx : 0 ≤ x"]
                                    prior_tactics:["intro hx", "..."]
                                    cited_name:   "Real.log_nonneg"
                                    cited_source: "mathlib"
                                                          |
                                          +---------------+----------------+
                                          v                                v
                                gpt-5-mini generator              (corpus lookup
                                          |                          via union/)
                                          v
                                   GeneratedQuery + cited declaration
                                                          |
                                                          v
                                                  gpt-5 verifier
                                                          |
                                          +---------------+----------------+
                                          v                                v
                                  BenchmarkItem (accepted)         RejectedItem
                                  -> data/<project>/benchmark.jsonl
```

The trace step needs to run on Linux (LeanDojo-v2 wraps a real Lean
elaborator), so it lives in `scripts/remote/` for an operator to run on
a rented EC2 box. Every other step runs locally on macOS or Linux.

## Why use a real elaborator (LeanDojo) instead of regex?

The same source text means different things to a regex parser and to
Lean. Four examples that show up in real proofs:

1. **Name resolution.** `apply trans` could be `Eq.trans`, `LE.le.trans`,
   `IdentDistrib.trans`, ... Regex captures the literal token and
   guesses; LeanDojo reads the elaborator's resolved name directly.
   (LeanDojo-v2 dropped the full elaboration step; the
   [`CorpusIndex.resolve`](src/leangrep_bench/extract/index.py)
   bare-name fallback reconstructs the qualified form on our side.)
2. **Goal state.** The proposition the lemma is supposed to prove
   exists nowhere in the source — it's a derived state of the proof
   so far. A regex parser literally cannot see it.
3. **Live hypotheses.** A regex sees the theorem's binder list. The
   elaborator knows what's in scope at line 80 of a long proof,
   including `let` bindings and instances introduced by tactics.
4. **Macro-generated declarations.** Mathlib's `@[to_additive]` macro
   takes one source-level theorem (`Finset.prod_congr`) and creates
   a second theorem at compile time (`Finset.sum_congr`). The
   additive twin doesn't exist in source. The corpus parser in this
   repo re-implements the macro's name-mangling rules to compensate
   when reading source-only; LeanDojo just sees both names natively.

## Reproduce from a checkout

### Prerequisites
- Python 3.11+, a venv.
- `OPENAI_API_KEY` if you want to regenerate queries or benchmark.
- Local Mathlib4 checkout(s) at the commit(s) in
  [data/corpus/build_manifest.json](data/corpus/build_manifest.json) —
  each project pins its own Mathlib SHA. (Same Mathlib4 working tree
  can be re-checked out between rebuilds.)
- Local project checkout(s) at the SHAs in the same manifest.
- A LeanDojo-v2 trace per project (gitignored at
  `data/dojo_trace_<project>/`; see
  [specs/phase_15_remote_runbook.md](specs/phase_15_remote_runbook.md)
  for the EC2-side procedure).

### Install

```sh
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Per-project pipeline

The same five commands work for every project; just vary `--project`.

```sh
PROJECT=pnt

# (one-off, per Mathlib SHA) Build the Mathlib corpus snapshot.
leangrep-bench corpus build-mathlib \
    --mathlib-path /path/to/mathlib4 \
    --out data/corpus/mathlib__<sha>.jsonl

# (one-off, per project) Build the project's local declarations.
leangrep-bench corpus build-project \
    --project $PROJECT \
    --repo-path /path/to/$PROJECT \
    --sub-dir <SourceTopDir>

# (after manifest updated) Build the union corpus with visibility tags.
leangrep-bench corpus build-union

# 1. Trace the project with LeanDojo-v2 on EC2. See the phase-15 runbook.
#    Result lands in data/dojo_trace_$PROJECT/*.jsonl.
leangrep-bench dojo validate --trace data/dojo_trace_$PROJECT/

# 2. Convert traces into proof-step records.
leangrep-bench extract proof-steps --project $PROJECT

# 3. Generate one query per proof step (~$0.30 per 1k steps on gpt-5-mini;
#    resume-safe via on-disk cache).
leangrep-bench generate queries --project $PROJECT

# 4. Verify each (query, ground-truth) pair (~$0.30 per 1k items on gpt-5).
leangrep-bench verify queries --project $PROJECT

# 5. Merge the new project's benchmark into the unified file + CSV.
leangrep-bench benchmark merge \
    -i data/pfr/benchmark.jsonl \
    -i data/$PROJECT/benchmark.jsonl \
    --out data/benchmark.jsonl
leangrep-bench benchmark export-csv

# 6. Run retrieval baselines and compute Recall@k.
leangrep-bench eval -a bm25 -a minilm --out-dir results/run-001/
```

## Benchmark schema

Each row of [`data/benchmark.jsonl`](data/benchmark.jsonl) is:

```python
{
  "id":                   "lgb_<project>_<16-hex>",      # content-hash
  "project":              "pfr" | "pnt" | ...,
  "mathlib_sha":          "8f9d9cff…",                   # for visibility filter
  "scenario":             "mathlib_only" | "local_only" | "mixed",
  "query":                "<one-line natural-language search query>",
  "ground_truth_name":    "<qualified Lean name>",
  "ground_truth_source":  "mathlib" | "local:<project>",
  "context": {
    "enclosing_decl":     "<surrounding theorem name>",
    "enclosing_signature":"<binders + return type, may be null>",
    "goal":               "<⊢ ... proposition the lemma must prove>",
    "hypotheses":         ["name : type", ...],          # elaborated, in scope
    "prior_tactics":      ["<tactic line>", ...],        # up to 5
  },
  "provenance": {
    "source_file":        "PrimeNumberTheoremAnd/Foo.lean",
    "line":               42,
    "tactic_kind":        "apply" | "exact" | "use" | "refine",
  },
  "generation": {
    "generator_model":    "gpt-5-mini",
    "verifier_model":     "gpt-5",
    "seed":               1,
  },
}
```

`id` is a content hash over `(project, goal, hypotheses, prior_tactics,
cited_lemma_qualified_name)`, so the same logical proof-step always lands
on the same ID across regenerations and merges.

The CSV at [`data/benchmark.csv`](data/benchmark.csv) is a flat,
truncated-cell projection of the same data; regenerate with
`leangrep-bench benchmark export-csv`. An HTML viewer is also available
via `python scripts/convert_benchmark.py --in data/benchmark.jsonl
--out data/benchmark.html --format html`.

## Scenarios

The scenario label is computed per-item against the project's pinned
Mathlib snapshot, so the same lemma can flip classification across
projects whose Mathlib pins differ.

- **`local_only`** — the cited lemma lives in the item's project, and
  its short name doesn't shadow anything in the project's Mathlib
  snapshot. Tests whether a system has indexed local declarations.
- **`mathlib_only`** — the cited lemma resolves uniquely to Mathlib.
  The harder slice: the corpus has 245K+ similar-shaped lemmas to
  disambiguate among.
- **`mixed`** — the cited lemma is project-local AND its short name
  collides with at least one Mathlib lemma in the project's snapshot.
  Catches shadowing-resolution mistakes.

## Visibility filter

A retriever must surface lemmas that are *visible* under the item's
`(project, mathlib_sha)` context. An item from PFR (Mathlib pinned at
`35638f90…`) shouldn't credit retrievers for surfacing a PNT-local
lemma — PNT lemmas don't exist in PFR's world. The eval runner enforces
this with the `visible_in` tags written by `corpus build-union`: each
adapter is asked for `k × 5` candidates, then filtered to those visible
under the item's context, then truncated to `k`.

## Evaluating your own retrieval system

Implement [`adapters.base.RetrievalAdapter`](src/leangrep_bench/adapters/base.py)
and register it in [`adapters/registry.py`](src/leangrep_bench/adapters/registry.py),
then pass `-a your_adapter` to `leangrep-bench eval`. See
[`adapters/bm25.py`](src/leangrep_bench/adapters/bm25.py) for the
minimum interface (`index(corpus_entries)` then `search(query, k)`).

External-service adapters (HTTP) live in `adapters/external/` and
follow the same contract.

## License

MIT. See `pyproject.toml`.

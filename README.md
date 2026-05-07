# lean-grep-bench

A retrieval benchmark for Lean 4 lemma search. Each item is a real
proof step from the [PFR](https://github.com/teorth/pfr) project: an
elaborator-captured goal, the local hypotheses in scope, the prior
tactics in the proof block, and the lemma the step actually applied.
Retrieval systems are scored on whether they surface that lemma when
given a natural-language description of the proof situation.

The pipeline traces PFR with [LeanDojo](https://leandojo.org/), filters
the trace for single-citation tactics (`apply` / `exact` / `use` /
`refine`), and runs each step through an LLM generator + LLM verifier
to produce a paired `(query, ground_truth_lemma)` row.

## Headline numbers

- **Benchmark size:** 637 verified items (pass rate 67.8%, from 940
  generated queries against 2,000 raw tactic invocations across 64
  PFR files)
- **Scenario breakdown:** local_only=283, mathlib_only=339, mixed=15
- **Corpus indexed:** 250,674 Mathlib4 declarations + 1,077 PFR
  declarations
- **Retrieval baselines** (Recall@10): BM25 8.3% / Dense (MiniLM-L6)
  29.7% overall; on the `local_only` slice 14.1% / 44.2%

Full eval at [results/run-001/results.md](results/run-001/results.md);
verifier audit at [data/benchmark_audit.md](data/benchmark_audit.md).

## Repo layout

```
src/leangrep_bench/
  corpus/          parse Mathlib + PFR source into corpus JSONL
                   (handles `@[to_additive]` macro twins)
  dojo/            consume LeanDojo trace JSONL
  extract/         trace -> (tactic, cited declaration) ProofStep records
  generate/        LLM query generator (gpt-5-mini)
  verify/          LLM verifier of (query, declaration) pairs (gpt-5)
  adapters/        retrieval baselines: BM25, dense (sentence-tx),
                   plus external services: leansearch, leanfinder, ...
  eval/            run adapters against the benchmark, compute R@k

scripts/
  convert_benchmark.py   benchmark.jsonl  ->  benchmark.csv / .html
  remote/                EC2-side scripts that run LeanDojo against PFR
                         (see scripts/remote/RUNBOOK.md)

data/
  corpus/                Mathlib + PFR declaration index (Mathlib JSONL
                         is gitignored; PFR JSONL is small and tracked)
  proof_steps.jsonl      937 trace -> proof-step records
  queries.jsonl          one generated query per proof step
  benchmark.jsonl        accepted (verified) items: this is the
                         shippable benchmark
  benchmark.csv          flat human-viewable export (truncated cells)
  benchmark_rejected.jsonl   verifier-rejected items + reasons
  queries_audit.md       generation summary + 15 spot-checks
  benchmark_audit.md     verification summary + 10 acc + 10 rej

results/run-001/         eval results against benchmark.jsonl
```

## How an item is built

```
PFR source  -->  [LeanDojo trace]  -->  TacticTrace JSONL
                                          (in data/dojo_trace/)
                                                |
                          +-----------------------+
                          v
   `apply foo`            ProofStep record:
   in PFR/Foo.lean   -->    goal_text:    "⊢ a + b = b + a"
                            hypotheses:   ["a b : Nat"]
                            prior_tactics:["intro a", "intro b"]
                            cited_name:   "Nat.add_comm" (mathlib)
                            ...
                                |
                          +-----+-----+
                          v           v
                gpt-5-mini       (corpus lookup)
                generator           |
                          |         |
                          v         v
                   GeneratedQuery + cited declaration  -->  gpt-5 verifier
                                                             |
                                                             v
                                                BenchmarkItem (accepted)
                                                or RejectedItem (rejected)
```

The trace step needs to run on Linux (LeanDojo wraps a real Lean
elaborator), so it lives in `scripts/remote/` for an operator to run
on a rented EC2 box. The other steps run locally on macOS or Linux.

## Why use a real elaborator (LeanDojo) instead of regex?

The same source text means different things to a regex parser and to
Lean. Four examples that show up in real PFR proofs:

1. **Name resolution.** `apply trans` could be `Eq.trans`, `LE.le.trans`,
   `IdentDistrib.trans`, ... Regex captures the literal token and
   guesses; LeanDojo reads the elaborator's resolved name directly.
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
- `OPENAI_API_KEY` if you want to regenerate `queries.jsonl` or
  `benchmark.jsonl`.
- Local Mathlib4 + PFR checkouts at the commits in
  [data/corpus/build_manifest.json](data/corpus/build_manifest.json).
- A LeanDojo trace of PFR (gitignored at `data/dojo_trace/`; see
  [scripts/remote/RUNBOOK.md](scripts/remote/RUNBOOK.md) for the
  EC2-side procedure).

### Install

```sh
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### End-to-end pipeline

```sh
# (one-off) Build the declaration corpus from local checkouts.
leangrep-bench corpus build-mathlib --mathlib-path /path/to/mathlib4 \
    --out data/corpus/mathlib_declarations.jsonl
leangrep-bench corpus build-pfr --pfr-path /path/to/pfr \
    --out data/corpus/pfr_declarations.jsonl

# 1. Trace PFR with LeanDojo, on Linux. See scripts/remote/RUNBOOK.md.
#    Result lands in data/dojo_trace/*.jsonl.
leangrep-bench dojo validate --trace data/dojo_trace/

# 2. Convert traces into proof-step records.
leangrep-bench extract proof-steps \
    --trace-dir data/dojo_trace/ \
    --corpus-dir data/corpus/ \
    --out data/proof_steps.jsonl

# 3. Generate one query per proof step (~$0.30 on gpt-5-mini for ~940
#    items; resume-safe via on-disk cache).
leangrep-bench generate queries \
    --steps data/proof_steps.jsonl \
    --out data/queries.jsonl

# 4. Verify each (query, ground-truth) pair (~$1 on gpt-5).
leangrep-bench verify queries \
    --queries data/queries.jsonl \
    --steps data/proof_steps.jsonl \
    --out data/benchmark.jsonl \
    --rejected data/benchmark_rejected.jsonl

# 5. Run retrieval baselines and compute Recall@k.
leangrep-bench eval \
    --benchmark data/benchmark.jsonl \
    --corpus-dir data/corpus/ \
    -a bm25 -a minilm \
    --out-dir results/run-001/
```

## Benchmark schema

Each row of [`data/benchmark.jsonl`](data/benchmark.jsonl) is:

```python
{
  "id": "pfr_step_..."                    # unique within a run
  "scenario": "mathlib_only" | "local_only" | "mixed",
  "query": "<one-line natural-language search query>",
  "ground_truth_name": "<qualified Lean name>",
  "ground_truth_source": "mathlib" | "pfr",
  "context": {
    "enclosing_decl": "<surrounding theorem name>",
    "enclosing_signature": "<binders + return type, may be null>",
    "goal": "<⊢ ... proposition the lemma must prove>",
    "hypotheses": ["name : type", ...],   # elaborated, in scope
    "prior_tactics": ["<tactic line>", ...],   # up to 5
  },
  "provenance": {
    "source_file": "PFR/Foo.lean",
    "line": 42,
    "tactic_kind": "apply" | "exact" | "use" | "refine",
  },
  "generation": {
    "generator_model": "gpt-5-mini",
    "verifier_model": "gpt-5",
    "seed": 1,
  },
}
```

For a CSV-flattened version see
[`data/benchmark.csv`](data/benchmark.csv); regenerate with
`python scripts/convert_benchmark.py --in data/benchmark.jsonl --out
data/benchmark.csv --format csv`. An HTML viewer is available too
(`--format html`).

## Scenarios

- **`local_only`** — the cited lemma lives in PFR, and its short name
  doesn't shadow anything in Mathlib. Tests whether a system has
  indexed local declarations at all.
- **`mathlib_only`** — the cited lemma lives in Mathlib. The harder
  slice: the corpus has 250K+ similar-shaped lemmas to disambiguate
  among.
- **`mixed`** — short name appears in both PFR and Mathlib. Catches
  shadowing-resolution mistakes. Small N; treat as smoke-test.

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

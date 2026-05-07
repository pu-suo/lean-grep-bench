# Eval results

- Items: 637
- Adapters: bm25, dense:all-MiniLM-L6-v2

## Overall (N=637)

| System | R@1 | R@5 | R@10 | MRR |
|---|---|---|---|---|
| bm25 | 0.014 | 0.050 | 0.083 | 0.032 |
| dense:all-MiniLM-L6-v2 | 0.083 | 0.242 | 0.297 | 0.152 |

## local_only (N=283)

| System | R@1 | R@5 | R@10 | MRR |
|---|---|---|---|---|
| bm25 | 0.025 | 0.085 | 0.141 | 0.053 |
| dense:all-MiniLM-L6-v2 | 0.152 | 0.403 | 0.442 | 0.257 |

## mathlib_only (N=339)

| System | R@1 | R@5 | R@10 | MRR |
|---|---|---|---|---|
| bm25 | 0.006 | 0.021 | 0.027 | 0.013 |
| dense:all-MiniLM-L6-v2 | 0.029 | 0.106 | 0.159 | 0.064 |

## mixed (N=15)

| System | R@1 | R@5 | R@10 | MRR |
|---|---|---|---|---|
| bm25 | 0.000 | 0.067 | 0.267 | 0.059 |
| dense:all-MiniLM-L6-v2 | 0.000 | 0.267 | 0.667 | 0.155 |

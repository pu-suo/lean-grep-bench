from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass
class SliceMetrics:
    n: int
    recall_at: dict[int, float]
    mrr: float


def compute_metrics(
    rows: Iterable[tuple[str, list[str]]],
    *,
    ks: tuple[int, ...] = (1, 5, 10),
) -> SliceMetrics:
    """Compute Recall@k for each k in `ks` and MRR over the iterable.

    Each row is (ground_truth_name, predicted_names ranked best-first).
    """
    n = 0
    hits: dict[int, int] = dict.fromkeys(ks, 0)
    rr_sum = 0.0
    for gt, predicted in rows:
        n += 1
        rank = next((i for i, p in enumerate(predicted, 1) if p == gt), None)
        if rank is not None:
            for k in ks:
                if rank <= k:
                    hits[k] += 1
            rr_sum += 1.0 / rank
    recall = {k: (hits[k] / n) if n else 0.0 for k in ks}
    mrr = rr_sum / n if n else 0.0
    return SliceMetrics(n=n, recall_at=recall, mrr=mrr)

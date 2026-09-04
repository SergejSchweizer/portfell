"""Parallel preparation of independent Walk-Forward candidate refits."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from concurrent.futures import Executor
from typing import Any

from portfell.income import IncomeEvidence
from portfell.multivariate_candidates import (
    CandidateRefitTask,
    PortfolioCandidate,
    build_refit_candidate_set,
)
from portfell.multivariate_inputs import MultivariateInputSnapshot, MultivariateListingKey
from portfell.multivariate_validation import (
    DEFAULT_WALK_FORWARD_POLICY,
    WalkForwardPolicy,
    _common_dates,
    _walk_forward_starts,
)


def build_refitted_candidate_sets(
    *,
    executor: Executor,
    candidates: Sequence[PortfolioCandidate],
    snapshot: MultivariateInputSnapshot,
    return_rows: Sequence[Mapping[str, Any]],
    income: Mapping[MultivariateListingKey, IncomeEvidence],
    policy: WalkForwardPolicy = DEFAULT_WALK_FORWARD_POLICY,
) -> tuple[tuple[PortfolioCandidate, ...], ...]:
    # Each refit used to be submitted as a separate process task containing a
    # large, overlapping training-row slice.  With 24 refits that repeatedly
    # pickled the same history and dominated the actual solvers.  Batch the
    # refits by available CPU worker and send the full immutable history only
    # once per batch; each worker derives its own date slices locally.
    dates = _common_dates(candidates, return_rows)
    starts = _walk_forward_starts(dates, policy)
    if not starts:
        return ()
    worker_count = max(1, os.process_cpu_count() or 1)
    batch_count = min(worker_count, len(starts))
    batches = tuple(
        tuple(starts[index] for index in range(batch_index, len(starts), batch_count))
        for batch_index in range(batch_count)
    )
    tasks = tuple(
        (snapshot, tuple(return_rows), income, tuple(dates), batch, policy)
        for batch in batches
    )
    groups = executor.map(_build_refit_batch, tasks)
    return tuple(item for group in groups for item in group)


def _build_refit_batch(
    task: tuple[
        MultivariateInputSnapshot,
        tuple[Mapping[str, Any], ...],
        Mapping[MultivariateListingKey, IncomeEvidence],
        tuple[str, ...],
        tuple[int, ...],
        WalkForwardPolicy,
    ]
) -> tuple[tuple[PortfolioCandidate, ...], ...]:
    snapshot, return_rows, income, dates, starts, _policy = task
    results: list[tuple[PortfolioCandidate, ...]] = []
    for start in starts:
        training_dates = set(dates[:start])
        training_rows = tuple(
            row for row in return_rows if str(row.get("date", "")) in training_dates
        )
        results.append(build_refit_candidate_set(CandidateRefitTask(snapshot, training_rows, income)))
    return tuple(results)

"""Parallel preparation of independent Walk-Forward candidate refits."""

from __future__ import annotations

import os
import pickle
import tempfile
from collections.abc import Mapping, Sequence
from concurrent.futures import Executor
from contextlib import suppress
from typing import Any

from portfell.income import IncomeEvidence
from portfell.multivariate_candidates import (
    CandidateRefitTask,
    PortfolioCandidate,
    build_refit_candidate_set,
)
from portfell.multivariate_inputs import MultivariateInputSnapshot, MultivariateListingKey
from portfell.multivariate_risk_spec import RiskModelSpecification
from portfell.multivariate_validation import (
    DEFAULT_WALK_FORWARD_POLICY,
    WalkForwardPolicy,
    _common_dates,  # pyright: ignore[reportPrivateUsage]
    _walk_forward_starts,  # pyright: ignore[reportPrivateUsage]
)


def build_refitted_candidate_sets(
    *,
    executor: Executor,
    candidates: Sequence[PortfolioCandidate],
    snapshot: MultivariateInputSnapshot,
    return_rows: Sequence[Mapping[str, Any]],
    income: Mapping[MultivariateListingKey, IncomeEvidence],
    policy: WalkForwardPolicy = DEFAULT_WALK_FORWARD_POLICY,
    risk_model_spec: RiskModelSpecification | None = None,
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
    # Keep the large immutable history out of ProcessPool's pickle payload.
    # The temporary file lives on the API container's local tmpfs and is
    # removed only after every worker has consumed it.
    return_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            prefix="portfell-mv-", suffix=".pkl", delete=False
        ) as handle:
            pickle.dump(tuple(return_rows), handle, protocol=pickle.HIGHEST_PROTOCOL)
            return_path = handle.name
        tasks = tuple(
            (snapshot, return_path, income, tuple(dates), batch, policy, risk_model_spec)
            for batch in batches
        )
        groups = tuple(executor.map(_build_refit_batch, tasks))
        # Worker batches are intentionally round-robin for load balancing;
        # validation, however, is path-dependent and must consume refits in
        # the canonical chronological start order.
        return _ordered_refit_candidate_sets(groups)
    finally:
        if return_path:
            with suppress(FileNotFoundError):
                os.unlink(return_path)


def _build_refit_batch(
    task: tuple[
        MultivariateInputSnapshot,
        str,
        Mapping[MultivariateListingKey, IncomeEvidence],
        tuple[str, ...],
        tuple[int, ...],
        WalkForwardPolicy,
        RiskModelSpecification | None,
    ],
) -> tuple[tuple[int, tuple[PortfolioCandidate, ...]], ...]:
    snapshot, return_path, income, dates, starts, _policy, risk_model_spec = task
    with open(return_path, "rb") as handle:
        return_rows = tuple(pickle.load(handle))
    results: list[tuple[int, tuple[PortfolioCandidate, ...]]] = []
    for start in starts:
        training_dates = set(dates[:start])
        training_rows = tuple(
            row for row in return_rows if str(row.get("date", "")) in training_dates
        )
        results.append(
            (
                start,
                build_refit_candidate_set(
                    CandidateRefitTask(
                        snapshot, training_rows, income, risk_model_spec=risk_model_spec
                    )
                ),
            )
        )
    return tuple(results)


def _ordered_refit_candidate_sets(
    groups: Sequence[Sequence[tuple[int, tuple[PortfolioCandidate, ...]]]],
) -> tuple[tuple[PortfolioCandidate, ...], ...]:
    """Flatten worker batches by canonical walk-forward start index."""
    ordered = sorted((item for group in groups for item in group), key=lambda item: item[0])
    return tuple(candidate_set for _start, candidate_set in ordered)

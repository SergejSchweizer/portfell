"""Parallel preparation of independent Walk-Forward candidate refits."""

from __future__ import annotations

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
    walk_forward_training_rows,
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
    training_rows = walk_forward_training_rows(
        candidates=candidates, return_rows=return_rows, policy=policy
    )
    tasks = tuple(CandidateRefitTask(snapshot, rows, income) for rows in training_rows)
    return tuple(executor.map(build_refit_candidate_set, tasks))

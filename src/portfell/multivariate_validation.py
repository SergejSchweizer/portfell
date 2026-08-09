"""Walk-forward and deterministic stress validation for candidate portfolios."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import sqrt
from typing import Any

from portfell.contract_versioning import ContractVersion, stable_contract_id
from portfell.multivariate_candidates import PortfolioCandidate

VALIDATION_CONTRACT = ContractVersion("multivariate.validation", 1)


@dataclass(frozen=True)
class WalkForwardPolicy:
    version: ContractVersion = VALIDATION_CONTRACT
    minimum_training_observations: int = 504
    test_window_observations: int = 21
    minimum_completed_splits: int = 2
    transaction_cost_rate: float = 0.0005

    def to_row(self) -> dict[str, object]:
        return {
            "version": self.version.qualified_name,
            "minimum_training_observations": self.minimum_training_observations,
            "test_window_observations": self.test_window_observations,
            "minimum_completed_splits": self.minimum_completed_splits,
            "transaction_cost_rate": self.transaction_cost_rate,
        }


DEFAULT_WALK_FORWARD_POLICY = WalkForwardPolicy()


@dataclass(frozen=True)
class ValidationSplit:
    split_id: str
    method: str
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    pre_cost_return: float
    transaction_cost: float
    post_cost_return: float
    volatility: float | None
    status: str
    reason: str | None


def validate_candidates(
    *,
    candidates: Sequence[PortfolioCandidate],
    return_rows: Sequence[Mapping[str, Any]],
    policy: WalkForwardPolicy = DEFAULT_WALK_FORWARD_POLICY,
) -> tuple[ValidationSplit, ...]:
    """Validate each feasible candidate on identical out-of-sample slices."""
    by_date = _portfolio_returns_by_date(candidates, return_rows)
    series: list[set[str]] = [set(values) for values in by_date.values() if values]
    common_dates: set[str] = set(series[0]) if series else set()
    for values in series[1:]:
        common_dates &= values
    dates: tuple[str, ...] = tuple(sorted(common_dates))
    if len(dates) < policy.minimum_training_observations + policy.test_window_observations:
        return tuple(
            _unavailable(candidate, "insufficient_walk_forward_history") for candidate in candidates
        )
    results: list[ValidationSplit] = []
    for candidate in candidates:
        if candidate.status != "feasible":
            results.append(_unavailable(candidate, "candidate_unavailable"))
            continue
        returns = by_date[candidate.method]
        for start in range(
            policy.minimum_training_observations, len(dates), policy.test_window_observations
        ):
            test_dates = dates[start : start + policy.test_window_observations]
            if len(test_dates) != policy.test_window_observations:
                continue
            test = [returns[day] for day in test_dates]
            pre_cost = _compound(test)
            cost = policy.transaction_cost_rate
            results.append(
                ValidationSplit(
                    split_id=stable_contract_id(
                        "multivariate_validation_split",
                        {
                            "method": candidate.method,
                            "train_end": dates[start - 1],
                            "test_start": test_dates[0],
                            "policy": policy.to_row(),
                        },
                    ),
                    method=candidate.method,
                    train_start=dates[0],
                    train_end=dates[start - 1],
                    test_start=test_dates[0],
                    test_end=test_dates[-1],
                    pre_cost_return=pre_cost,
                    transaction_cost=cost,
                    post_cost_return=pre_cost - cost,
                    volatility=_volatility(test),
                    status="complete",
                    reason=None,
                )
            )
    return tuple(results)


def _portfolio_returns_by_date(
    candidates: Sequence[PortfolioCandidate], rows: Sequence[Mapping[str, Any]]
) -> dict[str, dict[str, float]]:
    indexed: dict[tuple[str, str, str], dict[str, float]] = {}
    for row in rows:
        key = (str(row["isin"]), str(row["exchange"]), str(row["code"]))
        indexed.setdefault(key, {})[str(row["date"])] = float(row.get("return", 0))
    output: dict[str, dict[str, float]] = {}
    for candidate in candidates:
        if candidate.status != "feasible":
            output[candidate.method] = {}
            continue
        weights = {key.as_tuple(): weight for key, weight in candidate.weights}
        keys = tuple(weights)
        if any(key not in indexed for key in keys):
            output[candidate.method] = {}
            continue
        common: set[str] = set(indexed[keys[0]]) if keys else set()
        for key in keys[1:]:
            common &= set(indexed[key])
        output[candidate.method] = {
            day: sum(weight * indexed[key][day] for key, weight in weights.items())
            for day in common
        }
    return output


def _unavailable(candidate: PortfolioCandidate, reason: str) -> ValidationSplit:
    return ValidationSplit(
        stable_contract_id(
            "multivariate_validation_split", {"method": candidate.method, "reason": reason}
        ),
        candidate.method,
        "",
        "",
        "",
        "",
        0.0,
        0.0,
        0.0,
        None,
        "unavailable",
        reason,
    )


def _compound(values: Sequence[float]) -> float:
    wealth = 1.0
    for value in values:
        wealth *= 1 + value
    return wealth - 1


def _volatility(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    average = sum(values) / len(values)
    return sqrt(sum((value - average) ** 2 for value in values) / (len(values) - 1))

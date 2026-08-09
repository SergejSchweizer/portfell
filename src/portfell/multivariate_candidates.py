"""Comparable monthly-distribution ETF portfolio candidates.

All candidates consume the exact canonical covariance artifact and aligned
return rows passed by the Multivariate orchestration boundary.  This module
does not select a winner and never replaces an unavailable solver with Equal
Weight.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import sqrt
from typing import Any

from portfell.contract_versioning import ContractVersion, stable_contract_id
from portfell.income import IncomeEvidence
from portfell.multivariate_inputs import MultivariateInputSnapshot, MultivariateListingKey
from portfell.multivariate_risk_model import MultivariateRiskModelArtifact
from portfell.portfolio import portfolio_variance
from portfell.portfolio_parts.clustering import (
    correlation_distance_matrix,
    quasi_diagonal_order,
    recursive_bisection,
    single_linkage,
)
from portfell.portfolio_parts.cvar import historical_var_and_cvar, solve_minimum_cvar
from portfell.portfolio_parts.solvers import (
    dense_covariance_matrix,
    inverse_volatility_weights,
    project_capped_simplex,
    solve_equal_risk_contribution,
    solve_minimum_variance,
)

CANDIDATE_CONTRACT = ContractVersion("multivariate.candidates", 1)
METHODS = (
    "equal_weight",
    "inverse_volatility",
    "minimum_variance",
    "equal_risk_contribution",
    "hierarchical_risk_parity",
    "minimum_cvar",
)
BASELINE_METHODS = frozenset({"equal_weight", "inverse_volatility"})


@dataclass(frozen=True)
class MonthlyDistributionEtfPortfolioPolicy:
    version: ContractVersion = CANDIDATE_CONTRACT
    min_weight: float = 0.0
    max_weight: float = 0.2
    minimum_holding_count: int = 2
    cvar_confidence_level: float = 0.95

    def __post_init__(self) -> None:
        if not 0 <= self.min_weight <= self.max_weight <= 1:
            raise ValueError("weights must satisfy 0 <= minimum <= maximum <= 1")
        if self.minimum_holding_count < 2:
            raise ValueError("minimum_holding_count must be at least two")

    def to_row(self) -> dict[str, object]:
        return {
            "version": self.version.qualified_name,
            "min_weight": self.min_weight,
            "max_weight": self.max_weight,
            "minimum_holding_count": self.minimum_holding_count,
            "cvar_confidence_level": self.cvar_confidence_level,
        }


DEFAULT_MONTHLY_DISTRIBUTION_ETF_PORTFOLIO_POLICY = MonthlyDistributionEtfPortfolioPolicy()


@dataclass(frozen=True)
class PortfolioCandidate:
    candidate_id: str
    method: str
    baseline: bool
    status: str
    reasons: tuple[str, ...]
    weights: tuple[tuple[MultivariateListingKey, float], ...]
    variance: float | None
    volatility: float | None
    var: float | None
    cvar: float | None
    maximum_weight: float | None
    herfindahl_index: float | None
    effective_holding_count: float | None
    gross_ttm_distribution_yield: float | None
    gross_monthly_distribution: float | None


def build_candidate_set(
    *,
    snapshot: MultivariateInputSnapshot,
    risk_model: MultivariateRiskModelArtifact,
    return_rows: Sequence[Mapping[str, Any]],
    income: Mapping[MultivariateListingKey, IncomeEvidence],
    policy: MonthlyDistributionEtfPortfolioPolicy = (
        DEFAULT_MONTHLY_DISTRIBUTION_ETF_PORTFOLIO_POLICY
    ),
) -> tuple[PortfolioCandidate, ...]:
    """Build the six stable candidates from one input/risk-model pair."""
    infeasible_reason = _feasibility_reason(snapshot, risk_model, policy)
    return tuple(
        _unavailable(snapshot, risk_model, policy, method, infeasible_reason)
        if infeasible_reason
        else _candidate(snapshot, risk_model, return_rows, income, policy, method)
        for method in METHODS
    )


def _feasibility_reason(
    snapshot: MultivariateInputSnapshot,
    risk_model: MultivariateRiskModelArtifact,
    policy: MonthlyDistributionEtfPortfolioPolicy,
) -> str | None:
    count = len(snapshot.listing_keys)
    if not snapshot.eligible:
        return "input_snapshot_unavailable"
    if not risk_model.available:
        return "risk_model_unavailable"
    if count < policy.minimum_holding_count:
        return "minimum_holding_count_not_met"
    if count * policy.max_weight < 1 - 1e-12 or count * policy.min_weight > 1 + 1e-12:
        return "infeasible_weight_bounds"
    return None


def _candidate(
    snapshot: MultivariateInputSnapshot,
    risk_model: MultivariateRiskModelArtifact,
    return_rows: Sequence[Mapping[str, Any]],
    income: Mapping[MultivariateListingKey, IncomeEvidence],
    policy: MonthlyDistributionEtfPortfolioPolicy,
    method: str,
) -> PortfolioCandidate:
    listings = risk_model.listings
    covariances = _covariance_map(risk_model)
    try:
        weights = _weights(method, listings, covariances, return_rows, policy)
    except ValueError as error:
        return _unavailable(snapshot, risk_model, policy, method, str(error))
    metrics = _metrics(listings, weights, covariances, return_rows, income, policy)
    identity = stable_contract_id(
        "multivariate_candidate",
        {
            "contract": CANDIDATE_CONTRACT.qualified_name,
            "snapshot_id": snapshot.snapshot_id,
            "risk_model_id": risk_model.risk_model_id,
            "method": method,
            "policy": policy.to_row(),
            "weights": [
                (key.as_tuple(), value) for key, value in zip(listings, weights, strict=True)
            ],
        },
    )
    return PortfolioCandidate(
        identity,
        method,
        method in BASELINE_METHODS,
        "feasible",
        (),
        tuple(zip(listings, weights, strict=True)),
        **metrics,
    )


def _weights(
    method: str,
    listings: tuple[MultivariateListingKey, ...],
    covariances: dict[tuple[tuple[str, str, str], tuple[str, str, str]], float],
    rows: Sequence[Mapping[str, Any]],
    policy: MonthlyDistributionEtfPortfolioPolicy,
) -> tuple[float, ...]:
    keys = tuple(item.as_tuple() for item in listings)
    if method == "equal_weight":
        return tuple(
            project_capped_simplex(
                [1 / len(keys)] * len(keys),
                min_weight=policy.min_weight,
                max_weight=policy.max_weight,
            )
        )
    if method == "inverse_volatility":
        return inverse_volatility_weights(
            keys, covariances, min_weight=policy.min_weight, max_weight=policy.max_weight
        )
    if method == "minimum_variance":
        outcome = solve_minimum_variance(
            keys,
            covariances,
            min_weight=policy.min_weight,
            max_weight=policy.max_weight,
            max_iterations=30_000,
        )
        if not outcome.converged:
            raise ValueError("minimum_variance_solver_not_converged")
        return outcome.weights
    if method == "equal_risk_contribution":
        outcome = solve_equal_risk_contribution(
            keys,
            covariances,
            min_weight=policy.min_weight,
            max_weight=policy.max_weight,
            max_iterations=30_000,
        )
        if not outcome.converged:
            raise ValueError("equal_risk_contribution_solver_not_converged")
        return outcome.weights
    if method == "hierarchical_risk_parity":
        matrix = dense_covariance_matrix(keys, covariances)
        order = quasi_diagonal_order(single_linkage(correlation_distance_matrix(matrix)), len(keys))
        raw, _splits = recursive_bisection(order, matrix)
        return tuple(
            project_capped_simplex(
                [raw[index] for index in range(len(keys))],
                min_weight=policy.min_weight,
                max_weight=policy.max_weight,
            )
        )
    if method == "minimum_cvar":
        matrix = _aligned_matrix(keys, rows)
        outcome = solve_minimum_cvar(
            matrix,
            confidence_level=policy.cvar_confidence_level,
            min_weight=policy.min_weight,
            max_weight=policy.max_weight,
        )
        if not outcome.converged:
            raise ValueError("minimum_cvar_solver_not_converged")
        return outcome.weights
    raise ValueError("unsupported_candidate_method")


def _metrics(
    listings: tuple[MultivariateListingKey, ...],
    weights: tuple[float, ...],
    covariances: Mapping[tuple[tuple[str, str, str], tuple[str, str, str]], float],
    rows: Sequence[Mapping[str, Any]],
    income: Mapping[MultivariateListingKey, IncomeEvidence],
    policy: MonthlyDistributionEtfPortfolioPolicy,
) -> dict[str, float | None]:
    keys = tuple(item.as_tuple() for item in listings)
    variance = portfolio_variance(keys, weights, covariances)
    matrix = _aligned_matrix(keys, rows)
    losses = [
        -sum(weight * value for weight, value in zip(weights, row, strict=True)) for row in matrix
    ]
    var, cvar, _ = historical_var_and_cvar(losses, policy.cvar_confidence_level)
    yields = [
        evidence.gross_ttm_distribution_yield if (evidence := income.get(listing)) else None
        for listing in listings
    ]
    monthly = [
        evidence.mean_observed_monthly_distribution if (evidence := income.get(listing)) else None
        for listing in listings
    ]
    gross_yield = _weighted_optional(weights, yields)
    gross_monthly = _weighted_optional(weights, monthly)
    return {
        "variance": variance,
        "volatility": sqrt(max(variance, 0)),
        "var": var,
        "cvar": cvar,
        "maximum_weight": max(weights),
        "herfindahl_index": sum(weight * weight for weight in weights),
        "effective_holding_count": 1 / sum(weight * weight for weight in weights),
        "gross_ttm_distribution_yield": gross_yield,
        "gross_monthly_distribution": gross_monthly,
    }


def _unavailable(
    snapshot: MultivariateInputSnapshot,
    risk_model: MultivariateRiskModelArtifact,
    policy: MonthlyDistributionEtfPortfolioPolicy,
    method: str,
    reason: str,
) -> PortfolioCandidate:
    identity = stable_contract_id(
        "multivariate_candidate",
        {
            "snapshot_id": snapshot.snapshot_id,
            "risk_model_id": risk_model.risk_model_id,
            "method": method,
            "policy": policy.to_row(),
            "reason": reason,
        },
    )
    return PortfolioCandidate(
        identity,
        method,
        method in BASELINE_METHODS,
        "unavailable",
        (reason,),
        (),
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )


def _weighted_optional(weights: Sequence[float], values: Sequence[float | None]) -> float | None:
    if any(value is None for value in values):
        return None
    return sum(
        weight * value for weight, value in zip(weights, values, strict=True) if value is not None
    )


def _covariance_map(
    risk_model: MultivariateRiskModelArtifact,
) -> dict[tuple[tuple[str, str, str], tuple[str, str, str]], float]:
    return {
        (left.as_tuple(), right.as_tuple()): risk_model.covariance[left_index][right_index]
        for left_index, left in enumerate(risk_model.listings)
        for right_index, right in enumerate(risk_model.listings)
    }


def _aligned_matrix(
    keys: tuple[tuple[str, str, str], ...], rows: Sequence[Mapping[str, Any]]
) -> list[list[float]]:
    indexed: dict[tuple[str, str, str], dict[str, float]] = {}
    for row in rows:
        key = (str(row["isin"]), str(row["exchange"]), str(row["code"]))
        indexed.setdefault(key, {})[str(row["date"])] = float(row.get("return", 0))
    if not keys or any(key not in indexed for key in keys):
        raise ValueError("incomplete_aligned_return_history")
    common_dates: set[str] = set(indexed[keys[0]])
    for key in keys[1:]:
        common_dates &= set(indexed[key])
    dates = sorted(common_dates)
    if len(dates) < 2:
        raise ValueError("insufficient_aligned_return_history")
    return [[indexed[key][date] for key in keys] for date in dates]

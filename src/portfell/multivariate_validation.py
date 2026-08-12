"""Walk-forward and deterministic stress validation for candidate portfolios."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import exp, sqrt
from random import Random
from typing import Any

from portfell.contract_versioning import ContractVersion, stable_contract_id
from portfell.multivariate_candidates import PortfolioCandidate
from portfell.multivariate_inputs import MultivariateListingKey

VALIDATION_CONTRACT = ContractVersion("multivariate.validation", 4)
CandidateFactory = Callable[[Sequence[Mapping[str, Any]]], Sequence[PortfolioCandidate]]


@dataclass(frozen=True)
class WalkForwardPolicy:
    version: ContractVersion = VALIDATION_CONTRACT
    minimum_training_observations: int = 100
    test_window_observations: int = 21
    maximum_refit_count: int = 24
    minimum_completed_splits: int = 2
    transaction_cost_rate: float = 0.0005
    bootstrap_seed: int = 41
    bootstrap_observations: int = 252

    def to_row(self) -> dict[str, object]:
        return {
            "version": self.version.qualified_name,
            "minimum_training_observations": self.minimum_training_observations,
            "test_window_observations": self.test_window_observations,
            "maximum_refit_count": self.maximum_refit_count,
            "minimum_completed_splits": self.minimum_completed_splits,
            "transaction_cost_rate": self.transaction_cost_rate,
            "bootstrap_seed": self.bootstrap_seed,
            "bootstrap_observations": self.bootstrap_observations,
        }


DEFAULT_WALK_FORWARD_POLICY = WalkForwardPolicy()
_SCENARIO_NAMES = (
    "historical",
    "seeded_block_bootstrap",
    "covariance_perturbation",
    "correlation_convergence",
    "distribution_cut",
)


def walk_forward_training_rows(
    *,
    candidates: Sequence[PortfolioCandidate],
    return_rows: Sequence[Mapping[str, Any]],
    policy: WalkForwardPolicy = DEFAULT_WALK_FORWARD_POLICY,
) -> tuple[tuple[Mapping[str, Any], ...], ...]:
    dates = _common_dates(candidates, return_rows)
    if len(dates) < policy.minimum_training_observations + policy.test_window_observations:
        return ()
    return tuple(
        tuple(row for row in return_rows if str(row.get("date", "")) in set(dates[:start]))
        for start in _walk_forward_starts(dates, policy)
    )


def _walk_forward_starts(dates: Sequence[str], policy: WalkForwardPolicy) -> tuple[int, ...]:
    starts = tuple(
        start
        for start in range(
            policy.minimum_training_observations, len(dates), policy.test_window_observations
        )
        if len(dates[start : start + policy.test_window_observations])
        == policy.test_window_observations
    )
    if policy.maximum_refit_count < 1:
        raise ValueError("maximum_refit_count must be positive")
    if len(starts) <= policy.maximum_refit_count:
        return starts
    last_index = len(starts) - 1
    limit_index = policy.maximum_refit_count - 1
    return tuple(
        starts[index * last_index // limit_index] for index in range(policy.maximum_refit_count)
    )


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
    candidate_id: str = ""
    turnover: float = 0.0
    weights: tuple[tuple[MultivariateListingKey, float], ...] = ()
    requested_method: str = ""
    risk_model_id: str | None = None
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    conditional_value_at_risk: float | None = None
    max_drawdown: float | None = None
    herfindahl_index: float | None = None
    income_available: bool = False
    test_observation_count: int = 0


@dataclass(frozen=True)
class ValidationScenario:
    """A deterministic historical or synthetic adverse scenario for one candidate."""

    scenario_id: str
    candidate_id: str
    method: str
    scenario: str
    compounded_return: float | None
    max_drawdown: float | None
    value_at_risk: float | None
    conditional_value_at_risk: float | None
    status: str
    reason: str | None


@dataclass(frozen=True)
class CandidateScorecard:
    """Comparable summary of the same out-of-sample and stress evidence."""

    candidate_id: str
    method: str
    completed_split_count: int
    median_post_cost_return: float | None
    adverse_post_cost_return: float | None
    median_volatility: float | None
    scenario_count: int
    availability_reasons: tuple[str, ...]


def validate_candidates(
    *,
    candidates: Sequence[PortfolioCandidate],
    return_rows: Sequence[Mapping[str, Any]],
    policy: WalkForwardPolicy = DEFAULT_WALK_FORWARD_POLICY,
    candidate_factory: CandidateFactory | None = None,
    precomputed_candidates: Sequence[Sequence[PortfolioCandidate]] | None = None,
    risk_model_id: str | None = None,
) -> tuple[ValidationSplit, ...]:
    """Validate candidates on common out-of-sample slices.

    A supplied factory receives only the training rows for each split.  This is
    the production path: it forces risk-model and optimizer re-estimation
    before any test observation is evaluated.  The no-factory fallback keeps
    this pure helper useful for explicit static-weight research fixtures.
    """

    if candidate_factory is not None and precomputed_candidates is not None:
        raise ValueError("candidate_factory_and_precomputed_candidates_are_exclusive")
    dates = _common_dates(candidates, return_rows)
    if len(dates) < policy.minimum_training_observations + policy.test_window_observations:
        return tuple(
            _unavailable(candidate, "insufficient_walk_forward_history") for candidate in candidates
        )
    results: list[ValidationSplit] = []
    previous_weights: dict[str, tuple[tuple[MultivariateListingKey, float], ...]] = {}
    indexed_returns = _index_return_rows(return_rows)
    refit_index = 0
    for start in _walk_forward_starts(dates, policy):
        test_dates = dates[start : start + policy.test_window_observations]
        training_rows = tuple(
            row for row in return_rows if str(row.get("date", "")) in set(dates[:start])
        )
        if precomputed_candidates is not None:
            if refit_index >= len(precomputed_candidates):
                raise ValueError("missing_precomputed_candidates")
            evaluated = tuple(precomputed_candidates[refit_index])
            refit_index += 1
        else:
            evaluated = (
                tuple(candidate_factory(training_rows)) if candidate_factory else tuple(candidates)
            )
        by_method = {candidate.method: candidate for candidate in evaluated}
        for requested in candidates:
            candidate = by_method.get(requested.method)
            if candidate is None or candidate.status != "feasible":
                results.append(_unavailable(requested, "candidate_unavailable"))
                continue
            test = _candidate_returns_for_dates(candidate, indexed_returns, test_dates)
            pre_cost = _compound(test)
            previous = previous_weights.get(candidate.method)
            turnover = _turnover(previous, candidate.weights)
            cost = (
                turnover * policy.transaction_cost_rate
                if candidate_factory is not None or precomputed_candidates is not None
                else policy.transaction_cost_rate
            )
            previous_weights[candidate.method] = candidate.weights
            results.append(
                ValidationSplit(
                    split_id=stable_contract_id(
                        "multivariate_validation_split",
                        {
                            "candidate_id": candidate.candidate_id,
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
                    candidate_id=candidate.candidate_id,
                    turnover=turnover,
                    weights=candidate.weights,
                    requested_method=requested.method,
                    risk_model_id=risk_model_id,
                    sharpe_ratio=_sharpe(test),
                    sortino_ratio=_sortino(test),
                    conditional_value_at_risk=_value_at_risk([-value for value in test])[1],
                    max_drawdown=_compound_and_drawdown(test)[1],
                    herfindahl_index=candidate.herfindahl_index,
                    income_available=candidate.gross_ttm_distribution_yield is not None,
                    test_observation_count=len(test),
                )
            )
    if precomputed_candidates is not None and refit_index != len(precomputed_candidates):
        raise ValueError("unexpected_precomputed_candidates")
    return tuple(results)


def validate_candidate_stress(
    *,
    candidates: Sequence[PortfolioCandidate],
    return_rows: Sequence[Mapping[str, Any]],
    policy: WalkForwardPolicy = DEFAULT_WALK_FORWARD_POLICY,
) -> tuple[ValidationScenario, ...]:
    """Produce deterministic scenario evidence without changing source observations.

    The distribution-cut scenario intentionally has no price-return adjustment:
    it records the cash-flow assumption boundary instead of inventing a total
    return series.
    """

    scenarios: list[ValidationScenario] = []
    for candidate in candidates:
        if candidate.status != "feasible":
            scenarios.extend(
                _unavailable_scenario(candidate, name, "candidate_unavailable")
                for name in _SCENARIO_NAMES
            )
            continue
        values = list(
            _portfolio_returns_by_date((candidate,), return_rows)[candidate.method].values()
        )
        for name, scenario_values, reason in _scenario_values(values, policy):
            scenarios.append(_scenario(candidate, name, scenario_values, reason, policy))
    return tuple(scenarios)


def build_candidate_scorecards(
    *, splits: Sequence[ValidationSplit], scenarios: Sequence[ValidationScenario]
) -> tuple[CandidateScorecard, ...]:
    """Aggregate comparable persisted evidence without ranking or selecting a winner."""

    candidate_ids = sorted(
        {item.candidate_id for item in splits if item.candidate_id}
        | {item.candidate_id for item in scenarios if item.candidate_id}
    )
    scorecards: list[CandidateScorecard] = []
    for candidate_id in candidate_ids:
        candidate_splits = [item for item in splits if item.candidate_id == candidate_id]
        candidate_scenarios = [item for item in scenarios if item.candidate_id == candidate_id]
        completed = [item for item in candidate_splits if item.status == "complete"]
        returns = sorted(item.post_cost_return for item in completed)
        volatility = sorted(item.volatility for item in completed if item.volatility is not None)
        reasons = tuple(
            sorted(
                {item.reason for item in candidate_splits if item.reason}
                | {item.reason for item in candidate_scenarios if item.reason}
            )
        )
        method = next(
            (item.method for item in candidate_splits),
            next((item.method for item in candidate_scenarios), "unavailable"),
        )
        scorecards.append(
            CandidateScorecard(
                candidate_id=candidate_id,
                method=method,
                completed_split_count=len(completed),
                median_post_cost_return=_median(returns),
                adverse_post_cost_return=returns[0] if returns else None,
                median_volatility=_median(volatility),
                scenario_count=len(candidate_scenarios),
                availability_reasons=reasons,
            )
        )
    return tuple(scorecards)


def _portfolio_returns_by_date(
    candidates: Sequence[PortfolioCandidate], rows: Sequence[Mapping[str, Any]]
) -> dict[str, dict[str, float]]:
    indexed = _index_return_rows(rows)
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


def _index_return_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, str], dict[str, float]]:
    indexed: dict[tuple[str, str, str], dict[str, float]] = {}
    for row in rows:
        key = (str(row["isin"]), str(row["exchange"]), str(row["code"]))
        indexed.setdefault(key, {})[str(row["date"])] = float(row.get("return", 0))
    return indexed


def _candidate_returns_for_dates(
    candidate: PortfolioCandidate,
    indexed_returns: Mapping[tuple[str, str, str], Mapping[str, float]],
    dates: Sequence[str],
) -> list[float]:
    weights = {key.as_tuple(): weight for key, weight in candidate.weights}
    if any(key not in indexed_returns for key in weights):
        raise ValueError("candidate_return_history_unavailable")
    return [
        sum(weight * indexed_returns[key][day] for key, weight in weights.items()) for day in dates
    ]


def _common_dates(
    candidates: Sequence[PortfolioCandidate], rows: Sequence[Mapping[str, Any]]
) -> tuple[str, ...]:
    keys = {
        key.as_tuple()
        for candidate in candidates
        if candidate.status == "feasible"
        for key, _ in candidate.weights
    }
    indexed = {
        key: {
            str(row["date"])
            for row in rows
            if (str(row["isin"]), str(row["exchange"]), str(row["code"])) == key
        }
        for key in keys
    }
    available = [dates for dates in indexed.values() if dates]
    if not available:
        return ()
    common = set(available[0])
    for dates in available[1:]:
        common &= dates
    return tuple(sorted(common))


def _turnover(
    previous: tuple[tuple[MultivariateListingKey, float], ...] | None,
    current: tuple[tuple[MultivariateListingKey, float], ...],
) -> float:
    if previous is None:
        # The first out-of-sample allocation is a full rebalance from cash.
        return 1.0
    before = {key: weight for key, weight in previous}
    after = {key: weight for key, weight in current}
    return 0.5 * sum(abs(before.get(key, 0.0) - after.get(key, 0.0)) for key in before | after)


def _scenario_values(
    values: Sequence[float], policy: WalkForwardPolicy
) -> tuple[tuple[str, tuple[float, ...], str | None], ...]:
    if not values:
        return tuple((name, (), "insufficient_return_history") for name in _SCENARIO_NAMES)
    rng = Random(policy.bootstrap_seed)
    count = min(policy.bootstrap_observations, len(values))
    bootstrap = _seeded_block_bootstrap(values, count, rng)
    mean = sum(values) / len(values)
    covariance_perturbed = tuple(mean + 1.25 * (value - mean) for value in values)
    convergence = tuple(0.75 * value + 0.25 * mean for value in values)
    return (
        ("historical", tuple(values), None),
        ("seeded_block_bootstrap", bootstrap, None),
        ("covariance_perturbation", covariance_perturbed, None),
        ("correlation_convergence", convergence, None),
        ("distribution_cut", tuple(values), "cash_flow_evidence_only"),
    )


def _seeded_block_bootstrap(values: Sequence[float], count: int, rng: Random) -> tuple[float, ...]:
    """Sample deterministic contiguous five-observation blocks, not IID points."""
    if not values or count <= 0:
        return ()
    block_size = min(5, len(values))
    sampled: list[float] = []
    while len(sampled) < count:
        start = rng.randrange(len(values))
        sampled.extend(values[(start + offset) % len(values)] for offset in range(block_size))
    return tuple(sampled[:count])


def _scenario(
    candidate: PortfolioCandidate,
    name: str,
    values: Sequence[float],
    reason: str | None,
    policy: WalkForwardPolicy,
) -> ValidationScenario:
    compounded, drawdown = _compound_and_drawdown(values)
    losses = [-value for value in values]
    var, cvar = _value_at_risk(losses)
    return ValidationScenario(
        scenario_id=stable_contract_id(
            "multivariate_validation_scenario",
            {"candidate_id": candidate.candidate_id, "scenario": name, "policy": policy.to_row()},
        ),
        candidate_id=candidate.candidate_id,
        method=candidate.method,
        scenario=name,
        compounded_return=compounded,
        max_drawdown=drawdown,
        value_at_risk=var,
        conditional_value_at_risk=cvar,
        status="complete" if reason is None else "available_with_warning",
        reason=reason,
    )


def _unavailable_scenario(
    candidate: PortfolioCandidate, name: str, reason: str
) -> ValidationScenario:
    return ValidationScenario(
        scenario_id=stable_contract_id(
            "multivariate_validation_scenario",
            {"candidate_id": candidate.candidate_id, "scenario": name, "reason": reason},
        ),
        candidate_id=candidate.candidate_id,
        method=candidate.method,
        scenario=name,
        compounded_return=None,
        max_drawdown=None,
        value_at_risk=None,
        conditional_value_at_risk=None,
        status="unavailable",
        reason=reason,
    )


def _compound_and_drawdown(values: Sequence[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    wealth = peak = 1.0
    drawdown = 0.0
    for value in values:
        wealth *= exp(value)
        peak = max(peak, wealth)
        drawdown = min(drawdown, wealth / peak - 1.0)
    return wealth - 1.0, drawdown


def _value_at_risk(losses: Sequence[float]) -> tuple[float | None, float | None]:
    if not losses:
        return None, None
    ordered = sorted(losses)
    threshold = ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]
    tail = [value for value in ordered if value >= threshold]
    return threshold, sum(tail) / len(tail)


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2


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
        candidate.candidate_id,
    )


def _compound(values: Sequence[float]) -> float:
    """Compound the canonical log-return series into simple-return wealth."""
    return exp(sum(values)) - 1.0


def _volatility(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    average = sum(values) / len(values)
    return sqrt(sum((value - average) ** 2 for value in values) / (len(values) - 1))


def _sharpe(values: Sequence[float]) -> float | None:
    volatility = _volatility(values)
    return (sum(values) / len(values)) / volatility * sqrt(252) if values and volatility else None


def _sortino(values: Sequence[float]) -> float | None:
    if not values:
        return None
    downside = [min(0.0, value) for value in values]
    deviation = sqrt(sum(value * value for value in downside) / len(downside))
    return (sum(values) / len(values)) / deviation * sqrt(252) if deviation else None

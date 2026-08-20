"""Hard eligibility stage for the Multivariate optimizer universe."""

from __future__ import annotations

from dataclasses import dataclass

from portfell.multivariate.contracts.common import ListingIdentity
from portfell.multivariate.contracts.decision_reasons import DecisionReasonCode


@dataclass(frozen=True, slots=True)
class SelectorMetrics:
    listing: ListingIdentity
    annualized_geometric_return: float | None
    sharpe: float | None
    sortino: float | None
    annualized_volatility: float | None
    expected_shortfall: float | None
    maximum_drawdown: float | None
    observation_count: int | None
    distribution_frequency: str | None


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    eligible: tuple[SelectorMetrics, ...]
    rejected: tuple[tuple[ListingIdentity, DecisionReasonCode], ...]


_REQUIRED_METRICS = (
    "annualized_geometric_return",
    "sharpe",
    "sortino",
    "annualized_volatility",
    "expected_shortfall",
    "maximum_drawdown",
)


def apply_eligibility(
    rows: tuple[SelectorMetrics, ...],
    *,
    allowed_distribution_frequencies: tuple[str, ...] = (),
    minimum_observations: int = 2,
) -> EligibilityResult:
    """Remove only listings that fail frozen hard rules and record one reason each."""

    allowed = set(allowed_distribution_frequencies)
    eligible: list[SelectorMetrics] = []
    rejected: list[tuple[ListingIdentity, DecisionReasonCode]] = []
    for row in sorted(rows, key=lambda item: item.listing):
        if any(getattr(row, metric) is None for metric in _REQUIRED_METRICS):
            rejected.append((row.listing, DecisionReasonCode.DATA_UNAVAILABLE))
            continue
        if row.observation_count is None or row.observation_count < minimum_observations:
            rejected.append((row.listing, DecisionReasonCode.INSUFFICIENT_HISTORY))
            continue
        if allowed and row.distribution_frequency not in allowed:
            rejected.append((row.listing, DecisionReasonCode.DISTRIBUTION_NOT_ALLOWED))
            continue
        eligible.append(row)
    return EligibilityResult(tuple(eligible), tuple(rejected))

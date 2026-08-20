"""Frozen optimizer-method registry and typed candidate results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from portfell.multivariate.contracts.common import ListingIdentity


class PortfolioMethod(StrEnum):
    EQUAL_WEIGHT = "equal_weight"
    MINIMUM_VARIANCE = "minimum_variance"
    MAXIMUM_SHARPE = "maximum_sharpe"
    MAXIMUM_DIVERSIFICATION = "maximum_diversification"
    EQUAL_RISK_CONTRIBUTION = "equal_risk_contribution"
    HIERARCHICAL_RISK_PARITY = "hierarchical_risk_parity"
    MINIMUM_CVAR = "minimum_cvar"


PORTFOLIO_METHODS: tuple[PortfolioMethod, ...] = tuple(PortfolioMethod)


@dataclass(frozen=True, slots=True)
class CandidateResult:
    method: PortfolioMethod
    listings: tuple[ListingIdentity, ...]
    weights: tuple[float, ...] | None
    available: bool
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.available:
            if self.weights is None or len(self.weights) != len(self.listings):
                raise ValueError("available candidate requires one weight per listing")
            if any(weight < -1e-12 for weight in self.weights):
                raise ValueError("long-only candidates cannot contain negative weights")
            if abs(sum(self.weights) - 1.0) > 1e-7:
                raise ValueError("candidate weights must sum to one")
        elif not self.reason:
            raise ValueError("unavailable candidate requires a reason")

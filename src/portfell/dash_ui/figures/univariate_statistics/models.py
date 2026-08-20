"""Presentation-only inputs for Univariate figures."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class UniversePointState(StrEnum):
    SELECTED = "selected"
    REJECTED_BY_SELECTION = "rejected_by_selection"
    DATA_QUALITY_EXCLUDED = "data_quality_excluded"


@dataclass(frozen=True, slots=True)
class UnivariatePoint:
    isin: str
    exchange: str
    code: str
    annualized_volatility: float
    annualized_geometric_return: float
    sharpe: float | None
    sortino: float | None
    expected_shortfall: float | None
    maximum_drawdown: float | None
    distribution_frequency: str | None
    annual_dividend_yield: float | None
    observation_count: int | None
    state: UniversePointState

    @property
    def listing_id(self) -> str:
        return f"{self.isin}|{self.exchange}|{self.code}"


@dataclass(frozen=True, slots=True)
class ListingHistory:
    isin: str
    exchange: str
    code: str
    first_date: str | None
    last_date: str | None
    observation_count: int | None

    @property
    def listing_id(self) -> str:
        return f"{self.isin}|{self.exchange}|{self.code}"

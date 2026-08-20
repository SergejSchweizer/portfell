"""Presentation-only Bivariate figure inputs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BivariateUniversePoint:
    isin: str
    exchange: str
    code: str
    annualized_geometric_return: float
    median_pearson: float | None
    median_spearman: float | None
    median_downside: float | None
    median_lower_tail: float | None
    median_co_exceedance: float | None
    median_drawdown_overlap: float | None
    usable_pair_count: int

    @property
    def listing_id(self) -> str:
        return f"{self.isin}|{self.exchange}|{self.code}"

    def metric(self, metric_id: str) -> float | None:
        values = {
            "median_pearson": self.median_pearson,
            "median_spearman": self.median_spearman,
            "median_downside": self.median_downside,
            "median_lower_tail": self.median_lower_tail,
            "median_co_exceedance": self.median_co_exceedance,
            "median_drawdown_overlap": self.median_drawdown_overlap,
        }
        if metric_id not in values:
            raise ValueError(f"unknown dependence metric: {metric_id}")
        return values[metric_id]


@dataclass(frozen=True, slots=True)
class PairHistoryPoint:
    left_listing_id: str
    right_listing_id: str
    shared_observations: int | None
    first_date: str | None
    last_date: str | None

    @property
    def pair_id(self) -> str:
        left, right = sorted((self.left_listing_id, self.right_listing_id))
        return f"{left}::{right}"

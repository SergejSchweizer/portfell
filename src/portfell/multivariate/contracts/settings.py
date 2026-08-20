"""Immutable user-selectable Multivariate settings."""

from __future__ import annotations

from dataclasses import dataclass

from portfell.multivariate.contracts.objectives import OptimizationObjective


@dataclass(frozen=True, slots=True)
class MultivariateOptimizationSettings:
    objective: OptimizationObjective = OptimizationObjective.RETURN_RISK
    allowed_distribution_frequencies: tuple[str, ...] = ()
    min_weight: float = 0.0
    max_weight: float = 1.0
    max_holdings: int | None = None
    transaction_cost_rate: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_weight <= self.max_weight <= 1.0:
            raise ValueError("weight bounds must satisfy 0 <= min_weight <= max_weight <= 1")
        if self.max_holdings is not None and self.max_holdings < 1:
            raise ValueError("max_holdings must be positive")
        if self.transaction_cost_rate < 0:
            raise ValueError("transaction_cost_rate cannot be negative")
        if len(set(self.allowed_distribution_frequencies)) != len(self.allowed_distribution_frequencies):
            raise ValueError("distribution frequencies must be unique")

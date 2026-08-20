"""Typed Multivariate Statistics optimizer view model."""

from __future__ import annotations

from dataclasses import dataclass

from portfell.dash_ui.core.run_control import StatisticsRunControl
from portfell.multivariate.contracts.objectives import DEFAULT_OBJECTIVE, OBJECTIVES, OptimizationObjective


@dataclass(frozen=True, slots=True)
class MultivariateView:
    run_control: StatisticsRunControl
    objective: OptimizationObjective = DEFAULT_OBJECTIVE
    min_weight: float = 0.0
    max_weight: float = 1.0
    max_holdings: int | None = None
    transaction_cost_rate: float = 0.0
    result_revision: str | None = None
    result_objective: OptimizationObjective | None = None

    @property
    def objective_options(self) -> tuple[tuple[str, str], ...]:
        return tuple((definition.objective.value, definition.label) for definition in OBJECTIVES.values())

    @property
    def result_is_stale(self) -> bool:
        return self.result_revision is not None and self.result_objective != self.objective

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_weight <= self.max_weight <= 1.0:
            raise ValueError("weight bounds are invalid")
        if self.max_holdings is not None and self.max_holdings < 1:
            raise ValueError("max_holdings must be positive")
        if self.transaction_cost_rate < 0:
            raise ValueError("transaction_cost_rate cannot be negative")

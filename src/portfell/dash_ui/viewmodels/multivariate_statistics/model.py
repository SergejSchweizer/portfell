"""Typed Multivariate Statistics optimizer view model."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from portfell.dash_ui.core.run_control import StatisticsRunControl
from portfell.multivariate.contracts.objectives import (
    DEFAULT_OBJECTIVE,
    OBJECTIVES,
    OptimizationObjective,
)
from portfell.multivariate.contracts.serialization import canonical_json


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
    result_settings_signature: str | None = None

    @property
    def objective_options(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (definition.objective.value, definition.label)
            for definition in OBJECTIVES.values()
        )

    @property
    def settings_signature(self) -> str:
        payload = canonical_json(
            {
                "objective": self.objective,
                "min_weight": self.min_weight,
                "max_weight": self.max_weight,
                "max_holdings": self.max_holdings,
                "transaction_cost_rate": self.transaction_cost_rate,
            }
        ).encode()
        return hashlib.sha256(payload).hexdigest()

    @property
    def result_is_stale(self) -> bool:
        if self.result_revision is None:
            return False
        if self.result_objective != self.objective:
            return True
        return self.result_settings_signature != self.settings_signature

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_weight <= self.max_weight <= 1.0:
            raise ValueError("weight bounds are invalid")
        if self.max_holdings is not None and self.max_holdings < 1:
            raise ValueError("max_holdings must be positive")
        if self.transaction_cost_rate < 0:
            raise ValueError("transaction_cost_rate cannot be negative")

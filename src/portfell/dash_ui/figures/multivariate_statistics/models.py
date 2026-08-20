"""Presentation-only inputs for Multivariate figures."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PortfolioCandidatePoint:
    configuration_id: str
    annualized_oos_return: float | None
    oos_annualized_volatility: float | None
    objective_value: float | None
    winner: bool
    method: str
    risk_model: str


@dataclass(frozen=True, slots=True)
class DecisionStageView:
    stage: str
    status: str
    reason: str | None
    selected_ids: tuple[str, ...]
    rejected_count: int
    metrics: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class WalkForwardView:
    split_id: str
    training_first: str
    training_last: str
    test_first: str
    test_last: str
    training_observations: int
    test_observations: int

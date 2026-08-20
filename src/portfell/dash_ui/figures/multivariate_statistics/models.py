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


@dataclass(frozen=True, slots=True)
class PersistedHistoryRangeView:
    evidence_id: str
    first_date: str | None
    last_date: str | None
    observation_count: int | None
    status: str = "available"
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raise ValueError("evidence_id is required")
        if self.observation_count is None and (
            self.first_date is not None or self.last_date is not None
        ):
            raise ValueError("unavailable history cannot carry guessed dates")
        if self.observation_count is not None and self.observation_count < 0:
            raise ValueError("observation_count cannot be negative")

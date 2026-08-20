"""Frozen Multivariate optimization objective registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OptimizationObjective(StrEnum):
    RETURN_RISK = "return_risk"
    RETURN_DRAWDOWN = "return_drawdown"
    MINIMUM_RISK = "minimum_risk"


class RankingDirection(StrEnum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


@dataclass(frozen=True, slots=True)
class RankingTerm:
    metric: str
    direction: RankingDirection
    absolute: bool = False


@dataclass(frozen=True, slots=True)
class ObjectiveDefinition:
    objective: OptimizationObjective
    label: str
    ranking: tuple[RankingTerm, ...]


OBJECTIVES: dict[OptimizationObjective, ObjectiveDefinition] = {
    OptimizationObjective.RETURN_RISK: ObjectiveDefinition(
        OptimizationObjective.RETURN_RISK,
        "Return / Risk",
        (
            RankingTerm("median_oos_sharpe", RankingDirection.MAXIMIZE),
            RankingTerm("median_oos_sortino", RankingDirection.MAXIMIZE),
            RankingTerm("whole_oos_maximum_drawdown", RankingDirection.MINIMIZE, absolute=True),
            RankingTerm("oos_cvar", RankingDirection.MINIMIZE),
            RankingTerm("median_turnover", RankingDirection.MINIMIZE),
            RankingTerm("configuration_id", RankingDirection.MINIMIZE),
        ),
    ),
    OptimizationObjective.RETURN_DRAWDOWN: ObjectiveDefinition(
        OptimizationObjective.RETURN_DRAWDOWN,
        "Return / Drawdown",
        (
            RankingTerm("oos_calmar", RankingDirection.MAXIMIZE),
            RankingTerm("annualized_oos_return", RankingDirection.MAXIMIZE),
            RankingTerm("whole_oos_maximum_drawdown", RankingDirection.MINIMIZE, absolute=True),
            RankingTerm("oos_cvar", RankingDirection.MINIMIZE),
            RankingTerm("median_turnover", RankingDirection.MINIMIZE),
            RankingTerm("configuration_id", RankingDirection.MINIMIZE),
        ),
    ),
    OptimizationObjective.MINIMUM_RISK: ObjectiveDefinition(
        OptimizationObjective.MINIMUM_RISK,
        "Minimum Risk",
        (
            RankingTerm("oos_annualized_volatility", RankingDirection.MINIMIZE),
            RankingTerm("whole_oos_maximum_drawdown", RankingDirection.MINIMIZE, absolute=True),
            RankingTerm("oos_cvar", RankingDirection.MINIMIZE),
            RankingTerm("annualized_oos_return", RankingDirection.MAXIMIZE),
            RankingTerm("median_turnover", RankingDirection.MINIMIZE),
            RankingTerm("configuration_id", RankingDirection.MINIMIZE),
        ),
    ),
}

DEFAULT_OBJECTIVE = OptimizationObjective.RETURN_RISK

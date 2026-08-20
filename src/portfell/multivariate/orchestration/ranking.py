"""Objective-specific OOS ranking with frozen tie-break semantics."""

from __future__ import annotations

import math
from dataclasses import dataclass

from portfell.multivariate.contracts.objectives import OptimizationObjective


@dataclass(frozen=True, slots=True)
class OOSScore:
    configuration_id: str
    median_oos_sharpe: float | None
    median_oos_sortino: float | None
    whole_oos_maximum_drawdown: float | None
    oos_cvar: float | None
    median_turnover: float | None
    annualized_oos_return: float | None
    oos_annualized_volatility: float | None

    @property
    def oos_calmar(self) -> float | None:
        if self.annualized_oos_return is None or self.whole_oos_maximum_drawdown is None:
            return None
        drawdown = abs(self.whole_oos_maximum_drawdown)
        if drawdown <= 1e-15:
            return None
        return self.annualized_oos_return / drawdown


def _required(value: float | None) -> float:
    if value is None or not math.isfinite(value):
        raise ValueError("required OOS ranking metric is unavailable")
    return value


def ranking_key(score: OOSScore, objective: OptimizationObjective) -> tuple[object, ...]:
    """Return an ascending key implementing the exact frozen objective ranking."""

    if objective is OptimizationObjective.RETURN_RISK:
        return (
            -_required(score.median_oos_sharpe),
            -_required(score.median_oos_sortino),
            abs(_required(score.whole_oos_maximum_drawdown)),
            _required(score.oos_cvar),
            _required(score.median_turnover),
            score.configuration_id,
        )
    if objective is OptimizationObjective.RETURN_DRAWDOWN:
        return (
            -_required(score.oos_calmar),
            -_required(score.annualized_oos_return),
            abs(_required(score.whole_oos_maximum_drawdown)),
            _required(score.oos_cvar),
            _required(score.median_turnover),
            score.configuration_id,
        )
    if objective is OptimizationObjective.MINIMUM_RISK:
        return (
            _required(score.oos_annualized_volatility),
            abs(_required(score.whole_oos_maximum_drawdown)),
            _required(score.oos_cvar),
            -_required(score.annualized_oos_return),
            _required(score.median_turnover),
            score.configuration_id,
        )
    raise ValueError(f"unsupported objective: {objective}")


def select_winner(scores: tuple[OOSScore, ...], objective: OptimizationObjective) -> OOSScore:
    """Select exactly one OOS winner; unavailable candidates are excluded explicitly."""

    ranked: list[tuple[tuple[object, ...], OOSScore]] = []
    for score in scores:
        try:
            ranked.append((ranking_key(score, objective), score))
        except ValueError:
            continue
    if not ranked:
        raise ValueError("no candidate has complete OOS evidence for the selected objective")
    ranked.sort(key=lambda item: item[0])
    return ranked[0][1]

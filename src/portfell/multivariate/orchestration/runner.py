"""Durable-service friendly Multivariate orchestration state machine."""

from __future__ import annotations

from dataclasses import dataclass

from portfell.multivariate.contracts.objectives import OptimizationObjective
from portfell.multivariate.contracts.runs import MultivariateProgressPhase
from portfell.multivariate.orchestration.ranking import OOSScore, select_winner
from portfell.multivariate.orchestration.walk_forward import WalkForwardSplit


@dataclass(frozen=True, slots=True)
class FinalRefit:
    configuration_id: str
    first_date: str
    last_date: str
    observation_count: int
    weights: tuple[float, ...]

    def __post_init__(self) -> None:
        if self.observation_count < 1:
            raise ValueError("final refit requires observations")
        if not self.weights or abs(sum(self.weights) - 1.0) > 1e-7:
            raise ValueError("final refit weights must sum to one")


@dataclass(frozen=True, slots=True)
class MultivariateRunResult:
    run_id: str
    objective: OptimizationObjective
    phases: tuple[MultivariateProgressPhase, ...]
    splits: tuple[WalkForwardSplit, ...]
    winner: OOSScore
    final_refit: FinalRefit


def complete_run(
    *,
    run_id: str,
    objective: OptimizationObjective,
    splits: tuple[WalkForwardSplit, ...],
    scores: tuple[OOSScore, ...],
    final_refit: FinalRefit,
) -> MultivariateRunResult:
    """Complete ranking/publication only after all required evidence exists."""

    winner = select_winner(scores, objective)
    if final_refit.configuration_id != winner.configuration_id:
        raise ValueError("final refit must use the OOS-winning configuration")
    return MultivariateRunResult(
        run_id=run_id,
        objective=objective,
        phases=tuple(MultivariateProgressPhase),
        splits=splits,
        winner=winner,
        final_refit=final_refit,
    )

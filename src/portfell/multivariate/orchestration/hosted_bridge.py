"""Bridge persisted hosted validation evidence into the frozen PR272 OOS contracts."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import median

from portfell.multivariate.contracts.objectives import DEFAULT_OBJECTIVE, OptimizationObjective
from portfell.multivariate.orchestration.ranking import OOSScore
from portfell.multivariate.orchestration.runner import FinalRefit, MultivariateRunResult, complete_run
from portfell.multivariate.orchestration.walk_forward import WalkForwardSplit


@dataclass(frozen=True, slots=True)
class HostedOOSSelection:
    """Validated OOS result plus the full-data candidate selected for final publication."""

    result: MultivariateRunResult
    candidate_id: str


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _median(values: Sequence[float | None]) -> float | None:
    available = [value for value in values if value is not None]
    return None if not available else float(median(available))


def _annualized_return(rows: Sequence[Mapping[str, object]]) -> float | None:
    completed = [row for row in rows if row.get("status") == "complete"]
    observations = sum(int(row.get("test_observation_count") or 0) for row in completed)
    if observations <= 0:
        return None
    wealth = 1.0
    for row in completed:
        value = _optional_float(row.get("post_cost_return"))
        if value is None or value <= -1.0:
            return None
        wealth *= 1.0 + value
    if wealth <= 0.0:
        return None
    return wealth ** (252.0 / observations) - 1.0


def _score(candidate_id: str, rows: Sequence[Mapping[str, object]]) -> OOSScore:
    completed = [row for row in rows if row.get("status") == "complete"]
    drawdowns = [_optional_float(row.get("max_drawdown")) for row in completed]
    cvars = [_optional_float(row.get("conditional_value_at_risk")) for row in completed]
    available_drawdowns = [value for value in drawdowns if value is not None]
    available_cvars = [value for value in cvars if value is not None]
    return OOSScore(
        configuration_id=candidate_id,
        median_oos_sharpe=_median([_optional_float(row.get("sharpe_ratio")) for row in completed]),
        median_oos_sortino=_median([_optional_float(row.get("sortino_ratio")) for row in completed]),
        whole_oos_maximum_drawdown=min(available_drawdowns) if available_drawdowns else None,
        oos_cvar=max(available_cvars) if available_cvars else None,
        median_turnover=_median([_optional_float(row.get("turnover")) for row in completed]),
        annualized_oos_return=_annualized_return(completed),
        oos_annualized_volatility=_median(
            [_optional_float(row.get("volatility")) for row in completed]
        ),
    )


def _walk_forward_ranges(rows: Sequence[Mapping[str, object]]) -> tuple[WalkForwardSplit, ...]:
    ranges = sorted(
        {
            (
                str(row.get("train_start") or ""),
                str(row.get("train_end") or ""),
                str(row.get("test_start") or ""),
                str(row.get("test_end") or ""),
            )
            for row in rows
            if row.get("kind") == "walk_forward" and row.get("status") == "complete"
        }
    )
    splits: list[WalkForwardSplit] = []
    for index, (train_start, train_end, test_start, test_end) in enumerate(ranges, start=1):
        if not train_start or not train_end or not test_start or not test_end:
            raise ValueError("walk-forward range is incomplete")
        training_dates = (train_start,) if train_start == train_end else (train_start, train_end)
        test_dates = (test_start,) if test_start == test_end else (test_start, test_end)
        splits.append(WalkForwardSplit(f"hosted-wf-{index:02d}", training_dates, test_dates))
    if not splits:
        raise ValueError("walk-forward OOS evidence is unavailable")
    return tuple(splits)


def _weights(candidate: Mapping[str, object]) -> tuple[float, ...]:
    raw = candidate.get("weights")
    if not isinstance(raw, list):
        raise ValueError("winner weights are unavailable")
    values: list[float] = []
    for row in raw:
        if not isinstance(row, dict):
            raise ValueError("winner weights are invalid")
        value = _optional_float(row.get("weight"))
        if value is None:
            raise ValueError("winner weights are invalid")
        values.append(value)
    return tuple(values)


def select_hosted_oos_winner(
    *,
    run_id: str,
    settings: Mapping[str, object],
    summary: Mapping[str, object],
    candidates: Sequence[Mapping[str, object]],
    validation: Sequence[Mapping[str, object]],
) -> HostedOOSSelection:
    """Select the published candidate only from persisted walk-forward OOS evidence."""

    raw_objective = settings.get("objective", DEFAULT_OBJECTIVE.value)
    objective = OptimizationObjective(str(raw_objective))
    walk_forward_rows = [row for row in validation if row.get("kind") == "walk_forward"]
    candidate_ids = sorted(
        {
            str(row.get("candidate_id"))
            for row in walk_forward_rows
            if isinstance(row.get("candidate_id"), str) and row.get("candidate_id")
        }
    )
    scores = tuple(
        _score(
            candidate_id,
            [row for row in walk_forward_rows if row.get("candidate_id") == candidate_id],
        )
        for candidate_id in candidate_ids
    )
    if not scores:
        raise ValueError("no OOS candidate evidence is available")

    from portfell.multivariate.orchestration.ranking import select_winner

    winner = select_winner(scores, objective)
    winner_rows = [row for row in candidates if row.get("candidate_id") == winner.configuration_id]
    if len(winner_rows) != 1:
        raise ValueError("OOS winner does not map to exactly one final-refit candidate")

    aligned = summary.get("aligned_period")
    if not isinstance(aligned, dict):
        raise ValueError("final-refit aligned period is unavailable")
    first_date = str(aligned.get("date_start") or "")
    last_date = str(aligned.get("date_end") or "")
    observation_count = int(aligned.get("observation_count") or 0)
    if not first_date or not last_date:
        raise ValueError("final-refit aligned range is unavailable")

    final_refit = FinalRefit(
        configuration_id=winner.configuration_id,
        first_date=first_date,
        last_date=last_date,
        observation_count=observation_count,
        weights=_weights(winner_rows[0]),
    )
    result = complete_run(
        run_id=run_id,
        objective=objective,
        splits=_walk_forward_ranges(walk_forward_rows),
        scores=scores,
        final_refit=final_refit,
    )
    return HostedOOSSelection(result=result, candidate_id=winner.configuration_id)

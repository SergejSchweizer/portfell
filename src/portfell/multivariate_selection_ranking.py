"""Configuration-keyed OOS scorecards for the Selection v2 migration.

This module is deliberately separate from the Decision service.  It creates
selection evidence only; production authority remains unchanged until PR471.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import median
from typing import Any

from portfell.contract_versioning import ContractVersion
from portfell.selection_v2_contract import SELECTION_V2_CONFIGURATIONS

RANKING_CONTRACT = ContractVersion("portfolio_selection_v2.ranking", 1)
OBJECTIVES = ("return_risk", "return_drawdown", "minimum_risk")


@dataclass(frozen=True)
class ConfigurationScorecard:
    configuration_id: str
    method: str
    spec_key: str
    completed_split_count: int
    required_split_count: int
    median_post_cost_return: float | None
    median_volatility: float | None
    median_sharpe_ratio: float | None
    median_return_drawdown_ratio: float | None
    median_turnover: float | None
    median_herfindahl_index: float | None
    availability_reasons: tuple[str, ...]
    warning_reasons: tuple[str, ...]

    @property
    def rankable(self) -> bool:
        return (
            self.completed_split_count >= self.required_split_count
            and not self.availability_reasons
        )

    def to_row(self) -> dict[str, Any]:
        return {
            "configuration_id": self.configuration_id,
            "method": self.method,
            "spec_key": self.spec_key,
            "completed_split_count": self.completed_split_count,
            "required_split_count": self.required_split_count,
            "median_post_cost_return": self.median_post_cost_return,
            "median_volatility": self.median_volatility,
            "median_sharpe_ratio": self.median_sharpe_ratio,
            "median_return_drawdown_ratio": self.median_return_drawdown_ratio,
            "median_turnover": self.median_turnover,
            "median_herfindahl_index": self.median_herfindahl_index,
            "availability_reasons": list(self.availability_reasons),
            "warning_reasons": list(self.warning_reasons),
            "rankable": self.rankable,
        }


def build_configuration_scorecards(
    *,
    validation_rows: Sequence[Mapping[str, Any]],
    scenario_rows: Sequence[Mapping[str, Any]] = (),
    expected_configuration_ids: Sequence[str] | None = None,
    required_split_count: int = 2,
) -> tuple[ConfigurationScorecard, ...]:
    """Aggregate measured rows by semantic configuration, never candidate ID."""
    expected = tuple(
        expected_configuration_ids
        or (item.configuration_id for item in SELECTION_V2_CONFIGURATIONS)
    )
    metadata = {
        item.configuration_id: (item.method, item.risk_model_spec.spec_key)
        for item in SELECTION_V2_CONFIGURATIONS
    }
    groups: dict[str, list[Mapping[str, Any]]] = {
        configuration_id: [] for configuration_id in expected
    }
    for row in validation_rows:
        configuration_id = str(
            row.get("candidate_configuration_id") or row.get("configuration_id") or ""
        )
        if configuration_id in groups:
            groups[configuration_id].append(row)
    scenario_groups: dict[str, list[Mapping[str, Any]]] = {
        configuration_id: [] for configuration_id in expected
    }
    for row in scenario_rows:
        configuration_id = str(
            row.get("candidate_configuration_id") or row.get("configuration_id") or ""
        )
        if configuration_id in scenario_groups:
            scenario_groups[configuration_id].append(row)
    cards: list[ConfigurationScorecard] = []
    for configuration_id in expected:
        rows = groups[configuration_id]
        method, spec_key = metadata.get(configuration_id, ("unavailable", ""))
        complete = [row for row in rows if row.get("status") == "complete"]
        reasons = {str(row["reason"]) for row in rows if row.get("reason")}
        if len({str(row.get("test_start", "")) for row in complete}) < required_split_count:
            reasons.add("incomplete_common_split_evidence")
        warnings = {
            str(row["reason"])
            for row in (*rows, *scenario_groups[configuration_id])
            if row.get("reason") == "cash_flow_evidence_only"
        }
        cards.append(
            ConfigurationScorecard(
                configuration_id=configuration_id,
                method=method,
                spec_key=spec_key,
                completed_split_count=len(complete),
                required_split_count=required_split_count,
                median_post_cost_return=_median_field(complete, "post_cost_return"),
                median_volatility=_median_field(complete, "volatility"),
                median_sharpe_ratio=_median_field(complete, "sharpe_ratio"),
                median_return_drawdown_ratio=_median_field(
                    complete, "same_split_return_drawdown_ratio"
                ),
                median_turnover=_median_field(complete, "turnover"),
                median_herfindahl_index=_median_field(complete, "herfindahl_index"),
                availability_reasons=tuple(sorted(reasons - warnings)),
                warning_reasons=tuple(sorted(warnings)),
            )
        )
    return tuple(cards)


def rank_configuration_scorecards(
    scorecards: Sequence[ConfigurationScorecard],
    *,
    objective: str,
) -> tuple[dict[str, Any], ...]:
    """Return deterministic ranking evidence without selecting a Decision."""
    if objective not in OBJECTIVES:
        raise ValueError("invalid_multivariate_objective")
    scored: list[tuple[float, float, float, str, ConfigurationScorecard]] = []
    for card in scorecards:
        if not card.rankable:
            continue
        primary = (
            card.median_sharpe_ratio
            if objective == "return_risk"
            else card.median_return_drawdown_ratio
            if objective == "return_drawdown"
            else None
        )
        if objective == "minimum_risk":
            primary = None if card.median_volatility is None else -card.median_volatility
        if primary is None:
            continue
        scored.append(
            (
                primary,
                card.median_turnover if card.median_turnover is not None else float("inf"),
                card.median_herfindahl_index
                if card.median_herfindahl_index is not None
                else float("inf"),
                card.configuration_id,
                card,
            )
        )
    ordered = sorted(scored, key=lambda item: (-item[0], item[1], item[2], item[3]))
    ranked: list[dict[str, object]] = []
    for rank, (primary, turnover, hhi, _, card) in enumerate(ordered, 1):
        ranked.append(
            {
                "rank": rank,
                "objective": objective,
                "objective_score": primary,
                "configuration_id": card.configuration_id,
                "method": card.method,
                "spec_key": card.spec_key,
                "completed_split_count": card.completed_split_count,
                "median_turnover": None if turnover == float("inf") else turnover,
                "median_herfindahl_index": None if hhi == float("inf") else hhi,
                "evidence_role": "selection",
                "contract_version": RANKING_CONTRACT.qualified_name,
            }
        )
    return tuple(ranked)


def _median_field(rows: Sequence[Mapping[str, Any]], field: str) -> float | None:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    return float(median(values)) if values else None


__all__ = [
    "ConfigurationScorecard",
    "OBJECTIVES",
    "RANKING_CONTRACT",
    "build_configuration_scorecards",
    "rank_configuration_scorecards",
]

from __future__ import annotations

from migration_evidence import config_ranking_evidence

from portfell.multivariate_selection_ranking import (
    build_configuration_scorecards,
    rank_configuration_scorecards,
)
from portfell.selection_v2_contract import SELECTION_V2_CONFIGURATIONS


def _rows(*, winner: str | None = None, warning: bool = False):
    rows = []
    for config in SELECTION_V2_CONFIGURATIONS:
        for split in range(2):
            score = 2.0 if config.configuration_id == winner else 0.5
            row = {
                "candidate_configuration_id": config.configuration_id,
                "test_start": f"2025-0{split + 1}-01",
                "status": "complete",
                "post_cost_return": score / 100,
                "volatility": 0.05 if config.configuration_id == winner else 0.2,
                "sharpe_ratio": score,
                "same_split_return_drawdown_ratio": score,
                "turnover": 0.1,
                "herfindahl_index": 0.2,
            }
            if warning:
                row["reason"] = "cash_flow_evidence_only"
            rows.append(row)
    return rows


def test_each_objective_uses_its_frozen_primary_metric() -> None:
    winner = SELECTION_V2_CONFIGURATIONS[4].configuration_id
    cards = build_configuration_scorecards(
        validation_rows=_rows(winner=winner), required_split_count=2
    )
    for objective in ("return_risk", "return_drawdown", "minimum_risk"):
        ranked = rank_configuration_scorecards(cards, objective=objective)
        assert ranked[0]["configuration_id"] == winner
        assert ranked[0]["evidence_role"] == "selection"


def test_missing_split_is_unrankable_and_warning_is_non_blocking() -> None:
    rows = _rows(warning=True)
    target = rows[0]["candidate_configuration_id"]
    rows = [
        row
        for row in rows
        if row["candidate_configuration_id"] != target or row["test_start"] == "2025-01-01"
    ]
    cards = build_configuration_scorecards(validation_rows=rows, required_split_count=2)
    card = next(item for item in cards if item.configuration_id == target)
    assert not card.rankable
    assert "incomplete_common_split_evidence" in card.availability_reasons
    assert card.warning_reasons == ("cash_flow_evidence_only",)


def test_stage_five_evidence_is_sanitized() -> None:
    cards = build_configuration_scorecards(validation_rows=_rows(), required_split_count=2)
    rankings = {
        objective: rank_configuration_scorecards(cards, objective=objective)
        for objective in ("return_risk", "return_drawdown", "minimum_risk")
    }
    evidence = config_ranking_evidence(
        sha="test-sha",
        rankings=rankings,
        focused_tests=["test_pr470_selection_v2_config_ranking_qa.py"],
    )
    assert evidence["stage"] == "config_ranking_ready"
    assert evidence["objectives_covered"] == ["minimum_risk", "return_drawdown", "return_risk"]
    assert evidence["full_sample_excluded"] and evidence["status"] == "PASS"

from __future__ import annotations

import pytest

from portfell.dash_ui.figures.multivariate_statistics.audit import decision_audit_figure
from portfell.dash_ui.figures.multivariate_statistics.candidates import candidate_return_risk_figure
from portfell.dash_ui.figures.multivariate_statistics.history import (
    final_refit_history_figure,
    reduction_history_figure,
    risk_model_history_figure,
    walk_forward_history_figure,
)
from portfell.dash_ui.figures.multivariate_statistics.models import (
    DecisionStageView,
    PersistedHistoryRangeView,
    PortfolioCandidatePoint,
    WalkForwardView,
)
from portfell.multivariate.contracts.common import DECISION_STAGE_ORDER


def test_pr288_candidate_figure_has_exact_title_all_objectives_and_winner_context() -> None:
    points = tuple(
        PortfolioCandidatePoint(
            configuration_id=f"cfg-{index}",
            annualized_oos_return=0.08 + index / 100,
            oos_annualized_volatility=0.12 + index / 100,
            objective_value=1.0 + index,
            winner=index == 1,
            method="minimum_variance",
            risk_model="sample",
            objective=objective,
        )
        for index, objective in enumerate(
            ("return_risk", "return_drawdown", "minimum_risk")
        )
    )
    forward = candidate_return_risk_figure(points)
    reverse = candidate_return_risk_figure(reversed(points))
    assert forward == reverse
    assert forward["layout"]["title"] == "Portfolio Candidate OOS Return / Risk"
    assert forward["layout"]["meta"]["objectives"] == [
        "minimum_risk",
        "return_drawdown",
        "return_risk",
    ]
    assert forward["layout"]["meta"]["winner_configuration_ids"] == ["cfg-1"]
    with pytest.raises(ValueError, match="unknown multivariate objective"):
        PortfolioCandidatePoint("bad", 0.1, 0.1, 1.0, False, "equal_weight", "sample", "other")


def test_pr288_decision_audit_always_renders_all_eight_stages_and_typed_missing() -> None:
    stage = DecisionStageView(
        stage="winner_selection",
        status="available",
        reason="objective_winner",
        selected_ids=("cfg-a",),
        rejected_count=2,
        metrics={},
    )
    figure = decision_audit_figure((stage,))
    trace = figure["data"][0]
    assert trace["y"] == [item.value for item in DECISION_STAGE_ORDER]
    assert len(trace["y"]) == 8
    winner_index = trace["y"].index("winner_selection")
    assert trace["customdata"][winner_index][0] == "available"
    unavailable = [
        row for index, row in enumerate(trace["customdata"]) if index != winner_index
    ]
    assert all(row[:2] == ["unavailable", "section_not_persisted"] for row in unavailable)


def test_pr288_persisted_history_figures_preserve_unavailable_without_zero() -> None:
    rows = (
        PersistedHistoryRangeView("sample", "2020-01-02", "2026-08-19", 1600),
        PersistedHistoryRangeView(
            "ewma", None, None, None, status="unavailable", reason="insufficient_history"
        ),
    )
    for factory, title in (
        (risk_model_history_figure, "Aligned Risk-Model History"),
        (reduction_history_figure, "Multivariate Reduction History"),
        (final_refit_history_figure, "Final Portfolio Refit History"),
    ):
        figure = factory(reversed(rows))
        assert figure["layout"]["title"] == title
        assert figure["data"][0]["y"] == [1600]
        assert figure["layout"]["meta"]["unavailable"] == [
            {
                "evidence_id": "ewma",
                "status": "unavailable",
                "reason": "insufficient_history",
            }
        ]


def test_pr288_walk_forward_coverage_is_deterministic() -> None:
    rows = tuple(
        WalkForwardView(
            split_id=f"wf-{index:02d}",
            training_first="2024-01-02",
            training_last=f"2024-0{index}-28",
            test_first=f"2024-0{index + 1}-01",
            test_last=f"2024-0{index + 1}-27",
            training_observations=100 + index * 21,
            test_observations=21,
        )
        for index in range(1, 6)
    )
    assert walk_forward_history_figure(rows) == walk_forward_history_figure(reversed(rows))
    assert walk_forward_history_figure(rows)["layout"]["title"] == (
        "Walk-Forward Training / Test Coverage"
    )

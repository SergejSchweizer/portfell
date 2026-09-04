from __future__ import annotations

import pytest

from portfell.dash_app.pages.multivariate import (
    _cumulative_extended_return_figure,
    build_page,
    multivariate_page_data,
    optimize_portfolio,
)


class Service:
    def workflow_state(self) -> dict[str, object]:
        return {
            "univariate_selection": {"selection_id": "selection-1", "member_count": 2},
            "stages": {
                "bivariate": {"run_id": "run-b", "status": "succeeded"},
                "multivariate": {"run_id": "run-m", "status": "succeeded"},
            },
        }

    def run_detail(self, run_id: str) -> dict[str, object]:
        assert run_id == "run-m"
        return {
            "run_id": run_id,
            "status": "succeeded",
            "input_snapshot_id": "market_source_snapshot_123456",
            "algorithm_version": "multivariate_execution.clean.v1",
            "decision": {
                "objective": "return_risk",
                "winning_candidate_id": "candidate-1",
                "requested_method": "minimum_variance",
                "actual_method": "minimum_variance",
                "available": True,
                "production_eligible": True,
                "reason": None,
                "document": {
                    "median_post_cost_return": 0.08,
                    "median_volatility": 0.12,
                    "ranking_basis": "walk_forward_out_of_sample_only",
                },
            },
            "artifacts": {
                "candidates": {
                    "items": [
                        {
                            "candidate_id": "candidate-1",
                            "method": "minimum_variance",
                            "max_drawdown": -0.14,
                            "weights": [
                                {"isin": "DE1", "exchange": "XETRA", "code": "AAA", "weight": 0.6},
                                {"isin": "DE2", "exchange": "XETRA", "code": "BBB", "weight": 0.4},
                            ],
                        }
                    ]
                },
                "validation": {
                    "items": [
                        {
                            "kind": "scorecard",
                            "candidate_id": "candidate-1",
                            "method": "minimum_variance",
                            "median_post_cost_return": 0.08,
                            "median_volatility": 0.12,
                        },
                        {
                            "kind": "walk_forward",
                            "candidate_id": "candidate-1",
                            "status": "complete",
                            "max_drawdown": -0.11,
                        },
                        {
                            "kind": "walk_forward",
                            "candidate_id": "candidate-1",
                            "status": "complete",
                            "max_drawdown": -0.18,
                        },
                    ]
                },
                "risk_contributions": {
                    "items": [
                        {
                            "candidate_id": "candidate-1",
                            "isin": "DE1",
                            "exchange": "XETRA",
                            "code": "AAA",
                            "percent_risk_contribution": 0.55,
                        },
                        {
                            "candidate_id": "candidate-1",
                            "isin": "DE2",
                            "exchange": "XETRA",
                            "code": "BBB",
                            "percent_risk_contribution": 0.45,
                        },
                    ]
                },
                "performance": {
                    "portfolio_series": [
                        {
                            "candidate_id": "candidate-1",
                            "method": "minimum_variance",
                            "values": [
                                {"date": "2026-01-31", "return": 0.01},
                                {"date": "2026-02-28", "return": 0.03},
                            ],
                        }
                    ]
                },
            },
        }

    def run_multivariate(
        self, *, selection_id: str, bivariate_run_id: str, objective: str = "return_risk"
    ) -> dict[str, object]:
        return {
            "run_id": "new-m",
            "selection_id": selection_id,
            "bivariate_run_id": bivariate_run_id,
            "objective": objective,
        }


def test_model_kpis_come_from_persisted_oos_and_decision_evidence() -> None:
    model = multivariate_page_data(Service())
    assert model["winner_id"] == "candidate-1"
    assert model["winner_oos_return"] == 0.08
    assert model["winner_oos_risk"] == 0.12
    assert model["winner_max_drawdown"] == -0.18
    assert model["production_eligibility"] is True
    assert model["ready"] is True


def test_optimize_accepts_only_frozen_objectives() -> None:
    service = Service()
    result = optimize_portfolio(
        service,
        selection_id="selection-1",
        bivariate_run_id="run-b",
        objective="return_drawdown",
    )
    assert result["objective"] == "return_drawdown"
    with pytest.raises(ValueError, match="invalid_multivariate_objective"):
        optimize_portfolio(
            service,
            selection_id="selection-1",
            bivariate_run_id="run-b",
            objective="equal_weight",
        )


def test_page_has_frozen_multivariate_contract_and_exact_weights() -> None:
    rendered = str(build_page(Service()).to_plotly_json())
    for text in (
        "Multivariate",
        "Optimize portfolio",
        "Winner OOS return",
        "Winner OOS risk",
        "Winner max drawdown",
        "Production eligibility",
        "Portfolio Candidate OOS Return / Risk",
        "Cumulative Performance",
        "Drawdown",
        "Allocation",
        "Risk Contribution",
        "Final Portfolio",
        "Decision",
        "Universe & History",
        "minimum_variance",
        "DE1",
        "AAA",
        "0.6",
    ):
        assert text in rendered
    assert "multivariate-objective" not in rendered


def test_cumulative_return_plot_uses_time_axis_and_no_isin_point_fallback() -> None:
    figure = _cumulative_extended_return_figure(
        None,
        ({"isin": "DE1", "cumulative_extended_return": 0.2},),
        {"DE1"},
    )
    assert figure.layout.xaxis.title.text == "Time"
    assert figure.layout.yaxis.title.text == "Cumulative extended return"
    assert not figure.data

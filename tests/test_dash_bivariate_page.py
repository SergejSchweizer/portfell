from __future__ import annotations

from portfell.dash_app.pages.bivariate import (
    _scatter,
    bivariate_page_data,
    build_page,
    compute_bivariate,
)


class Service:
    def workflow_state(self) -> dict[str, object]:
        return {
            "univariate_selection": {
                "selection_id": "selection-1",
                "version": 2,
                "member_count": 3,
            },
            "stages": {
                "bivariate": {
                    "run_id": "run-b",
                    "status": "succeeded",
                    "input_snapshot_id": "market_source_snapshot_xyz",
                    "algorithm_version": "bivariate.statistics.v1",
                }
            },
        }

    def run_detail(self, run_id: str) -> dict[str, object]:
        assert run_id == "run-b"
        return {
            "run_id": run_id,
            "status": "succeeded",
            "input_snapshot_id": "market_source_snapshot_xyz",
            "algorithm_version": "bivariate.statistics.v1",
            "artifacts": {
                "bivariate_rows": {
                    "items": [
                        {
                            "left_isin": "DE1",
                            "left_exchange": "XETRA",
                            "left_code": "AAA",
                            "right_isin": "DE2",
                            "right_exchange": "XETRA",
                            "right_code": "BBB",
                            "n_observations": 252,
                            "pearson_correlation": 0.25,
                            "spearman_correlation": 0.2,
                            "covariance": 0.003,
                            "downside_correlation": 0.35,
                            "lower_tail_dependence": 0.1,
                            "drawdown_overlap_rate": 0.3,
                        },
                        {
                            "left_isin": "DE1",
                            "left_exchange": "XETRA",
                            "left_code": "AAA",
                            "right_isin": "DE3",
                            "right_exchange": "XETRA",
                            "right_code": "CCC",
                            "n_observations": 252,
                            "pearson_correlation": -0.1,
                            "spearman_correlation": -0.08,
                            "covariance": -0.001,
                            "downside_correlation": 0.05,
                            "lower_tail_dependence": 0.02,
                            "drawdown_overlap_rate": 0.1,
                        },
                    ]
                }
            },
        }

    def run_bivariate(self, selection_id: str) -> dict[str, object]:
        return {"run_id": "new-b", "input_ref": selection_id, "status": "succeeded"}


def test_pair_counts_reconcile_from_persisted_selection() -> None:
    model = bivariate_page_data(Service())
    assert model["input_count"] == 3
    assert model["candidate_count"] == 3
    assert model["eligible_count"] == 2
    assert model["unavailable_count"] == 1
    assert model["ready"] is True


def test_compute_delegates_exact_selection_id() -> None:
    assert compute_bivariate(Service(), "selection-1") == {
        "run_id": "new-b",
        "input_ref": "selection-1",
        "status": "succeeded",
    }


def test_scatter_colors_pairs_by_lower_tail_dependence() -> None:
    figure = _scatter(
        (
            {
                "spearman_correlation": 0.7,
                "pearson_correlation": 0.8,
                "downside_correlation": 0.1,
                "lower_tail_dependence": 0.1,
                "tail_coexceedance_rate": 1.0,
            },
            {
                "spearman_correlation": 0.85,
                "pearson_correlation": 0.9,
                "downside_correlation": 0.9,
                "lower_tail_dependence": 0.9,
                "tail_coexceedance_rate": 0.0,
            },
        )
    ).to_plotly_json()
    marker = figure["data"][0]["marker"]
    assert figure["data"][0]["x"] == [0.7, 0.85]
    assert marker["color"] == [0.1, 0.9]
    assert marker["size"] == [8.0, 30.0]
    assert marker["sizemode"] == "diameter"
    assert marker["colorscale"][0][1] == "#dc2626"
    assert marker["colorscale"][-1][1] == "#6b7280"
    assert marker["colorbar"]["title"]["text"] == "Lower-tail dependence"
    assert figure["layout"]["xaxis"]["title"]["text"] == "Spearman correlation"
    assert figure["layout"]["yaxis"]["title"]["text"] == "Downside correlation"
    assert figure["layout"]["legend"]["title"]["text"] == "Marker size: co-exceedance rate"
    assert [trace["name"] for trace in figure["data"][1:]] == [
        "High rate — frequent joint extremes",
        "Medium rate",
        "Low rate — rare joint extremes",
    ]


def test_page_exposes_full_pair_identity_and_frozen_sections() -> None:
    rendered = str(build_page(Service()).to_plotly_json())
    for text in (
        "Bivariate",
        "Compute bivariate statistics",
        "Multivariate Selected ISINs",
        "Candidate pairs",
        "Eligible pairs",
        "Bivariate Return / Diversification Universe",
        "DE1",
        "XETRA",
        "AAA",
        "DE2",
        "BBB",
    ):
        assert text in rendered
    assert "Bivariate Statistics" not in rendered
    assert "Universe & History" not in rendered
    assert "Continue to Multivariate" not in rendered


def test_compute_button_stays_disabled_while_background_job_runs() -> None:
    class RunningService(Service):
        def workflow_state(self) -> dict[str, object]:
            state = super().workflow_state()
            state["active_job"] = {"status": "running"}
            return state

    rendered = str(build_page(RunningService()).to_plotly_json())
    assert "disabled=True" in rendered


def test_compute_button_stays_disabled_when_stage_is_running_after_reload() -> None:
    class StageRunningService(Service):
        def workflow_state(self) -> dict[str, object]:
            state = super().workflow_state()
            state.pop("active_job", None)
            state["stages"]["bivariate"]["status"] = "running"  # type: ignore[index]
            return state

    rendered = str(build_page(StageRunningService()).to_plotly_json())
    assert "disabled=True" in rendered

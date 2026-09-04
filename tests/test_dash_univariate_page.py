from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from portfell.dash_app.pages.univariate import (
    build_page,
    save_selection,
    univariate_page_data,
)


@dataclass(frozen=True)
class Selection:
    selection_id: str = "selection-1"


class Service:
    def workflow_state(self) -> dict[str, object]:
        return {
            "metadata_universe": {"universe_id": "universe-1", "version": 2, "member_count": 2},
            "univariate_selection": {
                "selection_id": "selection-1",
                "source_run_id": "run-u",
                "version": 4,
                "member_count": 1,
                "members": [{"isin": "DE1", "exchange": "XETRA", "code": "AAA"}],
            },
            "stages": {
                "univariate": {
                    "run_id": "run-u",
                    "status": "succeeded",
                    "input_snapshot_id": "market_source_snapshot_abc",
                    "algorithm_version": "univariate.statistics.v2",
                }
            },
        }

    def univariate_result_preview(self, run_id: str, *, limit: int = 500) -> dict[str, object]:
        assert run_id == "run-u"
        return {
            "run": {
                "run_id": run_id,
                "status": "succeeded",
                "input_snapshot_id": "market_source_snapshot_abc",
                "algorithm_version": "univariate.statistics.v2",
            },
            "item_count": 2,
            "summary": {"available_count": 1, "unavailable_count": 1},
            "rows": [
                {
                    "isin": "DE1",
                    "exchange": "XETRA",
                    "code": "AAA",
                    "annualized_return": 0.12,
                    "annualized_volatility": 0.2,
                    "max_drawdown": -0.1,
                    "sharpe_ratio": 0.6,
                    "sortino_ratio": 0.8,
                    "annual_dividend_yield": 0.03,
                    "availability_reason": "ok",
                },
                {
                    "isin": "DE2",
                    "exchange": "XETRA",
                    "code": "BBB",
                    "annualized_return": None,
                    "annualized_volatility": None,
                    "max_drawdown": None,
                    "sharpe_ratio": None,
                    "sortino_ratio": None,
                    "annual_dividend_yield": None,
                    "availability_reason": "insufficient_returns",
                },
            ],
        }

    def create_univariate_selection(
        self,
        run_id: str,
        *,
        predicates: Sequence[Mapping[str, object]] | None = None,
    ) -> Selection:
        assert run_id == "run-u"
        assert predicates is None
        return Selection()


def test_model_uses_persisted_run_and_selection() -> None:
    model = univariate_page_data(Service())
    assert model["input_count"] == 2
    assert model["available_count"] == 1
    assert model["unavailable_count"] == 1
    assert model["selected_count"] == 1
    assert model["selected"] == {"DE1:XETRA:AAA"}
    assert [row["isin"] for row in model["chart_rows"]] == ["DE1"]
    assert model["ready"] is True


def test_selection_action_delegates_to_application_service() -> None:
    service = Service()
    assert save_selection(service, "run-u") == Selection()


def test_page_stops_after_return_risk_plot() -> None:
    rendered = str(build_page(Service()).to_plotly_json())
    for text in (
        "Univariate",
        "Metadata Selected ISINs",
        "Univariate Selected ISINs",
        "Univariate Return / Risk Universe",
    ):
        assert text in rendered
    for text in (
        "Save selection",
        "Continue to Bivariate",
        "Univariate Statistics",
        "Universe & History",
    ):
        assert text not in rendered
    assert "Compute univariate statistics" not in rendered


def test_page_shows_dividend_frequency_window_after_plot() -> None:
    rendered = str(build_page(Service()).to_plotly_json())
    assert "Dividend Payments" in rendered
    assert "univariate-dividend-frequency-chart" in rendered
    assert "univariate-dividend-frequency-table" in rendered
    assert "None / unknown" in rendered
    assert "dividend-frequency:none / unknown" in rendered
    assert "ISIN Age" in rendered
    assert "univariate-isin-age-chart" in rendered
    assert "univariate-isin-age-table" in rendered
    assert "Monthly Returns" in rendered
    assert "univariate-monthly-return-chart" in rendered
    assert "univariate-monthly-return-table" in rendered


def test_page_excludes_results_outside_metadata_universe() -> None:
    class ScopedService(Service):
        def workflow_state(self) -> dict[str, object]:
            state = super().workflow_state()
            state["metadata_universe"] = {
                "universe_id": "universe-1",
                "version": 2,
                "member_count": 1,
                "members": [{"isin": "DE1", "exchange": "XETRA", "code": "AAA"}],
            }
            return state

    model = univariate_page_data(ScopedService())
    rows = model["rows"]
    assert len(rows) == 1
    assert rows[0]["isin"] == "DE1"
    assert model["input_count"] == 1


def test_page_uses_univariate_run_matching_active_metadata_universe() -> None:
    class LineageService(Service):
        def workflow_state(self) -> dict[str, object]:
            state = super().workflow_state()
            state["metadata_universe"] = {
                "universe_id": "universe-2",
                "version": 3,
                "member_count": 2,
                "members": [
                    {"isin": "DE1", "exchange": "XETRA", "code": "AAA"},
                    {"isin": "DE2", "exchange": "XETRA", "code": "BBB"},
                ],
            }
            state["stages"] = {
                "univariate": {
                    "run_id": "run-old",
                    "status": "succeeded",
                    "input_ref": "universe-1",
                }
            }
            state["history"] = {
                "univariate": [
                    {
                        "run_id": "run-u",
                        "status": "succeeded",
                        "input_ref": "universe-2",
                    },
                    {
                        "run_id": "run-old",
                        "status": "succeeded",
                        "input_ref": "universe-1",
                    },
                ]
            }
            return state

    model = univariate_page_data(LineageService())
    assert model["run"]["run_id"] == "run-u"


def test_page_does_not_show_old_run_for_new_metadata_universe() -> None:
    class PendingService(Service):
        def workflow_state(self) -> dict[str, object]:
            state = super().workflow_state()
            state["metadata_universe"] = {"universe_id": "universe-2", "member_count": 2}
            state["stages"]["univariate"]["input_ref"] = "universe-1"
            return state

    model = univariate_page_data(PendingService())
    assert model["run"] is None
    assert model["rows"] == ()


def test_page_limits_large_persisted_result_presentation() -> None:
    class LargeService(Service):
        def univariate_result_preview(self, run_id: str, *, limit: int = 500) -> dict[str, object]:
            result = super().univariate_result_preview(run_id, limit=limit)
            result["item_count"] = 501
            result["summary"] = {"available_count": 501, "unavailable_count": 0}
            result["rows"] = [
                {
                    "isin": f"DE{index:010d}",
                    "exchange": "XETRA",
                    "code": f"ETF{index}",
                    "annualized_return": 0.12,
                    "annualized_volatility": 0.2,
                    "max_drawdown": -0.1,
                    "sharpe_ratio": 0.6,
                    "sortino_ratio": 0.8,
                    "annual_dividend_yield": 0.03,
                    "availability_reason": "ok",
                }
                for index in range(501)
            ]
            return result

    model = univariate_page_data(LargeService())
    assert model["available_count"] == 501
    rendered = str(build_page(LargeService()).to_plotly_json())
    assert "Showing the first 100 of 501 persisted results." not in rendered

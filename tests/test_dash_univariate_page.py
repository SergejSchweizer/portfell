from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from portfell.dash_app.pages.univariate import (
    build_page,
    compute_univariate,
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

    def run_detail(self, run_id: str) -> dict[str, object]:
        assert run_id == "run-u"
        return {
            "run_id": run_id,
            "status": "succeeded",
            "input_snapshot_id": "market_source_snapshot_abc",
            "algorithm_version": "univariate.statistics.v2",
            "artifacts": {
                "univariate_rows": {
                    "items": [
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
                    ]
                }
            },
        }

    def run_univariate(self, universe_id: str) -> dict[str, object]:
        return {"run_id": "new-run", "input_ref": universe_id, "status": "succeeded"}

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
    assert model["ready"] is True


def test_actions_delegate_to_application_service() -> None:
    service = Service()
    assert compute_univariate(service, "universe-1")["run_id"] == "new-run"
    assert save_selection(service, "run-u") == Selection()


def test_page_has_frozen_chart_table_and_unavailable_evidence() -> None:
    rendered = str(build_page(Service()).to_plotly_json())
    for text in (
        "Univariate",
        "Compute univariate statistics",
        "Save selection",
        "Continue to Bivariate",
        "Input instruments",
        "Available results",
        "Selected instruments",
        "Unavailable results",
        "Univariate Return / Risk Universe",
        "Univariate Statistics",
        "Universe & History",
        "Showing all 2 persisted results.",
        "insufficient_returns",
        "DE1",
        "AAA",
    ):
        assert text in rendered


def test_page_limits_large_persisted_result_presentation() -> None:
    class LargeService(Service):
        def run_detail(self, run_id: str) -> dict[str, object]:
            result = super().run_detail(run_id)
            artifacts = cast(dict[str, object], result["artifacts"])
            artifact = cast(dict[str, object], artifacts["univariate_rows"])
            artifact["items"] = [
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
    assert "Showing the first 100 of 501 persisted results." in rendered
    assert "DE0000000000" in rendered
    assert "DE0000000500" not in rendered

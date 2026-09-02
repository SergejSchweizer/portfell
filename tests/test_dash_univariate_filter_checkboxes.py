from __future__ import annotations

import pytest

from portfell.dash_app.callbacks import univariate_checkbox_predicates
from portfell.dash_app.pages.univariate import univariate_page_data
from portfell.dash_app.state import browser_state_from_workflow

DIVIDEND_CASES = (
    ("none / unknown", "distribution_frequency", ["none", "unknown"]),
    ("monthly", "distribution_frequency", ["monthly"]),
    ("quarterly", "distribution_frequency", ["quarterly"]),
    ("semi-annual", "distribution_frequency", ["semi-annual"]),
    ("annual", "distribution_frequency", ["annual"]),
    ("irregular", "distribution_frequency", ["irregular"]),
)
AGE_CASES = (
    "le3_months",
    "gt3-6_months",
    "gt6_months-1_year",
    "gt1-2_years",
    "gt2-3_years",
    "gt3-4_years",
    "gt4-5_years",
    "gt5_years",
)


@pytest.mark.parametrize("category, metric, allowed", DIVIDEND_CASES)
def test_each_dividend_checkbox_can_be_activated_and_deactivated(
    category: str, metric: str, allowed: list[str]
) -> None:
    ids = [{"category": category}]
    active = univariate_checkbox_predicates([[category]], ids, [], [])
    assert active == [{"metric": metric, "operator": "in", "allowed": allowed}]
    # Removing the last check means no filter, rather than an empty selection.
    assert univariate_checkbox_predicates([[]], ids, [], []) == []


@pytest.mark.parametrize("category", AGE_CASES)
def test_each_age_checkbox_can_be_activated_and_deactivated(category: str) -> None:
    ids = [{"category": category}]
    active = univariate_checkbox_predicates([], [], [[category]], ids)
    assert active == [{"metric": "history_age_group", "operator": "in", "allowed": [category]}]
    assert univariate_checkbox_predicates([], [], [[]], ids) == []


def test_checkbox_parser_accepts_dash_wildcard_value_records() -> None:
    assert univariate_checkbox_predicates(
        [{"value": ["monthly"]}],
        [{"category": "monthly"}],
        [],
        [],
    ) == [
        {
            "metric": "distribution_frequency",
            "operator": "in",
            "allowed": ["monthly"],
        }
    ]


@pytest.mark.parametrize(
    "category",
    [
        "le_minus10_pct",
        "gt_minus10_to_0_pct",
        "gt_0_to_2_pct",
        "gt_2_to_5_pct",
        "gt_5_to_10_pct",
        "gt_10_pct",
        "unknown",
    ],
)
def test_each_monthly_return_checkbox_can_be_activated_and_deactivated(category: str) -> None:
    ids = [{"category": category}]
    assert univariate_checkbox_predicates([], [], [], [], [[category]], ids) == [
        {"metric": "monthly_return_group", "operator": "in", "allowed": [category]}
    ]
    assert univariate_checkbox_predicates([], [], [], [], [[]], ids) == []


def test_checkbox_selection_count_is_identical_in_page_and_sidebar() -> None:
    members = [
        {"isin": "A", "exchange": "XETRA", "code": "A"},
        {"isin": "B", "exchange": "XETRA", "code": "B"},
        {"isin": "C", "exchange": "XETRA", "code": "C"},
    ]

    class Service:
        def workflow_state(self) -> dict[str, object]:
            return {
                "metadata_universe": {"member_count": 3, "members": members},
                "univariate_selection": {
                    "selection_id": "selection",
                    "member_count": 1,
                    "members": members[:1],
                },
                "stages": {"univariate": {"run_id": "run", "status": "succeeded"}},
            }

        def univariate_result_preview(self, run_id: str, *, limit: int = 500) -> dict[str, object]:
            assert run_id == "run"
            return {
                "run": {"run_id": run_id, "status": "succeeded"},
                "item_count": 3,
                "summary": {"available_count": 3, "unavailable_count": 0},
                "rows": [
                    {
                        **member,
                        "availability_reason": "ok",
                        "annualized_return": 0.1,
                        "annualized_volatility": 0.2,
                    }
                    for member in members
                ],
            }

    service = Service()
    page_model = univariate_page_data(service)
    sidebar_state = browser_state_from_workflow(service.workflow_state())
    assert page_model["selected_count"] == 1
    assert sidebar_state.selected_count == page_model["selected_count"]

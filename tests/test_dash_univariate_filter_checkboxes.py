from __future__ import annotations

import pytest

from portfell.app_services.analysis_compute import (
    ComputedRun,
    filtered_univariate_selection,
    full_univariate_selection,
)
from portfell.dash_app.callbacks import _filter_trigger_is_mounted, univariate_checkbox_predicates
from portfell.dash_app.pages.univariate import build_page, univariate_page_data
from portfell.dash_app.shell import workflow_context_from_state
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


def test_filter_callback_ignores_dynamic_component_removal() -> None:
    ids = [{"type": "univariate-age-group", "category": "gt5_years"}]
    assert _filter_trigger_is_mounted(ids[0], ids) is True
    assert _filter_trigger_is_mounted(ids[0], []) is False
    assert _filter_trigger_is_mounted(None, ids) is False


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
                    "source_run_id": "run",
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


def test_metadata_selection_is_input_and_empty_univariate_selection_is_zero() -> None:
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
                    "selection_id": "empty",
                    "source_run_id": "run",
                    "member_count": 0,
                    "members": [],
                },
                "stages": {"univariate": {"run_id": "run", "status": "succeeded"}},
            }

        def univariate_result_preview(self, run_id: str, *, limit: int = 500) -> dict[str, object]:
            return {"run": {"run_id": run_id}, "item_count": 3, "rows": []}

    model = univariate_page_data(Service())
    assert model["input_count"] == 3
    assert model["selected_count"] == 0
    assert model["chart_rows"] == ()


@pytest.mark.parametrize(
    ("category", "field", "value"),
    [
        ("monthly", "distribution_frequency", "monthly"),
        ("quarterly", "distribution_frequency", "quarterly"),
        ("gt3-4_years", "history_age_group", "gt3-4_years"),
        ("gt5_years", "history_age_group", "gt5_years"),
        ("gt_0_to_2_pct", "monthly_return_group", "gt_0_to_2_pct"),
        ("gt_10_pct", "monthly_return_group", "gt_10_pct"),
    ],
)
def test_checkbox_filter_count_matches_page_and_sidebar(
    category: str, field: str, value: str
) -> None:
    rows = tuple(
        {
            "isin": f"I{index}",
            "exchange": "XETRA",
            "code": f"C{index}",
            "availability_reason": "ok",
            "distribution_frequency": "monthly" if index < 2 else "quarterly",
            "history_years": 3.5 if index < 2 else 6.0,
            "monthly_simple_return": 0.01 if index < 2 else 0.11,
            "return_observation_count": 12,
        }
        for index in range(4)
    )
    run = ComputedRun("run", "source", "test", rows)
    predicates = univariate_checkbox_predicates(
        [[category]] if field == "distribution_frequency" else [],
        [{"category": category}] if field == "distribution_frequency" else [],
        [[category]] if field == "history_age_group" else [],
        [{"category": category}] if field == "history_age_group" else [],
        [[category]] if field == "monthly_return_group" else [],
        [{"category": category}] if field == "monthly_return_group" else [],
    )
    selected = filtered_univariate_selection(run, predicates)
    assert len(selected.member_ids) == 2
    assert len(set(selected.member_ids)) == len(selected.member_ids)
    # Clearing the same checkbox removes the predicate and restores all rows.
    assert len(full_univariate_selection(run).member_ids) == 4


@pytest.mark.parametrize(
    ("active_groups", "expected_count"),
    [
        (("dividend",), 2),
        (("age",), 2),
        (("monthly",), 2),
        (("dividend", "age"), 1),
        (("dividend", "monthly"), 1),
        (("age", "monthly"), 2),
        (("dividend", "age", "monthly"), 1),
    ],
)
def test_checkbox_groups_are_intersected_for_every_combination(
    active_groups: tuple[str, ...], expected_count: int
) -> None:
    rows = tuple(
        {
            "isin": f"I{index}",
            "exchange": "XETRA",
            "code": f"C{index}",
            "distribution_frequency": "monthly" if index < 2 else "quarterly",
            "history_years": 3.5 if index in {0, 2} else 6.0,
            "monthly_simple_return": 0.01 if index in {0, 2} else 0.11,
            "availability_reason": "ok",
        }
        for index in range(4)
    )
    predicates: list[dict[str, object]] = []
    if "dividend" in active_groups:
        predicates.append(
            {"metric": "distribution_frequency", "operator": "in", "allowed": ["monthly"]}
        )
    if "age" in active_groups:
        predicates.append(
            {"metric": "history_age_group", "operator": "in", "allowed": ["gt3-4_years"]}
        )
    if "monthly" in active_groups:
        predicates.append(
            {"metric": "monthly_return_group", "operator": "in", "allowed": ["gt_0_to_2_pct"]}
        )
    selection = filtered_univariate_selection(
        ComputedRun("run", "source", "test", rows), predicates
    )
    assert len(selection.member_ids) == expected_count


@pytest.mark.parametrize(
    ("group", "category", "expected"),
    [("dividend", category, 2) for category, _, _ in DIVIDEND_CASES]
    + [("age", category, 2) for category in AGE_CASES]
    + [
        ("monthly", category, 2)
        for category in (
            "le_minus10_pct",
            "gt_minus10_to_0_pct",
            "gt_0_to_2_pct",
            "gt_2_to_5_pct",
            "gt_5_to_10_pct",
            "gt_10_pct",
            "unknown",
        )
    ],
)
def test_every_checkbox_category_has_exact_page_and_sidebar_count(
    group: str, category: str, expected: int
) -> None:
    """The merge gate verifies each category's persisted count projection.

    Every category is represented by two unique ISINs.  This deliberately
    exercises the callback predicate, durable-selection projection, page KPI,
    and sidebar workflow context together instead of only checking predicate
    syntax.
    """
    age_values = {
        "le3_months": 0.1,
        "gt3-6_months": 0.3,
        "gt6_months-1_year": 0.75,
        "gt1-2_years": 1.5,
        "gt2-3_years": 2.5,
        "gt3-4_years": 3.5,
        "gt4-5_years": 4.5,
        "gt5_years": 6.0,
    }
    monthly_values = {
        "le_minus10_pct": -0.2,
        "gt_minus10_to_0_pct": -0.05,
        "gt_0_to_2_pct": 0.01,
        "gt_2_to_5_pct": 0.03,
        "gt_5_to_10_pct": 0.07,
        "gt_10_pct": 0.11,
        "unknown": None,
    }
    rows: list[dict[str, object]] = []
    categories = {
        "dividend": [item[0] for item in DIVIDEND_CASES],
        "age": list(AGE_CASES),
        "monthly": list(monthly_values),
    }
    for row_category in categories[group]:
        for copy in range(2):
            row: dict[str, object] = {
                "isin": f"{group}-{row_category}-{copy}",
                "exchange": "XETRA",
                "code": f"C-{group}-{copy}",
                "availability_reason": "ok",
                "distribution_frequency": (
                    "none" if row_category == "none / unknown" else row_category
                ),
                "history_years": age_values.get(row_category),
                "monthly_simple_return": monthly_values.get(row_category),
                "annualized_return": 0.1,
                "annualized_volatility": 0.2,
            }
            rows.append(row)
    run = ComputedRun("run", "source", "test", tuple(rows))
    if group == "dividend":
        predicates = univariate_checkbox_predicates(
            [[category]], [{"category": category}], [], [], [], []
        )
    elif group == "age":
        predicates = univariate_checkbox_predicates(
            [], [], [[category]], [{"category": category}], [], []
        )
    else:
        predicates = univariate_checkbox_predicates(
            [], [], [], [], [[category]], [{"category": category}]
        )
    selection = filtered_univariate_selection(run, predicates)
    assert len(selection.member_ids) == expected

    class Service:
        def workflow_state(self) -> dict[str, object]:
            members = [{key: row[key] for key in ("isin", "exchange", "code")} for row in rows]
            selected_members = [
                {key: row[key] for key in ("isin", "exchange", "code")}
                for row in rows
                if f"{row['isin']}:{row['exchange']}:{row['code']}" in selection.member_ids
            ]
            return {
                "metadata_universe": {
                    "universe_id": "universe",
                    "member_count": len(members),
                    "members": members,
                },
                "univariate_selection": {
                    "selection_id": selection.selection_id,
                    "source_run_id": "run",
                    "member_count": len(selected_members),
                    "members": selected_members,
                },
                "stages": {
                    "univariate": {
                        "run_id": "run",
                        "status": "succeeded",
                        "input_ref": "universe",
                    }
                },
            }

        def univariate_result_preview(self, run_id: str, *, limit: int = 500) -> dict[str, object]:
            return {
                "run": {"run_id": run_id, "status": "succeeded"},
                "item_count": len(rows),
                "summary": {"available_count": len(rows), "unavailable_count": 0},
                "rows": rows,
            }

    service = Service()
    model = univariate_page_data(service)
    state = browser_state_from_workflow(service.workflow_state())
    context = workflow_context_from_state(state, "/univariate")
    context_counts = dict(context.project_metadata)
    rendered = str(build_page(service).to_plotly_json())
    assert model["selected_count"] == expected
    assert context_counts["Univariate"] == str(expected)
    assert "Univariate Selected ISINs" in rendered
    assert f"{expected}" in rendered

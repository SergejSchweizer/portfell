from __future__ import annotations

from math import exp

from migration_evidence import common_oos_evidence
from test_pr463_selection_v2_split_risk_models import _fixture

from portfell.multivariate_risk_model_comparison import (
    build_common_oos_validation,
    build_split_candidate_families,
    build_split_risk_model_bundles,
)


def _validated():
    snapshot, rows = _fixture()
    bundles = build_split_risk_model_bundles(snapshot=snapshot, return_rows=rows)
    families = build_split_candidate_families(
        snapshot=snapshot, return_rows=rows, income={}, bundles=bundles
    )
    return rows, families, build_common_oos_validation(return_rows=rows, families=families)


def test_independent_first_split_return_and_turnover_oracle() -> None:
    rows, families, validation = _validated()
    first = families[0]
    equal_weight = first.candidates[0]
    test_dates = sorted(
        {str(row["date"]) for row in rows if first.test_start <= str(row["date"]) <= first.test_end}
    )
    by_date = {day: [] for day in test_dates}
    weights = dict(equal_weight.weights)
    for row in rows:
        if str(row["date"]) in by_date:
            key = next(
                item
                for item in weights
                if item.as_tuple() == (row["isin"], row["exchange"], row["code"])
            )
            by_date[str(row["date"])].append(weights[key] * (exp(float(row["return"])) - 1.0))
    portfolio_returns = [sum(values) for _, values in sorted(by_date.items())]
    expected_pre_cost = 1.0
    for value in portfolio_returns:
        expected_pre_cost *= 1.0 + value
    expected_pre_cost -= 1.0
    result = next(
        item
        for item in validation
        if item.candidate_configuration_id == equal_weight.candidate_configuration_id
        and item.test_start == first.test_start
    )
    assert abs(result.pre_cost_return - expected_pre_cost) < 1e-12
    assert result.turnover == 1.0
    assert abs(result.transaction_cost - 0.0005) < 1e-15
    assert abs(result.post_cost_return - (expected_pre_cost - 0.0005)) < 1e-12
    assert result.test_observation_count == len(test_dates) == 21


def test_future_rows_cannot_change_prior_oos_split() -> None:
    rows, families, baseline = _validated()
    first_end = families[0].test_end
    mutated = [
        dict(row, **{"return": float(row["return"]) + 20.0})
        if str(row["date"]) > first_end
        else row
        for row in rows
    ]
    changed = build_common_oos_validation(return_rows=mutated, families=families)
    first_base = [item for item in baseline if item.test_start == families[0].test_start]
    first_changed = [item for item in changed if item.test_start == families[0].test_start]
    assert [
        (item.candidate_configuration_id, item.pre_cost_return, item.post_cost_return)
        for item in first_base
    ] == [
        (item.candidate_configuration_id, item.pre_cost_return, item.post_cost_return)
        for item in first_changed
    ]


def test_stage_four_evidence_is_sanitized_and_complete() -> None:
    _, _, validation = _validated()
    rows = [
        {
            "test_start": item.test_start,
            "train_start": item.train_start,
            "train_end": item.train_end,
            "test_end": item.test_end,
            "candidate_configuration_id": item.candidate_configuration_id,
            "candidate_id": item.candidate_id,
            "risk_model_id": item.risk_model_id,
            "fit_calendar_id": item.fit_calendar_id,
            "status": item.status,
        }
        for item in validation
    ]
    evidence = common_oos_evidence(
        sha="test-sha",
        validation_rows=rows,
        focused_tests=["test_pr468_selection_v2_common_oos_validation_qa.py"],
    )
    assert evidence["stage"] == "common_oos_measured"
    assert evidence["configuration_count"] == 14
    assert evidence["measured_rows"] == 42
    assert evidence["all_rows_have_boundaries"] and evidence["lineage_persisted"]
    assert evidence["status"] == "PASS"

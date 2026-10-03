from __future__ import annotations

from migration_evidence import split_risk_models_evidence
from test_pr463_selection_v2_split_risk_models import _fixture

import portfell.multivariate_risk_model_comparison as comparison
from portfell.multivariate_risk_model_comparison import build_split_risk_model_bundles


def _independent_ewma(rows, keys, decay=0.94):
    dates = sorted({str(row["date"]) for row in rows})
    values = {
        key: {
            str(row["date"]): float(row["return"])
            for row in rows
            if (row["isin"], row["exchange"], row["code"]) == key.as_tuple()
        }
        for key in keys
    }
    matrix = [[values[key][day] for key in keys] for day in dates]
    means = [sum(row[i] for row in matrix) / len(matrix) for i in range(len(keys))]
    centered = [[value - means[i] for i, value in enumerate(row)] for row in matrix]
    result = [[centered[0][i] * centered[0][j] for j in range(len(keys))] for i in range(len(keys))]
    for row in centered[1:]:
        for i in range(len(keys)):
            for j in range(len(keys)):
                result[i][j] = decay * result[i][j] + (1 - decay) * row[i] * row[j]
    return result


def test_independent_ewma_oracle_and_rolling_calendar() -> None:
    snapshot, rows = _fixture()
    bundles = build_split_risk_model_bundles(snapshot=snapshot, return_rows=rows, starts=(100, 252))
    bundle = bundles[0]
    ewma = bundle.model("EWMA_094")
    expected = _independent_ewma(
        [row for row in rows if row["date"] <= bundle.train_end], snapshot.listing_keys
    )
    for actual_row, expected_row in zip(ewma.covariance, expected, strict=True):
        for actual, expected_value in zip(actual_row, expected_row, strict=True):
            assert abs(actual - expected_value) < 1e-15
    later_bundle = next(item for item in bundles if item.model("LW_ROLLING_252").available)
    later = later_bundle.model("LW_ROLLING_252")
    assert later.observation_count == 252
    assert later.date_end == later_bundle.train_end
    assert later.date_end < later_bundle.test_start


def test_fit_call_count_is_three_per_split(monkeypatch) -> None:
    snapshot, rows = _fixture()
    original = comparison.build_multivariate_risk_model
    calls = []

    def counted(**kwargs):
        calls.append(kwargs["spec"].spec_key)
        return original(**kwargs)

    monkeypatch.setattr(comparison, "build_multivariate_risk_model", counted)
    bundles = build_split_risk_model_bundles(snapshot=snapshot, return_rows=rows)
    assert len(calls) == len(bundles) * 3
    assert all(
        calls[index : index + 3] == ["LW_FULL", "LW_ROLLING_252", "EWMA_094"]
        for index in range(0, len(calls), 3)
    )


def test_stage_two_evidence_is_sanitized_and_complete() -> None:
    snapshot, rows = _fixture()
    bundles = build_split_risk_model_bundles(snapshot=snapshot, return_rows=rows, starts=(100, 252))
    evidence = split_risk_models_evidence(
        sha="test-sha",
        bundles=[row for bundle in bundles for row in bundle.to_rows()],
        focused_tests=["test_pr463_selection_v2_split_risk_models.py"],
    )
    assert evidence["stage"] == "split_risk_models_complete"
    assert evidence["max_fits_per_split"] == 3
    assert evidence["all_fit_calendars_persisted"]
    assert evidence["unavailable_fits_retained"]
    assert evidence["status"] == "PASS"

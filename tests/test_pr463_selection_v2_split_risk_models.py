from __future__ import annotations

from datetime import date, timedelta

from portfell.multivariate_inputs import (
    MultivariateInputDependencies,
    MultivariateListingKey,
    build_multivariate_input_snapshot,
)
from portfell.multivariate_risk_model_comparison import (
    COMPARISON_SPECS,
    build_split_risk_model_bundles,
)


def _fixture(rows_count: int = 320):
    keys = tuple(
        MultivariateListingKey(chr(65 + index), "X", chr(65 + index)) for index in range(6)
    )
    dependencies = MultivariateInputDependencies(
        project_id="p",
        project_snapshot_id="s",
        metadata_selection_id="m",
        univariate_run_id="u",
        univariate_selection_id="us",
        bivariate_run_id="b",
        bivariate_status="complete",
        bivariate_listing_keys=keys,
        aligned_calendar_id="c",
        bivariate_aligned_calendar_id="c",
        date_start="2024-01-01",
        date_end="2025-12-31",
        observation_count=rows_count,
        quote_artifact_ids={key: "q" for key in keys},
        dividend_artifact_ids={key: "d" for key in keys},
    )
    metadata = [
        {
            "isin": key.isin,
            "exchange": key.exchange,
            "code": key.code,
            "instrument_type": "ETF",
            "distribution_frequency": "monthly",
        }
        for key in keys
    ]
    snapshot = build_multivariate_input_snapshot(
        dependencies=dependencies, univariate_rows=metadata
    )
    rows = []
    first = date(2024, 1, 1)
    for index in range(rows_count):
        current = (first + timedelta(days=index)).isoformat()
        for key, value in zip(keys, (0.001, 0.002, 0.003, 0.0015, 0.0025, 0.0035), strict=True):
            rows.append(
                {
                    "isin": key.isin,
                    "exchange": key.exchange,
                    "code": key.code,
                    "date": current,
                    "return": value + index * 0.000001,
                }
            )
    return snapshot, rows


def test_split_bundles_fit_three_specs_once_and_persist_identity() -> None:
    snapshot, rows = _fixture()
    bundles = build_split_risk_model_bundles(snapshot=snapshot, return_rows=rows)
    assert bundles
    assert all(
        tuple(key for key, _ in bundle.models) == tuple(spec.spec_key for spec in COMPARISON_SPECS)
        for bundle in bundles
    )
    assert all(len(bundle.to_rows()) == 3 for bundle in bundles)
    assert all(
        row["split_index"] == bundles[row["split_index"]].split_index
        for bundle in bundles
        for row in bundle.to_rows()
    )
    assert all(
        row["spec_id"] and row["risk_model_id"] and row["fit_calendar_id"]
        for bundle in bundles
        for row in bundle.to_rows()
    )
    rolling = [bundle.model("LW_ROLLING_252") for bundle in bundles]
    assert any(model.available and model.observation_count == 252 for model in rolling)


def test_split_fit_is_training_only_and_future_mutation_invariant() -> None:
    snapshot, rows = _fixture()
    bundles = build_split_risk_model_bundles(snapshot=snapshot, return_rows=rows)
    first = bundles[0]
    assert first.train_end is not None and first.test_start is not None
    future_rows = [
        dict(row, **{"return": float(row["return"]) + 10.0})
        for row in rows
        if row["date"] >= first.test_start
    ]
    mutated = [row for row in rows if row["date"] < first.test_start] + future_rows
    changed = build_split_risk_model_bundles(snapshot=snapshot, return_rows=mutated)[0]
    assert tuple(
        (key, model.risk_model_id, model.fit_calendar_id, model.observation_count)
        for key, model in first.models
    ) == tuple(
        (key, model.risk_model_id, model.fit_calendar_id, model.observation_count)
        for key, model in changed.models
    )

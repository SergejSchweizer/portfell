from portfell.multivariate_inputs import (
    MultivariateInputDependencies,
    MultivariateListingKey,
    build_multivariate_input_snapshot,
)
from portfell.multivariate_risk_model_comparison import build_risk_model_comparison


def _data():
    keys = (MultivariateListingKey("A", "X", "A"), MultivariateListingKey("B", "X", "B"))
    deps = MultivariateInputDependencies(
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
        observation_count=504,
        quote_artifact_ids={key: "q" for key in keys},
        dividend_artifact_ids={key: "d" for key in keys},
    )
    rows = [
        {
            "isin": key.isin,
            "exchange": key.exchange,
            "code": key.code,
            "instrument_type": "ETF",
            "distribution_frequency": "monthly",
        }
        for key in keys
    ]
    returns = [
        {
            "isin": key.isin,
            "exchange": key.exchange,
            "code": key.code,
            "date": f"2024-01-0{day}",
            "return": value,
        }
        for key, value in ((keys[0], 0.01), (keys[1], 0.02))
        for day in range(1, 4)
    ]
    return build_multivariate_input_snapshot(dependencies=deps, univariate_rows=rows), returns


def test_comparison_manifest_contains_exactly_fourteen_configurations() -> None:
    snapshot, returns = _data()
    result = build_risk_model_comparison(snapshot=snapshot, return_rows=returns, income={})
    assert result["configuration_count"] == 14
    assert len(result["configurations"]) == 14
    assert len(result["full_sample_evidence"]) == 14
    assert {item["spec_key"] for item in result["configurations"]} == {
        "LW_FULL",
        "LW_ROLLING_252",
        "EWMA_094",
    }

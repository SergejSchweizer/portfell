from portfell.multivariate_candidates import (
    METHODS,
    MonthlyDistributionEtfPortfolioPolicy,
    build_candidate_set,
)
from portfell.multivariate_inputs import (
    MultivariateInputDependencies,
    MultivariateListingKey,
    build_multivariate_input_snapshot,
)
from portfell.multivariate_risk_model import (
    RISK_MODEL_ARTIFACT_CONTRACT,
    MultivariateRiskModelArtifact,
)


def _keys() -> tuple[MultivariateListingKey, ...]:
    return tuple(MultivariateListingKey(f"IE{index}", "X", f"ETF{index}") for index in range(5))


def _snapshot():  # type: ignore[no-untyped-def]
    keys = _keys()
    dependencies = MultivariateInputDependencies(
        project_id="project-a",
        project_snapshot_id="snapshot-a",
        metadata_selection_id="metadata-a",
        univariate_run_id="univariate-a",
        univariate_selection_id="selection-a",
        bivariate_run_id="bivariate-a",
        bivariate_status="complete",
        bivariate_listing_keys=keys,
        aligned_calendar_id="calendar-a",
        bivariate_aligned_calendar_id="calendar-a",
        date_start="2024-01-01",
        date_end="2025-12-31",
        observation_count=504,
        quote_artifact_ids={key: f"q{index}" for index, key in enumerate(keys)},
        dividend_artifact_ids={key: f"d{index}" for index, key in enumerate(keys)},
    )
    return build_multivariate_input_snapshot(
        dependencies=dependencies,
        univariate_rows=[
            {
                "isin": key.isin,
                "exchange": key.exchange,
                "code": key.code,
                "instrument_type": "ETF",
                "distribution_frequency": "monthly",
            }
            for key in keys
        ],
    )


def _risk_model() -> MultivariateRiskModelArtifact:
    keys = _keys()
    return MultivariateRiskModelArtifact(
        risk_model_id="risk-a",
        input_snapshot_id="snapshot-a",
        contract_version=RISK_MODEL_ARTIFACT_CONTRACT,
        estimator="ledoit_wolf",
        return_type="log",
        window_policy="full",
        estimator_parameters=(),
        listings=keys,
        aligned_calendar_id="calendar-a",
        date_start="2024-01-01",
        date_end="2025-12-31",
        observation_count=504,
        covariance=tuple(
            tuple(0.01 if left == right else 0.001 for right in range(5)) for left in range(5)
        ),
        shrinkage_intensity=0.1,
        minimum_eigenvalue=0.009,
        condition_number=2.0,
        is_positive_semidefinite=True,
        availability_reasons=(),
        algorithm_version=1,
    )


def _returns() -> list[dict[str, object]]:
    return [
        {
            "isin": key.isin,
            "exchange": key.exchange,
            "code": key.code,
            "date": f"2025-01-{day:02d}",
            "return": 0.001 * (index + 1) * (-1 if day % 2 else 1),
        }
        for index, key in enumerate(_keys())
        for day in range(1, 25)
    ]


def test_candidate_set_has_six_stable_methods_and_no_silent_fallbacks() -> None:
    candidates = build_candidate_set(
        snapshot=_snapshot(), risk_model=_risk_model(), return_rows=_returns(), income={}
    )
    assert tuple(candidate.method for candidate in candidates) == METHODS
    assert candidates[0].baseline and candidates[1].baseline
    assert all(candidate.status in {"feasible", "unavailable"} for candidate in candidates)
    for candidate in candidates:
        if candidate.status == "feasible":
            assert abs(sum(weight for _, weight in candidate.weights) - 1) < 1e-9
            assert all(0 <= weight <= 0.2 for _, weight in candidate.weights)


def test_infeasible_bounds_remain_explicit_for_every_candidate() -> None:
    candidates = build_candidate_set(
        snapshot=_snapshot(),
        risk_model=_risk_model(),
        return_rows=_returns(),
        income={},
        policy=MonthlyDistributionEtfPortfolioPolicy(max_weight=0.19),
    )
    assert all(candidate.status == "unavailable" for candidate in candidates)
    assert {candidate.reasons for candidate in candidates} == {("infeasible_weight_bounds",)}

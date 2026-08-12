from portfell.multivariate_inputs import (
    MultivariateInputDependencies,
    MultivariateListingKey,
    build_multivariate_input_snapshot,
)
from portfell.multivariate_risk_model import (
    _risk_model_identity,  # pyright: ignore[reportPrivateUsage]
    build_multivariate_risk_model,
)


def _key(number: int) -> MultivariateListingKey:
    return MultivariateListingKey(f"IE{number}", "XETRA", f"ETF{number}")


def _dependencies(
    *, observations: int, project_snapshot_id: str = "snapshot-a"
) -> MultivariateInputDependencies:
    keys = (_key(1), _key(2))
    return MultivariateInputDependencies(
        project_id="project-a",
        project_snapshot_id=project_snapshot_id,
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
        observation_count=observations,
        quote_artifact_ids={key: f"quote-{key.code}" for key in keys},
        dividend_artifact_ids={key: f"dividend-{key.code}" for key in keys},
    )


def _row(key: MultivariateListingKey) -> dict[str, object]:
    return {
        "isin": key.isin,
        "exchange": key.exchange,
        "code": key.code,
        "instrument_type": "ETF",
        "distribution_frequency": "monthly",
    }


def _returns() -> list[dict[str, object]]:
    return [
        {
            "isin": key.isin,
            "exchange": key.exchange,
            "code": key.code,
            "date": date,
            "return": value,
        }
        for key, values in ((_key(1), (0.10, -0.10, 0.10)), (_key(2), (0.01, -0.01, 0.01)))
        for date, value in zip(("2024-01-01", "2024-01-02", "2024-01-03"), values, strict=True)
    ]


def test_canonical_artifact_converts_exact_matrix_to_solver_rows() -> None:
    snapshot = build_multivariate_input_snapshot(
        dependencies=_dependencies(observations=504),
        univariate_rows=[_row(_key(1)), _row(_key(2))],
    )
    artifact = build_multivariate_risk_model(snapshot=snapshot, return_rows=_returns())
    solver_input = artifact.solver_input()
    rows = solver_input.covariance_rows()
    assert artifact.available
    assert artifact.estimator == "ledoit_wolf"
    assert len(rows) == 4
    assert rows[1]["covariance"] == artifact.covariance[0][1]
    assert {row["risk_model_id"] for row in rows} == {artifact.risk_model_id}


def test_estimator_and_snapshot_changes_produce_distinct_artifact_ids() -> None:
    snapshot = build_multivariate_input_snapshot(
        dependencies=_dependencies(observations=504), univariate_rows=[_row(_key(1)), _row(_key(2))]
    )
    shrinkage = build_multivariate_risk_model(snapshot=snapshot, return_rows=_returns())
    sample = build_multivariate_risk_model(
        snapshot=snapshot, return_rows=_returns(), estimator="sample"
    )
    changed_snapshot = build_multivariate_input_snapshot(
        dependencies=_dependencies(observations=504, project_snapshot_id="other"),
        univariate_rows=[_row(_key(1)), _row(_key(2))],
    )
    assert shrinkage.risk_model_id != sample.risk_model_id
    assert (
        shrinkage.risk_model_id
        != build_multivariate_risk_model(
            snapshot=changed_snapshot, return_rows=_returns()
        ).risk_model_id
    )


def test_unavailable_snapshot_never_provides_covariance_to_a_solver() -> None:
    snapshot = build_multivariate_input_snapshot(
        dependencies=_dependencies(observations=99), univariate_rows=[_row(_key(1)), _row(_key(2))]
    )
    artifact = build_multivariate_risk_model(snapshot=snapshot, return_rows=_returns())
    assert not artifact.available
    try:
        artifact.solver_input()
    except ValueError as error:
        assert str(error) == "risk model is unavailable"
    else:
        raise AssertionError("unavailable risk model must fail closed")


def test_risk_model_reports_bad_returns_and_stably_handles_nonfinite_identity() -> None:
    snapshot = build_multivariate_input_snapshot(
        dependencies=_dependencies(observations=504), univariate_rows=[_row(_key(1)), _row(_key(2))]
    )
    artifact = build_multivariate_risk_model(snapshot=snapshot, return_rows=[], estimator="invalid")
    assert artifact.availability_reasons[0].startswith("risk_model_error:")
    identity = _risk_model_identity(
        snapshot=snapshot,
        listings=snapshot.listing_keys,
        estimator="sample",
        window_policy="full",
        parameters=(),
        covariance=((float("nan"),),),
        algorithm_version=1,
    )
    assert identity

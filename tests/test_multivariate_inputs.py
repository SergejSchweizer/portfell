from portfell.multivariate_inputs import (
    ExplicitMultivariateInputAdapter,
    MonthlyDistributionEtfPolicy,
    MultivariateInputDependencies,
    MultivariateListingKey,
    build_multivariate_input_snapshot,
)


def _key(n: int) -> MultivariateListingKey:
    return MultivariateListingKey(f"IE{n}", "XETRA", f"ETF{n}")


def _dependencies(
    *,
    keys: tuple[MultivariateListingKey, ...] = (_key(1), _key(2)),
    observations: int = 504,
    **changes: object,
) -> MultivariateInputDependencies:
    values: dict[str, object] = {
        "project_id": "project-a",
        "project_snapshot_id": "snapshot-a",
        "metadata_selection_id": "metadata-a",
        "univariate_run_id": "univariate-a",
        "univariate_selection_id": "selection-a",
        "bivariate_run_id": "bivariate-a",
        "bivariate_status": "complete",
        "bivariate_listing_keys": keys,
        "aligned_calendar_id": "calendar-a",
        "bivariate_aligned_calendar_id": "calendar-a",
        "date_start": "2024-01-01",
        "date_end": "2025-12-31",
        "observation_count": observations,
        "quote_artifact_ids": {key: f"quote-{key.code}" for key in keys},
        "dividend_artifact_ids": {key: f"dividend-{key.code}" for key in keys},
    }
    values.update(changes)
    return MultivariateInputDependencies(**values)  # type: ignore[arg-type]


def _row(key: MultivariateListingKey, **changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "isin": key.isin,
        "exchange": key.exchange,
        "code": key.code,
        "instrument_type": "ETF",
        "distribution_frequency": "monthly",
        "quote_history_production_eligible": True,
    }
    row.update(changes)
    return row


def test_snapshot_is_canonical_and_adapter_equivalent() -> None:
    keys = (_key(2), _key(1))
    dependencies = _dependencies(keys=tuple(sorted(keys)))
    direct = build_multivariate_input_snapshot(
        dependencies=dependencies, univariate_rows=[_row(keys[0]), _row(keys[1])]
    )
    adapter = ExplicitMultivariateInputAdapter().resolve(
        dependencies=dependencies, univariate_rows=[_row(keys[1]), _row(keys[0])]
    )
    assert direct.eligible
    assert direct.listing_keys == (_key(1), _key(2))
    assert direct.snapshot_id == adapter.snapshot_id
    assert direct.dependency_hash == adapter.dependency_hash


def test_snapshot_rejects_typed_non_monthly_and_non_etf_values() -> None:
    keys = (_key(1), _key(2), _key(3))
    snapshot = build_multivariate_input_snapshot(
        dependencies=_dependencies(keys=(_key(1),)),
        univariate_rows=[
            _row(keys[0]),
            _row(keys[1], instrument_type="Fund"),
            _row(keys[2], distribution_frequency="annual"),
        ],
    )
    assert snapshot.listing_keys == (_key(1),)
    assert "fewer_than_two_eligible_listings" in snapshot.availability_reasons
    assert "non_etf" in snapshot.eligibility[1].reasons
    assert "distribution_not_monthly" in snapshot.eligibility[2].reasons


def test_snapshot_detects_dependency_membership_calendar_and_history_failures() -> None:
    snapshot = build_multivariate_input_snapshot(
        dependencies=_dependencies(
            bivariate_status="running",
            bivariate_listing_keys=(_key(1),),
            bivariate_aligned_calendar_id="other",
            observations=503,
        ),
        univariate_rows=[_row(_key(1)), _row(_key(2))],
    )
    assert set(snapshot.availability_reasons) >= {
        "bivariate_not_complete",
        "membership_mismatch",
        "calendar_mismatch",
        "insufficient_common_history",
    }


def test_snapshot_identity_changes_with_pinned_dependency_or_policy() -> None:
    rows = [_row(_key(1)), _row(_key(2))]
    base = build_multivariate_input_snapshot(dependencies=_dependencies(), univariate_rows=rows)
    changed = build_multivariate_input_snapshot(
        dependencies=_dependencies(project_snapshot_id="snapshot-b"), univariate_rows=rows
    )
    policy_changed = build_multivariate_input_snapshot(
        dependencies=_dependencies(),
        univariate_rows=rows,
        policy=MonthlyDistributionEtfPolicy(minimum_common_daily_return_observations=505),
    )
    assert base.snapshot_id != changed.snapshot_id
    assert base.snapshot_id != policy_changed.snapshot_id


def test_same_isin_different_listing_key_remains_distinct() -> None:
    first = MultivariateListingKey("IE1", "XETRA", "ETF1")
    second = MultivariateListingKey("IE1", "LSE", "ETF1L")
    snapshot = build_multivariate_input_snapshot(
        dependencies=_dependencies(
            keys=(first, second),
            quote_artifact_ids={first: "q1", second: "q2"},
            dividend_artifact_ids={first: "d1", second: "d2"},
        ),
        univariate_rows=[_row(first), _row(second)],
    )
    assert snapshot.eligible
    assert len(snapshot.listing_keys) == 2

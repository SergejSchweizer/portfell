import pytest

from portfell.multivariate_candidates import PortfolioCandidate
from portfell.multivariate_inputs import (
    DEFAULT_DISTRIBUTION_ETF_POLICY,
    INPUT_SNAPSHOT_CONTRACT,
    MultivariateInputSnapshot,
    MultivariateListingKey,
)
from portfell.multivariate_structural_walk_forward import (
    build_structural_walk_forward_evidence,
    structural_walk_forward_rows,
)
from portfell.multivariate_validation import ValidationSplit, WalkForwardPolicy

A = MultivariateListingKey("IE1", "X", "A")
B = MultivariateListingKey("IE2", "X", "B")
POLICY = WalkForwardPolicy(
    minimum_training_observations=4,
    test_window_observations=2,
    maximum_refit_count=2,
    minimum_completed_splits=1,
)


def _snapshot() -> MultivariateInputSnapshot:
    return MultivariateInputSnapshot(
        snapshot_id="snapshot-v1",
        contract_version=INPUT_SNAPSHOT_CONTRACT,
        project_id="project-v1",
        project_snapshot_id="project-snapshot-v1",
        metadata_selection_id="metadata-v1",
        univariate_run_id="univariate-run-v1",
        univariate_selection_id="univariate-selection-v1",
        bivariate_run_id="bivariate-run-v1",
        listing_keys=(A, B),
        quote_artifact_ids=((A, "quote-a"), (B, "quote-b")),
        dividend_artifact_ids=((A, "dividend-a"), (B, "dividend-b")),
        aligned_calendar_id="calendar-v1",
        date_start="2025-01-01",
        date_end="2025-01-08",
        observation_count=8,
        policy=DEFAULT_DISTRIBUTION_ETF_POLICY,
        dependency_hash="dependency-v1",
        eligibility=(),
        availability_reasons=(),
    )


def _candidate(candidate_id: str) -> PortfolioCandidate:
    return PortfolioCandidate(
        candidate_id=candidate_id,
        method="equal_weight",
        baseline=True,
        status="feasible",
        reasons=(),
        weights=((A, 0.5), (B, 0.5)),
        variance=0.0001,
        volatility=0.01,
        var=None,
        cvar=None,
        maximum_weight=0.5,
        herfindahl_index=0.5,
        effective_holding_count=2.0,
        gross_ttm_distribution_yield=None,
        gross_monthly_distribution=None,
    )


def _returns() -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for day in range(1, 9):
        rows.extend(
            (
                {
                    "isin": A.isin,
                    "exchange": A.exchange,
                    "code": A.code,
                    "date": f"2025-01-{day:02d}",
                    "return": (day - 4.5) * 0.001,
                },
                {
                    "isin": B.isin,
                    "exchange": B.exchange,
                    "code": B.code,
                    "date": f"2025-01-{day:02d}",
                    "return": (((day * day) % 7) - 3) * 0.0013,
                },
            )
        )
    return tuple(rows)


def _split(
    *,
    split_id: str,
    candidate_id: str,
    train_end: str,
    test_start: str,
    test_end: str,
    value: float,
) -> ValidationSplit:
    return ValidationSplit(
        split_id=split_id,
        method="equal_weight",
        train_start="2025-01-01",
        train_end=train_end,
        test_start=test_start,
        test_end=test_end,
        pre_cost_return=value + 0.0005,
        transaction_cost=0.0005,
        post_cost_return=value,
        volatility=0.02,
        status="complete",
        reason=None,
        candidate_id=candidate_id,
        weights=_candidate(candidate_id).weights,
        requested_method="equal_weight",
        conditional_value_at_risk=0.03,
        max_drawdown=0.04,
        test_observation_count=2,
    )


def test_structural_evidence_reuses_exact_oos_metrics_and_is_deterministic() -> None:
    candidates = (_candidate("root"),)
    refits = ((_candidate("refit-4"),), (_candidate("refit-6"),))
    splits = (
        _split(
            split_id="split-4",
            candidate_id="refit-4",
            train_end="2025-01-04",
            test_start="2025-01-05",
            test_end="2025-01-06",
            value=0.011,
        ),
        _split(
            split_id="split-6",
            candidate_id="refit-6",
            train_end="2025-01-06",
            test_start="2025-01-07",
            test_end="2025-01-08",
            value=-0.007,
        ),
    )
    first = build_structural_walk_forward_evidence(
        snapshot=_snapshot(),
        candidates=candidates,
        return_rows=_returns(),
        refitted_candidate_sets=refits,
        validation_splits=splits,
        policy=POLICY,
    )
    second = build_structural_walk_forward_evidence(
        snapshot=_snapshot(),
        candidates=candidates,
        return_rows=_returns(),
        refitted_candidate_sets=refits,
        validation_splits=splits,
        policy=POLICY,
    )

    assert first == second
    assert structural_walk_forward_rows(first) == structural_walk_forward_rows(second)
    assert [row.post_cost_return for row in first] == [0.011, -0.007]
    assert all(row.train_end < row.test_start for row in first)
    assert all(row.risk_model_contract_version == "multivariate.risk_model@v1" for row in first)
    assert all(row.candidate_contract_version == "multivariate.candidates@v7" for row in first)
    assert all(row.structure_contract_version == "multivariate.structure@v2" for row in first)
    assert all(
        row.effective_pca_risk_drivers is None or row.effective_pca_risk_drivers >= 1.0
        for row in first
    )
    assert all(
        row.largest_pca_risk_share is None or 0.0 <= row.largest_pca_risk_share <= 1.0
        for row in first
    )
    assert all(
        row.largest_cluster_gross_abs_risk_share is None
        or 0.0 <= row.largest_cluster_gross_abs_risk_share <= 1.0
        for row in first
    )


def test_future_injected_training_window_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    from portfell import multivariate_structural_walk_forward as module

    injected = _returns()[:8] + (
        {
            "isin": A.isin,
            "exchange": A.exchange,
            "code": A.code,
            "date": "2025-01-07",
            "return": 9.0,
        },
    )
    monkeypatch.setattr(module, "walk_forward_training_rows", lambda **_: (injected,))
    bad_split = _split(
        split_id="split-injected",
        candidate_id="refit-4",
        train_end="2025-01-07",
        test_start="2025-01-05",
        test_end="2025-01-06",
        value=0.0,
    )
    with pytest.raises(ValueError, match="future_leakage"):
        build_structural_walk_forward_evidence(
            snapshot=_snapshot(),
            candidates=(_candidate("root"),),
            return_rows=_returns(),
            refitted_candidate_sets=((_candidate("refit-4"),),),
            validation_splits=(bad_split,),
            policy=POLICY,
        )


def test_no_winner_or_scorecard_field_is_emitted() -> None:
    source = structural_walk_forward_rows(
        build_structural_walk_forward_evidence(
            snapshot=_snapshot(),
            candidates=(_candidate("root"),),
            return_rows=_returns(),
            refitted_candidate_sets=((_candidate("refit-4"),), (_candidate("refit-6"),)),
            validation_splits=(
                _split(
                    split_id="split-4",
                    candidate_id="refit-4",
                    train_end="2025-01-04",
                    test_start="2025-01-05",
                    test_end="2025-01-06",
                    value=0.0,
                ),
                _split(
                    split_id="split-6",
                    candidate_id="refit-6",
                    train_end="2025-01-06",
                    test_start="2025-01-07",
                    test_end="2025-01-08",
                    value=0.0,
                ),
            ),
            policy=POLICY,
        )
    )
    assert all("winner" not in row and "score" not in row for row in source)

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from math import exp, log
from pathlib import Path

import pytest

from portfell.multivariate_candidate_cluster_risk import build_candidate_cluster_risk
from portfell.multivariate_candidate_structure import build_candidate_pca_risk
from portfell.multivariate_candidate_structure_summary import summarize_candidate_pca_risk
from portfell.multivariate_candidates import PortfolioCandidate
from portfell.multivariate_cluster_stability import build_cluster_bootstrap_stability
from portfell.multivariate_inputs import (
    DEFAULT_DISTRIBUTION_ETF_POLICY,
    INPUT_SNAPSHOT_CONTRACT,
    MultivariateInputSnapshot,
    MultivariateListingKey,
)
from portfell.multivariate_risk_clusters import (
    RiskClusterDiagnostics,
    RiskClusterMembership,
    build_hierarchical_risk_clusters,
)
from portfell.multivariate_risk_model import (
    RISK_MODEL_ARTIFACT_CONTRACT,
    MultivariateRiskModelArtifact,
)
from portfell.multivariate_rolling_structure import build_rolling_structure_diagnostics
from portfell.multivariate_signal_components import build_signal_component_diagnostics
from portfell.multivariate_structural_walk_forward import (
    build_structural_walk_forward_evidence,
)
from portfell.multivariate_structure_v2 import build_structure_pca_diagnostics
from portfell.multivariate_subspace_stability import subspace_overlap
from portfell.multivariate_validation import ValidationSplit, WalkForwardPolicy

A = MultivariateListingKey("IE1", "X", "A")
B = MultivariateListingKey("IE2", "X", "B")
C = MultivariateListingKey("IE3", "X", "C")


def _risk(
    covariance: tuple[tuple[float, ...], ...],
    listings: tuple[MultivariateListingKey, ...],
) -> MultivariateRiskModelArtifact:
    return MultivariateRiskModelArtifact(
        risk_model_id="risk-fixture",
        input_snapshot_id="snapshot-fixture",
        contract_version=RISK_MODEL_ARTIFACT_CONTRACT,
        estimator="ledoit_wolf",
        return_type="log",
        window_policy="full",
        estimator_parameters=(),
        listings=listings,
        aligned_calendar_id="calendar-fixture",
        date_start="2025-01-01",
        date_end="2025-12-31",
        observation_count=300,
        covariance=covariance,
        shrinkage_intensity=0.0,
        minimum_eigenvalue=0.1,
        condition_number=10.0,
        is_positive_semidefinite=True,
        availability_reasons=(),
        algorithm_version=1,
    )


def _candidate(
    candidate_id: str,
    method: str,
    listings: tuple[MultivariateListingKey, ...],
    weights: tuple[float, ...],
) -> PortfolioCandidate:
    return PortfolioCandidate(
        candidate_id=candidate_id,
        method=method,
        baseline=True,
        status="feasible",
        reasons=(),
        weights=tuple(zip(listings, weights, strict=True)),
        variance=None,
        volatility=None,
        var=None,
        cvar=None,
        maximum_weight=max(weights),
        herfindahl_index=sum(value * value for value in weights),
        effective_holding_count=None,
        gross_ttm_distribution_yield=None,
        gross_monthly_distribution=None,
    )


def _rows(
    observations: int,
    listings: tuple[MultivariateListingKey, ...],
    value_fn: Callable[[int, int], float],
) -> tuple[dict[str, object], ...]:
    start = date(2024, 1, 1)
    return tuple(
        {
            "isin": listing.isin,
            "exchange": listing.exchange,
            "code": listing.code,
            "date": (start + timedelta(days=index)).isoformat(),
            "return": float(value_fn(index, listing_index)),
        }
        for index in range(observations)
        for listing_index, listing in enumerate(listings)
    )


def test_independent_pca_entropy_and_candidate_variance_reconciliation() -> None:
    risk = _risk(((9.0, 0.0), (0.0, 1.0)), (A, B))
    structure = build_structure_pca_diagnostics(risk)

    expected_covariance_shares = (9.0 / 10.0, 1.0 / 10.0)
    expected_covariance_rank = exp(-sum(value * log(value) for value in expected_covariance_shares))
    assert structure.covariance.explained_variance == pytest.approx(expected_covariance_shares)
    assert structure.covariance.effective_rank == pytest.approx(expected_covariance_rank)
    assert structure.correlation.explained_variance == pytest.approx((0.5, 0.5))
    assert structure.correlation.effective_rank == pytest.approx(2.0)

    candidate = _candidate("candidate", "equal_weight", (A, B), (0.5, 0.5))
    pca_risk = build_candidate_pca_risk(candidate=candidate, risk_model=risk)
    expected_contributions = (9.0 * 0.5**2, 1.0 * 0.5**2)
    expected_portfolio_variance = 0.5 * 9.0 * 0.5 + 0.5 * 1.0 * 0.5
    assert tuple(row.variance_contribution for row in pca_risk.contributions) == pytest.approx(
        expected_contributions
    )
    assert sum(row.variance_contribution for row in pca_risk.contributions) == pytest.approx(
        expected_portfolio_variance
    )
    summary = summarize_candidate_pca_risk(pca_risk)
    expected_effective_drivers = exp(-sum(value * log(value) for value in (0.9, 0.1)))
    assert summary.effective_pca_risk_drivers == pytest.approx(expected_effective_drivers)
    assert summary.largest_pca_risk_share == pytest.approx(0.9)
    assert summary.components_for_80pct_risk == 1
    assert summary.components_for_90pct_risk == 1
    assert summary.components_for_95pct_risk == 2


def test_average_linkage_fixture_does_not_chain_through_pairwise_thresholds() -> None:
    correlation = (
        (1.0, 0.8, 0.0),
        (0.8, 1.0, 0.8),
        (0.0, 0.8, 1.0),
    )
    result = build_hierarchical_risk_clusters(listings=(A, B, C), correlation=correlation)
    membership = {row.listing: row.cluster_id for row in result.memberships}
    assert result.cluster_count == 2
    assert membership[A] == membership[B]
    assert membership[C] != membership[A]


def test_signed_and_gross_cluster_attribution_matches_hand_formula() -> None:
    covariance = (
        (1.0, -0.9, 0.0),
        (-0.9, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    risk = _risk(covariance, (A, B, C))
    candidate = _candidate("candidate", "equal_weight", (A, B, C), (0.1, 0.8, 0.1))
    clusters = RiskClusterDiagnostics(
        memberships=(
            RiskClusterMembership(A, "Cluster 1"),
            RiskClusterMembership(B, "Cluster 2"),
            RiskClusterMembership(C, "Cluster 3"),
        ),
        cluster_count=3,
        largest_redundancy_warning=None,
        availability_reasons=(),
    )
    result = build_candidate_cluster_risk(
        candidate=candidate,
        risk_model=risk,
        clusters=clusters,
    )

    weights = (0.1, 0.8, 0.1)
    marginal = tuple(
        sum(covariance[left][right] * weights[right] for right in range(3)) for left in range(3)
    )
    signed = tuple(weights[index] * marginal[index] for index in range(3))
    variance = sum(signed)
    gross = sum(abs(value) for value in signed)
    assert tuple(row.signed_variance_contribution for row in result.rows) == pytest.approx(signed)
    assert tuple(row.signed_percent_variance for row in result.rows) == pytest.approx(
        tuple(value / variance for value in signed)
    )
    assert tuple(row.gross_abs_risk_share for row in result.rows) == pytest.approx(
        tuple(abs(value) / gross for value in signed)
    )
    assert result.rows[0].signed_variance_contribution < 0.0


def test_subspace_overlap_matches_projection_formula_and_rotation_invariance() -> None:
    e1 = (1.0, 0.0, 0.0)
    e2 = (0.0, 1.0, 0.0)
    e3 = (0.0, 0.0, 1.0)
    rotated = (
        (2**-0.5, 2**-0.5, 0.0),
        (-(2**-0.5), 2**-0.5, 0.0),
    )
    assert subspace_overlap((e1, e2), rotated, component_count=2) == pytest.approx(1.0)
    assert subspace_overlap((e1,), (e3,), component_count=1) == pytest.approx(0.0)


def test_parallel_analysis_is_frozen_deterministic_and_structure_sensitive() -> None:
    pytest.importorskip("numpy")
    listings = (A, B, C)
    correlated = _rows(
        72,
        listings,
        lambda index, column: (
            ((index % 11) - 5) * 0.001
            if column == 0
            else (
                ((index % 11) - 5) * 0.00095 + ((index % 3) - 1) * 0.00001
                if column == 1
                else (((index * 7) % 13) - 6) * 0.0008
            )
        ),
    )
    changed = _rows(
        72,
        listings,
        lambda index, column: (
            ((index % 11) - 5) * 0.001
            if column == 0
            else (
                (((index * 5) % 17) - 8) * 0.0007
                if column == 1
                else (((index * 7) % 13) - 6) * 0.0008
            )
        ),
    )
    first = build_signal_component_diagnostics(
        return_rows=correlated,
        listings=listings,
    )
    second = build_signal_component_diagnostics(
        return_rows=correlated,
        listings=listings,
    )
    altered = build_signal_component_diagnostics(return_rows=changed, listings=listings)
    assert first == second
    assert first.replicate_count == 100
    assert first.seed == 41
    assert first.quantile == 0.95
    assert first.quantile_method == "higher"
    assert first.observed_eigenvalues != altered.observed_eigenvalues


def test_bootstrap_duplicate_series_pair_stability_is_one_and_deterministic() -> None:
    pytest.importorskip("numpy")
    listings = (A, B)
    rows = _rows(
        64,
        listings,
        lambda index, column: (((index * 5) % 17) - 8) * 0.001,
    )
    canonical = RiskClusterDiagnostics(
        memberships=(
            RiskClusterMembership(A, "Cluster 1"),
            RiskClusterMembership(B, "Cluster 1"),
        ),
        cluster_count=1,
        largest_redundancy_warning=None,
        availability_reasons=(),
    )
    first = build_cluster_bootstrap_stability(
        return_rows=rows,
        listings=listings,
        canonical_clusters=canonical,
    )
    second = build_cluster_bootstrap_stability(
        return_rows=rows,
        listings=listings,
        canonical_clusters=canonical,
    )
    assert first == second
    assert first.replicate_count == 100
    assert first.block_length == 21
    assert first.seed == 41
    assert len(first.pairs) == 1
    assert first.pairs[0].co_cluster_probability == pytest.approx(1.0)


def test_rolling_windows_are_252_stride_21_max_24_and_latest_anchored() -> None:
    listings = (A, B)
    rows = _rows(
        300,
        listings,
        lambda index, column: (
            (((index * 5) % 19) - 9) * 0.001 if column == 0 else (((index * 7) % 23) - 11) * 0.0008
        ),
    )
    result = build_rolling_structure_diagnostics(return_rows=rows, listings=listings)
    assert result.available
    assert len(result.rows) == 3
    assert all(row.observation_count == 252 for row in result.rows)
    source_dates = tuple(sorted({str(row["date"]) for row in rows}))
    expected_end_indexes = (257, 278, 299)
    assert tuple(row.date_end for row in result.rows) == tuple(
        source_dates[index] for index in expected_end_indexes
    )
    assert tuple(row.date_start for row in result.rows) == tuple(
        source_dates[index - 251] for index in expected_end_indexes
    )
    assert result.rows[-1].date_end == source_dates[-1]
    assert all(row.date_start <= row.date_end <= source_dates[-1] for row in result.rows)


def _snapshot() -> MultivariateInputSnapshot:
    return MultivariateInputSnapshot(
        "snapshot-v1",
        INPUT_SNAPSHOT_CONTRACT,
        "project-v1",
        "project-snapshot-v1",
        "metadata-v1",
        "univariate-v1",
        "univariate-selection-v1",
        "bivariate-v1",
        (A, B),
        ((A, "quote-a"), (B, "quote-b")),
        ((A, "dividend-a"), (B, "dividend-b")),
        "calendar-v1",
        "2024-01-01",
        "2024-01-06",
        6,
        DEFAULT_DISTRIBUTION_ETF_POLICY,
        "dependency-v1",
        (),
        (),
    )


def _split(candidate: PortfolioCandidate, value: float) -> ValidationSplit:
    return ValidationSplit(
        split_id=f"split-{candidate.candidate_id}",
        method=candidate.method,
        train_start="2024-01-01",
        train_end="2024-01-04",
        test_start="2024-01-05",
        test_end="2024-01-06",
        pre_cost_return=value + 0.0005,
        transaction_cost=0.0005,
        post_cost_return=value,
        volatility=0.02,
        status="complete",
        reason=None,
        candidate_id=candidate.candidate_id,
        weights=candidate.weights,
        requested_method=candidate.method,
        conditional_value_at_risk=0.03,
        max_drawdown=0.04,
        test_observation_count=2,
    )


def test_structural_walk_forward_is_additive_and_pre_v2_winner_is_unchanged() -> None:
    roots = (
        _candidate("root-eq", "equal_weight", (A, B), (0.5, 0.5)),
        _candidate("root-iv", "inverse_volatility", (A, B), (0.7, 0.3)),
    )
    refitted = (
        _candidate("refit-eq", "equal_weight", (A, B), (0.5, 0.5)),
        _candidate("refit-iv", "inverse_volatility", (A, B), (0.7, 0.3)),
    )
    splits = (_split(refitted[0], 0.01), _split(refitted[1], 0.02))
    frozen_before = tuple(splits)
    pre_v2_winner = max(
        splits,
        key=lambda split: (split.post_cost_return, split.candidate_id),
    ).candidate_id
    rows = _rows(
        6,
        (A, B),
        lambda index, column: (
            ((index % 5) - 2) * 0.001 if column == 0 else (((index * 3) % 7) - 3) * 0.0012
        ),
    )
    evidence = build_structural_walk_forward_evidence(
        snapshot=_snapshot(),
        candidates=roots,
        return_rows=rows,
        refitted_candidate_sets=(refitted,),
        validation_splits=splits,
        policy=WalkForwardPolicy(
            minimum_training_observations=4,
            test_window_observations=2,
            maximum_refit_count=1,
            minimum_completed_splits=1,
        ),
    )
    post_v2_winner = max(
        splits,
        key=lambda split: (split.post_cost_return, split.candidate_id),
    ).candidate_id
    assert tuple(splits) == frozen_before
    assert pre_v2_winner == post_v2_winner == "refit-iv"
    assert {row.split_id for row in evidence} == {split.split_id for split in splits}
    assert all(row.train_end < row.test_start for row in evidence)


def test_v2_ui_and_service_negative_space_and_hrp_boundary() -> None:
    root = Path(__file__).resolve().parents[1]
    v2_paths = (
        root / "src/portfell/multivariate_structure_artifacts.py",
        root / "src/portfell/dash_app/structure_presenters.py",
        root / "src/portfell/dash_app/candidate_structure_presenters.py",
    )
    emitted_surface = "\n".join(path.read_text(encoding="utf-8") for path in v2_paths)
    assert "effective_independent_drivers" not in emitted_surface
    assert "strongest_common_driver" not in emitted_surface

    candidates_source = (root / "src/portfell/multivariate_candidates.py").read_text(
        encoding="utf-8"
    )
    assert "multivariate_risk_clusters" not in candidates_source
    assert "RiskClusterDiagnostics" not in candidates_source

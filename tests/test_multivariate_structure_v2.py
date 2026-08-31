from dataclasses import replace
from math import isclose

from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_risk_model import RISK_MODEL_ARTIFACT_CONTRACT, MultivariateRiskModelArtifact
from portfell.multivariate_structure_v2 import build_structure_pca_diagnostics, correlation_from_covariance


def _risk(matrix: tuple[tuple[float, ...], ...]) -> MultivariateRiskModelArtifact:
    listings = (MultivariateListingKey("IE1", "X", "A"), MultivariateListingKey("IE2", "X", "B"))
    return MultivariateRiskModelArtifact(
        "risk", "snapshot", RISK_MODEL_ARTIFACT_CONTRACT, "ledoit_wolf", "log", "full", (), listings,
        "calendar", "2024-01-01", "2025-01-01", 252, matrix, 0.1, 0.1, 2.0, True, (), 1,
    )


def test_correlation_is_derived_from_canonical_covariance() -> None:
    matrix, reason = correlation_from_covariance(((4.0, 1.0), (1.0, 1.0)))
    assert reason is None
    assert matrix[0][0] == 1.0 and matrix[1][1] == 1.0
    assert matrix[0][1] == 0.5


def test_covariance_and_correlation_pca_are_separate() -> None:
    result = build_structure_pca_diagnostics(_risk(((4.0, 1.0), (1.0, 1.0))))
    assert result.covariance.available and result.correlation.available
    assert result.covariance.eigenvalues != result.correlation.eigenvalues
    assert result.covariance.effective_rank is not None
    assert result.correlation.effective_rank is not None
    assert result.covariance.dominant_component_representative is not None
    assert result.correlation.dominant_component_representative is not None


def test_bad_variance_fails_only_correlation_pca_closed() -> None:
    result = build_structure_pca_diagnostics(_risk(((1.0, 0.0), (0.0, 0.0))))
    assert result.covariance.available
    assert not result.correlation.available
    assert result.correlation.availability_reasons == ("correlation_non_positive_variance",)


def test_small_correlation_boundary_error_may_be_clipped() -> None:
    matrix, reason = correlation_from_covariance(((1.0, 1.0 + 5e-13), (1.0 + 5e-13, 1.0)))
    assert reason is None
    assert matrix[0][1] == 1.0
    _, reason = correlation_from_covariance(((1.0, 1.0 + 2e-12), (1.0 + 2e-12, 1.0)))
    assert reason == "correlation_out_of_bounds"


def test_unavailable_risk_model_fails_both_views_closed() -> None:
    result = build_structure_pca_diagnostics(replace(_risk(((1.0, 0.0), (0.0, 1.0))), availability_reasons=("x",)))
    assert not result.covariance.available and not result.correlation.available
    assert isclose(1.0, 1.0)

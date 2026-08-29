from dataclasses import replace

from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_risk_model import (
    RISK_MODEL_ARTIFACT_CONTRACT,
    MultivariateRiskModelArtifact,
)
from portfell.multivariate_structure import build_multivariate_structure


def _risk_model(matrix: tuple[tuple[float, ...], ...]) -> MultivariateRiskModelArtifact:
    listings = (MultivariateListingKey("IE1", "X", "A"), MultivariateListingKey("IE2", "X", "B"))
    return MultivariateRiskModelArtifact(
        risk_model_id="risk-a",
        input_snapshot_id="snapshot-a",
        contract_version=RISK_MODEL_ARTIFACT_CONTRACT,
        estimator="ledoit_wolf",
        return_type="log",
        window_policy="full",
        estimator_parameters=(),
        listings=listings,
        aligned_calendar_id="calendar-a",
        date_start="2024-01-01",
        date_end="2025-01-01",
        observation_count=504,
        covariance=matrix,
        shrinkage_intensity=0.1,
        minimum_eigenvalue=0.1,
        condition_number=2.0,
        is_positive_semidefinite=True,
        availability_reasons=(),
        algorithm_version=1,
    )


def test_structure_reports_explained_variance_effective_rank_and_bounded_loadings() -> None:
    result = build_multivariate_structure(_risk_model(((2.0, 0.0), (0.0, 1.0))))
    assert result.available
    assert result.explained_variance == (2 / 3, 1 / 3)
    assert result.cumulative_explained_variance[-1] == 1.0
    assert result.summary()["candidate_etf_count"] == 2
    assert result.summary()["strongest_common_driver"] is not None
    assert result.component_page(component_id="Component 1", limit=1)["total"] == 2


def test_structure_is_deterministic_and_unavailable_risk_model_fails_closed() -> None:
    first = build_multivariate_structure(_risk_model(((1.0, 0.8), (0.8, 1.0))))
    second = build_multivariate_structure(_risk_model(((1.0, 0.8), (0.8, 1.0))))
    assert first.structure_id == second.structure_id
    warning = first.summary()["largest_redundancy_warning"]
    assert warning is not None
    assert warning["correlation"] == 0.8
    unavailable = replace(_risk_model(()), availability_reasons=("bad",))
    assert not build_multivariate_structure(unavailable).available


def test_structure_reports_zero_variance_and_no_comparable_pair_explicitly() -> None:
    assert not build_multivariate_structure(_risk_model(((0.0, 0.0), (0.0, 0.0)))).available
    structure = build_multivariate_structure(_risk_model(((1.0, 0.0), (0.0, 0.0))))
    assert structure.summary()["largest_redundancy_warning"] is None

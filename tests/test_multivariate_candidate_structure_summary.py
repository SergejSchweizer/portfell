from portfell.multivariate_candidate_structure import CandidatePcaContribution, CandidatePcaRisk
from portfell.multivariate_candidate_structure_summary import summarize_candidate_pca_risk


def _risk(values: tuple[float, ...]) -> CandidatePcaRisk:
    total = sum(values)
    return CandidatePcaRisk(
        "candidate",
        "method",
        "risk",
        tuple(
            CandidatePcaContribution(
                "candidate",
                "method",
                f"Component {i + 1}",
                value,
                value / total,
                "risk",
            )
            for i, value in enumerate(values)
        ),
        total,
        (),
    )


def test_one_factor_and_equal_k_effective_driver_counts() -> None:
    one = summarize_candidate_pca_risk(_risk((1.0, 0.0, 0.0)))
    assert one.effective_pca_risk_drivers == 1.0
    assert one.largest_pca_risk_share == 1.0
    equal = summarize_candidate_pca_risk(_risk((1.0, 1.0, 1.0, 1.0)))
    assert equal.effective_pca_risk_drivers == 4.0
    assert equal.largest_pca_risk_share == 0.25
    assert equal.components_for_80pct_risk == 4


def test_risk_component_counts_sort_descending() -> None:
    result = summarize_candidate_pca_risk(_risk((0.6, 0.2, 0.1, 0.1)))
    assert result.components_for_80pct_risk == 2
    assert result.components_for_90pct_risk == 3
    assert result.components_for_95pct_risk == 4


def test_unavailable_pca_risk_stays_unavailable() -> None:
    result = summarize_candidate_pca_risk(CandidatePcaRisk("c", "m", "r", (), None, ("x",)))
    assert not result.available
    assert result.effective_pca_risk_drivers is None

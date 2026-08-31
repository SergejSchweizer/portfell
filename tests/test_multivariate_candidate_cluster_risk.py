from portfell.multivariate_candidate_cluster_risk import build_candidate_cluster_risk
from portfell.multivariate_candidates import PortfolioCandidate
from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_risk_clusters import RiskClusterDiagnostics, RiskClusterMembership
from portfell.multivariate_risk_model import RISK_MODEL_ARTIFACT_CONTRACT, MultivariateRiskModelArtifact


A = MultivariateListingKey("IE1", "X", "A")
B = MultivariateListingKey("IE2", "X", "B")


def _candidate() -> PortfolioCandidate:
    return PortfolioCandidate(
        candidate_id="c", method="m", baseline=False, status="feasible", reasons=(),
        weights=((A, 0.75), (B, 0.25)), variance=None, volatility=None, var=None, cvar=None,
        maximum_weight=None, herfindahl_index=None, effective_holding_count=None,
        gross_ttm_distribution_yield=None, gross_monthly_distribution=None,
    )


def _risk() -> MultivariateRiskModelArtifact:
    return MultivariateRiskModelArtifact(
        "risk", "snapshot", RISK_MODEL_ARTIFACT_CONTRACT, "ledoit_wolf", "log", "full", (), (A, B),
        "calendar", "2024", "2025", 252, ((1.0, -0.5), (-0.5, 1.0)), 0.1, 0.5, 3.0, True, (), 1,
    )


def test_cluster_risk_reconciles_and_preserves_signed_contributions() -> None:
    clusters = RiskClusterDiagnostics(
        (RiskClusterMembership(A, "Cluster 1"), RiskClusterMembership(B, "Cluster 2")), 2, None, ()
    )
    result = build_candidate_cluster_risk(candidate=_candidate(), risk_model=_risk(), clusters=clusters)
    assert result.available
    assert sum(row.signed_percent_variance for row in result.rows) == 1.0
    assert sum(row.gross_abs_risk_share for row in result.rows) == 1.0
    assert any(row.signed_variance_contribution < 0.0 for row in result.rows)


def test_cluster_risk_fails_closed_on_membership_mismatch() -> None:
    clusters = RiskClusterDiagnostics((RiskClusterMembership(A, "Cluster 1"),), 1, None, ())
    result = build_candidate_cluster_risk(candidate=_candidate(), risk_model=_risk(), clusters=clusters)
    assert not result.available
    assert result.rows == ()

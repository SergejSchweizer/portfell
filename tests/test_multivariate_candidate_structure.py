from portfell.multivariate_candidate_structure import build_candidate_pca_risk
from portfell.multivariate_candidates import PortfolioCandidate
from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_risk_model import (
    RISK_MODEL_ARTIFACT_CONTRACT,
    MultivariateRiskModelArtifact,
)

A = MultivariateListingKey("IE1", "X", "A")
B = MultivariateListingKey("IE2", "X", "B")


def _candidate(weights: tuple[tuple[MultivariateListingKey, float], ...]) -> PortfolioCandidate:
    return PortfolioCandidate(
        candidate_id="candidate-a",
        method="equal_weight",
        baseline=True,
        status="feasible",
        reasons=(),
        weights=weights,
        variance=0.5,
        volatility=None,
        var=None,
        cvar=None,
        maximum_weight=None,
        herfindahl_index=None,
        effective_holding_count=None,
        gross_ttm_distribution_yield=None,
        gross_monthly_distribution=None,
    )


def _risk() -> MultivariateRiskModelArtifact:
    return MultivariateRiskModelArtifact(
        "risk",
        "snapshot",
        RISK_MODEL_ARTIFACT_CONTRACT,
        "ledoit_wolf",
        "log",
        "full",
        (),
        (A, B),
        "calendar",
        "2024-01-01",
        "2025-01-01",
        252,
        ((2.0, 0.0), (0.0, 1.0)),
        0.1,
        1.0,
        2.0,
        True,
        (),
        1,
    )


def test_candidate_pca_contributions_reconcile_to_variance() -> None:
    result = build_candidate_pca_risk(
        candidate=_candidate(((A, 0.5), (B, 0.5))),
        risk_model=_risk(),
    )
    assert result.available
    assert result.portfolio_variance == 0.75
    assert sum(row.variance_contribution for row in result.contributions) == 0.75
    assert sum(row.percent_portfolio_variance for row in result.contributions) == 1.0
    assert result.contributions[0].variance_contribution == 0.5
    assert result.contributions[1].variance_contribution == 0.25


def test_candidate_pca_alignment_uses_full_listing_identity() -> None:
    wrong = MultivariateListingKey("IE1", "Y", "A")
    result = build_candidate_pca_risk(
        candidate=_candidate(((wrong, 0.5), (B, 0.5))),
        risk_model=_risk(),
    )
    assert not result.available
    assert result.availability_reasons == ("candidate_identity_mismatch",)


def test_infeasible_candidate_gets_no_zero_contributions() -> None:
    candidate = _candidate(((A, 0.5), (B, 0.5)))
    unavailable = PortfolioCandidate(
        **{
            **candidate.__dict__,
            "status": "unavailable",
            "reasons": ("solver",),
        }
    )
    result = build_candidate_pca_risk(candidate=unavailable, risk_model=_risk())
    assert not result.available
    assert result.contributions == ()

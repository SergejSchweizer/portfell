from portfell.multivariate_candidates import PortfolioCandidate
from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_risk_model import RISK_MODEL_ARTIFACT_CONTRACT, MultivariateRiskModelArtifact
from portfell.multivariate_structure_artifacts import build_structure_v2_documents


A = MultivariateListingKey("IE1", "X", "A")
B = MultivariateListingKey("IE2", "X", "B")


def _risk() -> MultivariateRiskModelArtifact:
    return MultivariateRiskModelArtifact(
        "risk-v1", "snapshot-v1", RISK_MODEL_ARTIFACT_CONTRACT, "ledoit_wolf", "log", "full", (), (A, B),
        "calendar-v1", "2025-01-01", "2025-01-10", 10, ((1.0, 0.2), (0.2, 1.0)),
        0.1, 0.8, 1.5, True, (), 1,
    )


def _candidate() -> PortfolioCandidate:
    return PortfolioCandidate(
        candidate_id="candidate-a", method="equal_weight", baseline=True, status="feasible", reasons=(),
        weights=((A, 0.5), (B, 0.5)), variance=0.6, volatility=None, var=None, cvar=None,
        maximum_weight=None, herfindahl_index=None, effective_holding_count=None,
        gross_ttm_distribution_yield=None, gross_monthly_distribution=None,
    )


def _returns() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "isin": listing.isin,
            "exchange": listing.exchange,
            "code": listing.code,
            "date": f"2025-01-{day:02d}",
            "return": ((day % 5) - 2) * (0.001 if listing == A else 0.0012),
        }
        for day in range(1, 11)
        for listing in (A, B)
    )


def test_structure_v2_documents_are_stable_and_separately_versioned() -> None:
    first = build_structure_v2_documents(risk_model=_risk(), return_rows=_returns(), candidates=(_candidate(),))
    second = build_structure_v2_documents(risk_model=_risk(), return_rows=_returns(), candidates=(_candidate(),))
    assert first.structure_id == second.structure_id
    assert first.candidate_structure_id == second.candidate_structure_id
    assert first.structure == second.structure
    assert first.candidate_structure == second.candidate_structure
    assert first.structure["contract_version"] == "multivariate.structure@v2"
    assert first.candidate_structure["contract_version"] == "multivariate.candidate_structure@v1"


def test_v2_documents_do_not_emit_retired_names_or_change_candidates() -> None:
    candidate = _candidate()
    result = build_structure_v2_documents(risk_model=_risk(), return_rows=_returns(), candidates=(candidate,))
    payload = repr((result.structure, result.candidate_structure))
    assert "effective_independent_drivers" not in payload
    assert "strongest_common_driver" not in payload
    assert candidate.weights == ((A, 0.5), (B, 0.5))
    assert result.candidate_structure["candidate_ids"] == ["candidate-a"]


def test_optional_diagnostics_fail_closed_not_as_zero() -> None:
    result = build_structure_v2_documents(risk_model=_risk(), return_rows=_returns(), candidates=(_candidate(),))
    rolling = result.structure["rolling_structure"]
    assert isinstance(rolling, dict)
    assert rolling["items"] == []
    assert rolling["availability_reasons"] == ["rolling_structure_insufficient_history"]
    subspace = result.structure["subspace_stability"]
    assert isinstance(subspace, dict)
    assert subspace["items"] == []
    assert subspace["availability_reasons"]

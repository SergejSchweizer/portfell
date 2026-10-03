from types import SimpleNamespace

from pytest import approx

from portfell.contract_versioning import ContractVersion
from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_risk_model import MultivariateRiskModelArtifact
from portfell.multivariate_risk_stress import (
    CORRELATION_CONVERGENCE_25PCT,
    RISK_STRESS_CONTRACT,
    VOLATILITY_UP_25PCT,
    correlation_convergence_25pct,
    volatility_up_25pct,
)


def test_volatility_up_25pct_matches_two_asset_oracle_and_serializes() -> None:
    keys = (MultivariateListingKey("A", "X", "A"), MultivariateListingKey("B", "X", "B"))
    risk = MultivariateRiskModelArtifact(
        risk_model_id="risk-1",
        input_snapshot_id="snap",
        contract_version=ContractVersion("multivariate.risk_model", 1),
        estimator="ledoit_wolf",
        return_type="log",
        window_policy="full",
        estimator_parameters=(),
        listings=keys,
        aligned_calendar_id="cal",
        date_start="2020-01-01",
        date_end="2020-02-01",
        observation_count=2,
        covariance=((0.04, 0.01), (0.01, 0.09)),
        shrinkage_intensity=None,
        minimum_eigenvalue=0.03,
        condition_number=1.0,
        is_positive_semidefinite=True,
        availability_reasons=(),
        algorithm_version=1,
    )
    candidate = SimpleNamespace(
        candidate_id="candidate-1",
        candidate_configuration_id="config-1",
        status="feasible",
        weights=((keys[0], 0.4), (keys[1], 0.6)),
    )
    result = volatility_up_25pct(risk_model=risk, candidate=candidate)
    base_variance = 0.4**2 * 0.04 + 2 * 0.4 * 0.6 * 0.01 + 0.6**2 * 0.09
    assert result.scenario == VOLATILITY_UP_25PCT
    assert result.status == "available"
    assert result.stressed_variance == approx(base_variance * 1.25**2)
    assert result.stressed_volatility == approx((base_variance * 1.25**2) ** 0.5)
    assert result.to_row()["contract_version"] == RISK_STRESS_CONTRACT.qualified_name


def test_volatility_stress_is_unavailable_for_invalid_risk_model() -> None:
    key = MultivariateListingKey("A", "X", "A")
    risk = SimpleNamespace(
        available=False, risk_model_id="risk-1", listings=(key,), covariance=((1.0,),)
    )
    candidate = SimpleNamespace(
        candidate_id="c", candidate_configuration_id="cfg", status="feasible", weights=((key, 1.0),)
    )
    result = volatility_up_25pct(risk_model=risk, candidate=candidate)
    assert result.status == "unavailable"
    assert result.stressed_variance is None


def test_correlation_convergence_moves_off_diagonal_toward_one() -> None:
    keys = (MultivariateListingKey("A", "X", "A"), MultivariateListingKey("B", "X", "B"))
    risk = MultivariateRiskModelArtifact(
        risk_model_id="risk-1",
        input_snapshot_id="snap",
        contract_version=ContractVersion("multivariate.risk_model", 1),
        estimator="ledoit_wolf",
        return_type="log",
        window_policy="full",
        estimator_parameters=(),
        listings=keys,
        aligned_calendar_id="cal",
        date_start="2020-01-01",
        date_end="2020-02-01",
        observation_count=2,
        covariance=((0.04, 0.0), (0.0, 0.09)),
        shrinkage_intensity=None,
        minimum_eigenvalue=0.04,
        condition_number=1.0,
        is_positive_semidefinite=True,
        availability_reasons=(),
        algorithm_version=1,
    )
    candidate = SimpleNamespace(
        candidate_id="c",
        candidate_configuration_id="cfg",
        status="feasible",
        weights=((keys[0], 0.5), (keys[1], 0.5)),
    )
    result = correlation_convergence_25pct(risk_model=risk, candidate=candidate)
    assert result.scenario == CORRELATION_CONVERGENCE_25PCT
    assert result.status == "available"
    # stressed covariance has off-diagonal 0.25 * 0.2 * 0.3 = 0.015
    assert result.stressed_variance == approx(0.25 * 0.04 + 0.25 * 0.09 + 2 * 0.25 * 0.015)

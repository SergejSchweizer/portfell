from __future__ import annotations

from portfell.multivariate.candidates.builder import (
    CandidateConfiguration,
    CandidateMethodId,
    annualized_expected_log_returns,
)
from portfell.multivariate.candidates.risk_models import (
    RISK_MODELS,
    RiskModel,
    align_returns,
    estimate_risk_model,
)
from portfell.multivariate.contracts.common import ListingIdentity


def _series() -> dict[ListingIdentity, tuple[tuple[str, float], ...]]:
    a = ListingIdentity("A", "XETRA", "AAA")
    b = ListingIdentity("B", "XETRA", "BBB")
    return {
        b: (("2024-01-03", 0.02), ("2024-01-04", 0.03), ("2024-01-05", 0.01)),
        a: (("2024-01-02", 0.01), ("2024-01-03", 0.01), ("2024-01-04", 0.02)),
    }


def test_pr285_risk_model_registry_is_exactly_sample_ledoit_wolf_ewma() -> None:
    assert RISK_MODELS == (RiskModel.SAMPLE, RiskModel.LEDOIT_WOLF, RiskModel.EWMA)


def test_pr285_alignment_is_deterministic_and_reports_exact_common_history() -> None:
    series = _series()
    forward = align_returns(series)
    reverse = align_returns(dict(reversed(tuple(series.items()))))
    assert forward == reverse
    assert [listing.isin for listing in forward.listings] == ["A", "B"]
    assert forward.dates == ("2024-01-03", "2024-01-04")
    assert forward.rows == ((0.01, 0.02), (0.02, 0.03))
    for model in RISK_MODELS:
        result = estimate_risk_model(forward, model)
        assert result.available is True
        assert result.first_date == "2024-01-03"
        assert result.last_date == "2024-01-04"
        assert result.observation_count == 2


def test_pr285_insufficient_history_is_typed_unavailable() -> None:
    listing = ListingIdentity("A", "XETRA", "AAA")
    aligned = align_returns({listing: (("2024-01-03", 0.01),)})
    for model in RISK_MODELS:
        result = estimate_risk_model(aligned, model)
        assert result.available is False
        assert result.covariance is None
        assert result.reason == "insufficient_history"


def test_pr285_configuration_identity_changes_with_model_method_and_settings_version() -> None:
    base = CandidateConfiguration(
        RiskModel.SAMPLE,
        CandidateMethodId.EQUAL_WEIGHT,
        "settings-v1",
        "algo-v1",
    )
    other_model = CandidateConfiguration(
        RiskModel.EWMA,
        CandidateMethodId.EQUAL_WEIGHT,
        "settings-v1",
        "algo-v1",
    )
    other_method = CandidateConfiguration(
        RiskModel.SAMPLE,
        CandidateMethodId.MINIMUM_VARIANCE,
        "settings-v1",
        "algo-v1",
    )
    other_settings = CandidateConfiguration(
        RiskModel.SAMPLE,
        CandidateMethodId.EQUAL_WEIGHT,
        "settings-v2",
        "algo-v1",
    )
    assert len({base.configuration_id, other_model.configuration_id, other_method.configuration_id, other_settings.configuration_id}) == 4


def test_pr285_expected_return_estimate_is_split_local() -> None:
    listing = ListingIdentity("A", "XETRA", "AAA")
    early = align_returns(
        {listing: (("2024-01-02", 0.001), ("2024-01-03", 0.001))}
    )
    later = align_returns(
        {
            listing: (
                ("2024-01-02", 0.001),
                ("2024-01-03", 0.001),
                ("2024-01-04", 0.05),
            )
        }
    )
    assert annualized_expected_log_returns(early) != annualized_expected_log_returns(later)

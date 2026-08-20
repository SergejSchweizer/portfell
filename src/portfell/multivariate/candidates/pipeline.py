"""Composition-only candidate pipeline across risk models and methods."""

from __future__ import annotations

from dataclasses import dataclass

from portfell.multivariate.candidates.builder import CandidateConfiguration, CandidateMethodId, annualized_expected_log_returns
from portfell.multivariate.candidates.methods import CandidateResult, PortfolioMethod
from portfell.multivariate.candidates.risk_models import RISK_MODELS, RiskModelResult, align_returns, estimate_risk_model
from portfell.multivariate.candidates.solvers import build_candidate
from portfell.multivariate.contracts.common import ListingIdentity


@dataclass(frozen=True, slots=True)
class CandidatePipelineItem:
    configuration: CandidateConfiguration
    risk: RiskModelResult
    candidate: CandidateResult


def build_candidate_universe(
    series: dict[ListingIdentity, tuple[tuple[str, float], ...]],
    *,
    settings_version: str,
    algorithm_version: str,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
) -> tuple[CandidatePipelineItem, ...]:
    """Build every frozen risk-model/method configuration deterministically."""

    aligned = align_returns(series)
    if not aligned.listings:
        return ()
    expected_returns = annualized_expected_log_returns(aligned) if aligned.rows else ()
    results: list[CandidatePipelineItem] = []
    for risk_model in RISK_MODELS:
        risk = estimate_risk_model(aligned, risk_model)
        for method in PortfolioMethod:
            configuration = CandidateConfiguration(
                risk_model=risk_model,
                method=CandidateMethodId(method.value),
                settings_version=settings_version,
                algorithm_version=algorithm_version,
            )
            if not risk.available or risk.covariance is None:
                candidate = CandidateResult(method, aligned.listings, None, False, risk.reason or "risk_model_unavailable")
            else:
                candidate = build_candidate(
                    method=method,
                    listings=aligned.listings,
                    expected_returns=expected_returns,
                    covariance=risk.covariance,
                    scenarios=aligned.rows,
                    min_weight=min_weight,
                    max_weight=max_weight,
                )
            results.append(CandidatePipelineItem(configuration, risk, candidate))
    return tuple(sorted(results, key=lambda item: item.configuration.configuration_id))

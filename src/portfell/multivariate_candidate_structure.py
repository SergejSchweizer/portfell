"""Pure candidate PCA structural-risk diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite

from portfell.multivariate_candidates import PortfolioCandidate
from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_risk_model import MultivariateRiskModelArtifact
from portfell.multivariate_spectral import SpectralResult, analyze_symmetric_matrix

CONTRIBUTION_TOLERANCE = 1e-12


@dataclass(frozen=True)
class CandidatePcaContribution:
    candidate_id: str
    method: str
    component_id: str
    variance_contribution: float
    percent_portfolio_variance: float
    risk_model_id: str


@dataclass(frozen=True)
class CandidatePcaRisk:
    candidate_id: str
    method: str
    risk_model_id: str
    contributions: tuple[CandidatePcaContribution, ...]
    portfolio_variance: float | None
    availability_reasons: tuple[str, ...]

    @property
    def available(self) -> bool:
        return not self.availability_reasons


def build_candidate_pca_risk(
    *,
    candidate: PortfolioCandidate,
    risk_model: MultivariateRiskModelArtifact,
    spectral: SpectralResult | None = None,
) -> CandidatePcaRisk:
    """Project candidate weights onto the covariance-PCA basis without changing the candidate."""

    if candidate.status != "feasible" or candidate.reasons:
        return _unavailable(candidate, risk_model, "candidate_unavailable")
    if not risk_model.available or not risk_model.covariance:
        return _unavailable(candidate, risk_model, "risk_model_unavailable")
    weights, reason = _aligned_weights(candidate.weights, risk_model.listings)
    if reason is not None:
        return _unavailable(candidate, risk_model, reason)
    result = spectral or analyze_symmetric_matrix(risk_model.covariance)
    if not result.available:
        return _unavailable(candidate, risk_model, result.availability_reasons[0])
    portfolio_variance = _portfolio_variance(weights, risk_model.covariance)
    if not isfinite(portfolio_variance) or portfolio_variance <= 0.0:
        return _unavailable(candidate, risk_model, "candidate_pca_non_positive_variance")
    values: list[float] = []
    for eigenvalue, component in zip(result.eigenvalues, result.component_coefficients, strict=True):
        projection = sum(coefficient * weight for coefficient, weight in zip(component, weights, strict=True))
        contribution = eigenvalue * projection * projection
        if contribution < -CONTRIBUTION_TOLERANCE:
            return _unavailable(candidate, risk_model, "candidate_pca_negative_contribution")
        values.append(0.0 if contribution < 0.0 else contribution)
    total = sum(values)
    if not isclose(total, portfolio_variance, rel_tol=1e-9, abs_tol=1e-12):
        return _unavailable(candidate, risk_model, "candidate_pca_variance_mismatch")
    rows = tuple(
        CandidatePcaContribution(
            candidate_id=candidate.candidate_id,
            method=candidate.method,
            component_id=f"Component {index + 1}",
            variance_contribution=value,
            percent_portfolio_variance=value / portfolio_variance,
            risk_model_id=risk_model.risk_model_id,
        )
        for index, value in enumerate(values)
    )
    return CandidatePcaRisk(
        candidate.candidate_id,
        candidate.method,
        risk_model.risk_model_id,
        rows,
        portfolio_variance,
        (),
    )


def _aligned_weights(
    weights: tuple[tuple[MultivariateListingKey, float], ...],
    listings: tuple[MultivariateListingKey, ...],
) -> tuple[tuple[float, ...], str | None]:
    by_listing = {listing: weight for listing, weight in weights}
    if len(by_listing) != len(weights) or set(by_listing) != set(listings):
        return (), "candidate_identity_mismatch"
    aligned = tuple(by_listing[listing] for listing in listings)
    if any(not isfinite(value) for value in aligned):
        return (), "candidate_identity_mismatch"
    return aligned, None


def _portfolio_variance(
    weights: tuple[float, ...], covariance: tuple[tuple[float, ...], ...]
) -> float:
    return sum(
        weights[left] * covariance[left][right] * weights[right]
        for left in range(len(weights))
        for right in range(len(weights))
    )


def _unavailable(
    candidate: PortfolioCandidate,
    risk_model: MultivariateRiskModelArtifact,
    reason: str,
) -> CandidatePcaRisk:
    return CandidatePcaRisk(candidate.candidate_id, candidate.method, risk_model.risk_model_id, (), None, (reason,))


__all__ = ["CandidatePcaContribution", "CandidatePcaRisk", "build_candidate_pca_risk"]

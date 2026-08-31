"""Candidate effective PCA risk-driver diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite, log

from portfell.multivariate_candidate_structure import CandidatePcaRisk

RISK_THRESHOLDS = (0.80, 0.90, 0.95)


@dataclass(frozen=True)
class CandidatePcaRiskSummary:
    candidate_id: str
    method: str
    effective_pca_risk_drivers: float | None
    largest_pca_risk_share: float | None
    components_for_80pct_risk: int | None
    components_for_90pct_risk: int | None
    components_for_95pct_risk: int | None
    availability_reasons: tuple[str, ...]

    @property
    def available(self) -> bool:
        return not self.availability_reasons


def summarize_candidate_pca_risk(risk: CandidatePcaRisk) -> CandidatePcaRiskSummary:
    if not risk.available or risk.portfolio_variance is None:
        return _unavailable(
            risk,
            risk.availability_reasons or ("candidate_pca_non_positive_variance",),
        )
    total = sum(row.variance_contribution for row in risk.contributions)
    if not isfinite(total) or total <= 0.0:
        return _unavailable(risk, ("candidate_pca_non_positive_variance",))
    shares = tuple(row.variance_contribution / total for row in risk.contributions)
    if any(not isfinite(value) or value < 0.0 for value in shares):
        return _unavailable(risk, ("candidate_pca_non_positive_variance",))
    effective = exp(-sum(value * log(value) for value in shares if value > 0.0))
    ordered = sorted(
        ((share, row.component_id) for share, row in zip(shares, risk.contributions, strict=True)),
        key=lambda item: (-item[0], item[1]),
    )
    counts: dict[float, int] = {}
    for threshold in RISK_THRESHOLDS:
        running = 0.0
        for index, (share, _) in enumerate(ordered, start=1):
            running += share
            if running >= threshold:
                counts[threshold] = index
                break
    return CandidatePcaRiskSummary(
        candidate_id=risk.candidate_id,
        method=risk.method,
        effective_pca_risk_drivers=effective,
        largest_pca_risk_share=max(shares),
        components_for_80pct_risk=counts[0.80],
        components_for_90pct_risk=counts[0.90],
        components_for_95pct_risk=counts[0.95],
        availability_reasons=(),
    )


def _unavailable(risk: CandidatePcaRisk, reasons: tuple[str, ...]) -> CandidatePcaRiskSummary:
    return CandidatePcaRiskSummary(
        risk.candidate_id,
        risk.method,
        None,
        None,
        None,
        None,
        None,
        reasons,
    )


__all__ = ["CandidatePcaRiskSummary", "RISK_THRESHOLDS", "summarize_candidate_pca_risk"]

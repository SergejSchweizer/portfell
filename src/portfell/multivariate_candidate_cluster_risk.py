"""Pure candidate cluster-risk attribution for Multivariate Structure v2."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite

from portfell.multivariate_candidates import PortfolioCandidate
from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_risk_clusters import RiskClusterDiagnostics
from portfell.multivariate_risk_model import MultivariateRiskModelArtifact


@dataclass(frozen=True)
class CandidateClusterRiskRow:
    candidate_id: str
    method: str
    cluster_id: str
    member_count: int
    signed_variance_contribution: float
    signed_percent_variance: float
    gross_abs_risk_share: float
    risk_model_id: str


@dataclass(frozen=True)
class CandidateClusterRisk:
    candidate_id: str
    method: str
    risk_model_id: str
    rows: tuple[CandidateClusterRiskRow, ...]
    availability_reasons: tuple[str, ...]

    @property
    def available(self) -> bool:
        return not self.availability_reasons


def build_candidate_cluster_risk(
    *,
    candidate: PortfolioCandidate,
    risk_model: MultivariateRiskModelArtifact,
    clusters: RiskClusterDiagnostics,
) -> CandidateClusterRisk:
    if candidate.status != "feasible" or candidate.reasons:
        return _unavailable(candidate, risk_model, "candidate_unavailable")
    if not risk_model.available or not risk_model.covariance or not clusters.available:
        return _unavailable(candidate, risk_model, "clusters_unavailable")
    by_weight = {listing: weight for listing, weight in candidate.weights}
    if len(by_weight) != len(candidate.weights) or set(by_weight) != set(risk_model.listings):
        return _unavailable(candidate, risk_model, "candidate_identity_mismatch")
    membership = {row.listing: row.cluster_id for row in clusters.memberships}
    if set(membership) != set(risk_model.listings):
        return _unavailable(candidate, risk_model, "candidate_identity_mismatch")
    weights = tuple(by_weight[listing] for listing in risk_model.listings)
    marginal = tuple(
        sum(risk_model.covariance[index][right] * weights[right] for right in range(len(weights)))
        for index in range(len(weights))
    )
    asset_contributions = tuple(weights[index] * marginal[index] for index in range(len(weights)))
    if any(not isfinite(value) for value in asset_contributions):
        return _unavailable(candidate, risk_model, "candidate_cluster_variance_mismatch")
    portfolio_variance = sum(asset_contributions)
    if not isfinite(portfolio_variance) or portfolio_variance <= 0.0:
        return _unavailable(candidate, risk_model, "candidate_cluster_variance_mismatch")
    gross_denominator = sum(abs(value) for value in asset_contributions)
    if gross_denominator <= 0.0:
        return _unavailable(candidate, risk_model, "candidate_cluster_variance_mismatch")
    cluster_ids = tuple(sorted(set(membership.values()), key=_cluster_sort_key))
    rows: list[CandidateClusterRiskRow] = []
    for cluster_id in cluster_ids:
        indexes = tuple(
            index for index, listing in enumerate(risk_model.listings) if membership[listing] == cluster_id
        )
        signed = sum(asset_contributions[index] for index in indexes)
        gross = sum(abs(asset_contributions[index]) for index in indexes)
        rows.append(
            CandidateClusterRiskRow(
                candidate.candidate_id,
                candidate.method,
                cluster_id,
                len(indexes),
                signed,
                signed / portfolio_variance,
                gross / gross_denominator,
                risk_model.risk_model_id,
            )
        )
    if not isclose(sum(row.signed_variance_contribution for row in rows), portfolio_variance, rel_tol=1e-9, abs_tol=1e-12):
        return _unavailable(candidate, risk_model, "candidate_cluster_variance_mismatch")
    if not isclose(sum(row.signed_percent_variance for row in rows), 1.0, rel_tol=1e-9, abs_tol=1e-12):
        return _unavailable(candidate, risk_model, "candidate_cluster_variance_mismatch")
    if not isclose(sum(row.gross_abs_risk_share for row in rows), 1.0, rel_tol=1e-9, abs_tol=1e-12):
        return _unavailable(candidate, risk_model, "candidate_cluster_variance_mismatch")
    return CandidateClusterRisk(candidate.candidate_id, candidate.method, risk_model.risk_model_id, tuple(rows), ())


def _cluster_sort_key(cluster_id: str) -> tuple[int, str]:
    try:
        return int(cluster_id.rsplit(" ", 1)[1]), cluster_id
    except (IndexError, ValueError):
        return 2**31 - 1, cluster_id


def _unavailable(
    candidate: PortfolioCandidate, risk_model: MultivariateRiskModelArtifact, reason: str
) -> CandidateClusterRisk:
    return CandidateClusterRisk(candidate.candidate_id, candidate.method, risk_model.risk_model_id, (), (reason,))


__all__ = ["CandidateClusterRisk", "CandidateClusterRiskRow", "build_candidate_cluster_risk"]

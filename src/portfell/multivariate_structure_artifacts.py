"""Immutable Structure v2 artifact assembly for later application-service adoption."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from portfell.contract_versioning import ContractVersion, stable_contract_id
from portfell.multivariate_candidate_cluster_risk import build_candidate_cluster_risk
from portfell.multivariate_candidate_structure import build_candidate_pca_risk
from portfell.multivariate_candidate_structure_summary import summarize_candidate_pca_risk
from portfell.multivariate_candidates import PortfolioCandidate
from portfell.multivariate_cluster_stability import build_cluster_bootstrap_stability
from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_risk_clusters import (
    RiskClusterDiagnostics,
    build_hierarchical_risk_clusters,
)
from portfell.multivariate_risk_model import MultivariateRiskModelArtifact
from portfell.multivariate_rolling_structure import build_rolling_structure_diagnostics
from portfell.multivariate_signal_components import build_signal_component_diagnostics
from portfell.multivariate_structure_v2 import PcaDiagnostics, build_structure_pca_diagnostics
from portfell.table_io import JsonRow

STRUCTURE_V2_CONTRACT = ContractVersion("multivariate.structure", 2)
CANDIDATE_STRUCTURE_V1_CONTRACT = ContractVersion("multivariate.candidate_structure", 1)


@dataclass(frozen=True)
class StructureV2Documents:
    structure_id: str
    candidate_structure_id: str
    structure: JsonRow
    candidate_structure: JsonRow


def build_structure_v2_documents(
    *,
    risk_model: MultivariateRiskModelArtifact,
    return_rows: Sequence[Mapping[str, Any]],
    candidates: Sequence[PortfolioCandidate],
) -> StructureV2Documents:
    """Build canonical serializable documents without changing decision or candidate objects."""

    pca = build_structure_pca_diagnostics(risk_model)
    clusters = (
        build_hierarchical_risk_clusters(
            listings=risk_model.listings,
            correlation=pca.correlation_matrix,
        )
        if pca.correlation.available and pca.correlation_matrix
        else RiskClusterDiagnostics((), None, None, ("clusters_unavailable",))
    )
    signal = build_signal_component_diagnostics(
        return_rows=return_rows,
        listings=risk_model.listings,
    )
    rolling = build_rolling_structure_diagnostics(
        return_rows=return_rows,
        listings=risk_model.listings,
    )
    bootstrap = build_cluster_bootstrap_stability(
        return_rows=return_rows,
        listings=risk_model.listings,
        canonical_clusters=clusters,
    )
    structure_id = stable_contract_id(
        "multivariate_structure_v2",
        {
            "contract": STRUCTURE_V2_CONTRACT.qualified_name,
            "risk_model_id": risk_model.risk_model_id,
            "input_snapshot_id": risk_model.input_snapshot_id,
            "aligned_calendar_id": risk_model.aligned_calendar_id,
            "listing_keys": [key.as_tuple() for key in risk_model.listings],
            "explained_variance_thresholds": [0.80, 0.90, 0.95],
            "cluster_correlation_cut": 0.70,
            "parallel_analysis": {
                "replicates": 100,
                "seed": 41,
                "quantile": 0.95,
                "method": "higher",
            },
            "rolling": {"observations": 252, "stride": 21, "max_windows": 24},
            "subspace_components": min(3, len(risk_model.listings)),
            "cluster_bootstrap": {"replicates": 100, "block_length": 21, "seed": 41},
        },
    )
    candidate_ids = tuple(candidate.candidate_id for candidate in candidates)
    candidate_structure_id = stable_contract_id(
        "multivariate_candidate_structure_v1",
        {
            "contract": CANDIDATE_STRUCTURE_V1_CONTRACT.qualified_name,
            "structure_id": structure_id,
            "risk_model_id": risk_model.risk_model_id,
            "candidate_ids": list(candidate_ids),
        },
    )
    structure_document: JsonRow = {
        "contract_version": STRUCTURE_V2_CONTRACT.qualified_name,
        "structure_id": structure_id,
        "risk_model_id": risk_model.risk_model_id,
        "input_snapshot_id": risk_model.input_snapshot_id,
        "listing_count": len(risk_model.listings),
        "period": {
            "date_start": risk_model.date_start,
            "date_end": risk_model.date_end,
            "observation_count": risk_model.observation_count,
        },
        "covariance_pca": _pca_row(pca.covariance),
        "correlation_pca": _pca_row(pca.correlation),
        "signal_components": {
            "observed_eigenvalues": list(signal.observed_eigenvalues),
            "null_thresholds": list(signal.null_thresholds),
            "signal_component_count": signal.signal_component_count,
            "replicate_count": signal.replicate_count,
            "seed": signal.seed,
            "quantile": signal.quantile,
            "quantile_method": signal.quantile_method,
            "availability_reasons": list(signal.availability_reasons),
        },
        "risk_clusters": {
            "cluster_count": clusters.cluster_count,
            "memberships": [
                {
                    "isin": row.listing.isin,
                    "exchange": row.listing.exchange,
                    "code": row.listing.code,
                    "cluster_id": row.cluster_id,
                }
                for row in clusters.memberships
            ],
            "largest_redundancy_warning": (
                None
                if clusters.largest_redundancy_warning is None
                else {
                    "left": _listing_row(clusters.largest_redundancy_warning.left),
                    "right": _listing_row(clusters.largest_redundancy_warning.right),
                    "correlation": clusters.largest_redundancy_warning.correlation,
                }
            ),
            "availability_reasons": list(clusters.availability_reasons),
        },
        "rolling_structure": {
            "items": [
                {
                    "date_start": row.date_start,
                    "date_end": row.date_end,
                    "observation_count": row.observation_count,
                    "covariance_dominant_component_share": row.covariance_dominant_component_share,
                    "correlation_dominant_component_share": (
                        row.correlation_dominant_component_share
                    ),
                    "covariance_effective_rank": row.covariance_effective_rank,
                    "correlation_effective_rank": row.correlation_effective_rank,
                    "risk_cluster_count": row.risk_cluster_count,
                    "availability_reasons": list(row.availability_reasons),
                }
                for row in rolling.rows
            ],
            "availability_reasons": list(rolling.availability_reasons),
        },
        "subspace_stability": {
            "items": [],
            "availability_reasons": ["subspace_stability_adapter_pending"],
        },
        "cluster_bootstrap_stability": {
            "pairs": [
                {
                    "left": _listing_row(row.left),
                    "right": _listing_row(row.right),
                    "co_cluster_probability": row.co_cluster_probability,
                }
                for row in bootstrap.pairs
            ],
            "clusters": [
                {
                    "cluster_id": row.cluster_id,
                    "mean_co_cluster_probability": row.mean_co_cluster_probability,
                    "minimum_co_cluster_probability": row.minimum_co_cluster_probability,
                    "availability_reasons": list(row.availability_reasons),
                }
                for row in bootstrap.clusters
            ],
            "replicate_count": bootstrap.replicate_count,
            "block_length": bootstrap.block_length,
            "seed": bootstrap.seed,
            "availability_reasons": list(bootstrap.availability_reasons),
        },
    }
    candidate_rows: list[JsonRow] = []
    for candidate in candidates:
        pca_risk = build_candidate_pca_risk(candidate=candidate, risk_model=risk_model)
        summary = summarize_candidate_pca_risk(pca_risk)
        cluster_risk = build_candidate_cluster_risk(
            candidate=candidate,
            risk_model=risk_model,
            clusters=clusters,
        )
        candidate_rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "method": candidate.method,
                "availability_reasons": sorted(
                    set(
                        (
                            *pca_risk.availability_reasons,
                            *summary.availability_reasons,
                            *cluster_risk.availability_reasons,
                        )
                    )
                ),
                "effective_pca_risk_drivers": summary.effective_pca_risk_drivers,
                "largest_pca_risk_share": summary.largest_pca_risk_share,
                "components_for_80pct_risk": summary.components_for_80pct_risk,
                "components_for_90pct_risk": summary.components_for_90pct_risk,
                "components_for_95pct_risk": summary.components_for_95pct_risk,
                "pca_risk_contributions": [
                    {
                        "component_id": row.component_id,
                        "variance_contribution": row.variance_contribution,
                        "percent_portfolio_variance": row.percent_portfolio_variance,
                        "risk_model_id": row.risk_model_id,
                    }
                    for row in pca_risk.contributions
                ],
                "cluster_risk_contributions": [
                    {
                        "cluster_id": row.cluster_id,
                        "member_count": row.member_count,
                        "signed_variance_contribution": row.signed_variance_contribution,
                        "signed_percent_variance": row.signed_percent_variance,
                        "gross_abs_risk_share": row.gross_abs_risk_share,
                        "risk_model_id": row.risk_model_id,
                    }
                    for row in cluster_risk.rows
                ],
            }
        )
    candidate_document: JsonRow = {
        "contract_version": CANDIDATE_STRUCTURE_V1_CONTRACT.qualified_name,
        "candidate_structure_id": candidate_structure_id,
        "structure_id": structure_id,
        "risk_model_id": risk_model.risk_model_id,
        "candidate_ids": list(candidate_ids),
        "items": candidate_rows,
    }
    return StructureV2Documents(
        structure_id,
        candidate_structure_id,
        structure_document,
        candidate_document,
    )


def _pca_row(value: PcaDiagnostics) -> JsonRow:
    return {
        "eigenvalues": list(value.eigenvalues),
        "explained_variance": list(value.explained_variance),
        "cumulative_explained_variance": list(value.cumulative_explained_variance),
        "effective_rank": value.effective_rank,
        "components_for_80pct": value.components_for_80pct,
        "components_for_90pct": value.components_for_90pct,
        "components_for_95pct": value.components_for_95pct,
        "dominant_component_share": value.dominant_component_share,
        "dominant_component_representative": (
            None
            if value.dominant_component_representative is None
            else _listing_row(value.dominant_component_representative)
        ),
        "component_coefficients": [
            {
                "component_id": row.component_id,
                "isin": row.listing.isin,
                "exchange": row.listing.exchange,
                "code": row.listing.code,
                "coefficient": row.coefficient,
            }
            for row in value.coefficients
        ],
        "availability_reasons": list(value.availability_reasons),
    }


def _listing_row(listing: MultivariateListingKey) -> JsonRow:
    return {
        "isin": str(listing.isin),
        "exchange": str(listing.exchange),
        "code": str(listing.code),
    }


__all__ = [
    "CANDIDATE_STRUCTURE_V1_CONTRACT",
    "STRUCTURE_V2_CONTRACT",
    "StructureV2Documents",
    "build_structure_v2_documents",
]

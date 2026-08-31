"""Presentation-only adapters for persisted Multivariate Structure v2 universe evidence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from portfell.table_io import JsonRow

UNIVERSE_STRUCTURE_CARD_TITLES = (
    "PCA Spectrum",
    "Structural Diversification",
    "Risk Clusters",
    "Structural Stability",
)


def universe_structure_view(document: Mapping[str, Any]) -> JsonRow:
    """Build Dash-ready view data without financial recomputation."""

    covariance = _mapping(document.get("covariance_pca"))
    correlation = _mapping(document.get("correlation_pca"))
    clusters = _mapping(document.get("risk_clusters"))
    signal = _mapping(document.get("signal_components"))
    rolling = _mapping(document.get("rolling_structure"))
    bootstrap = _mapping(document.get("cluster_bootstrap_stability"))
    subspace = _mapping(document.get("subspace_stability"))
    cluster_stability = {
        str(item.get("cluster_id", "")): item for item in _dict_rows(bootstrap.get("clusters"))
    }
    cluster_rows: list[JsonRow] = []
    for membership in _dict_rows(clusters.get("memberships")):
        stability = _mapping(cluster_stability.get(str(membership.get("cluster_id", ""))))
        cluster_rows.append(
            {
                "isin": membership.get("isin"),
                "exchange": membership.get("exchange"),
                "code": membership.get("code"),
                "cluster_id": membership.get("cluster_id"),
                "mean_co_cluster_probability": stability.get("mean_co_cluster_probability"),
                "minimum_co_cluster_probability": stability.get("minimum_co_cluster_probability"),
                "stability_availability_reasons": stability.get("availability_reasons", []),
            }
        )
    return {
        "cards": list(UNIVERSE_STRUCTURE_CARD_TITLES),
        "pca_spectrum": {
            "covariance": {
                "explained_variance": covariance.get("explained_variance", []),
                "availability_reasons": covariance.get("availability_reasons", []),
            },
            "correlation": {
                "explained_variance": correlation.get("explained_variance", []),
                "availability_reasons": correlation.get("availability_reasons", []),
            },
        },
        "structural_diversification": {
            "listing_count": document.get("listing_count"),
            "covariance_effective_rank": covariance.get("effective_rank"),
            "correlation_effective_rank": correlation.get("effective_rank"),
            "signal_component_count": signal.get("signal_component_count"),
            "covariance_dominant_component_share": covariance.get("dominant_component_share"),
            "correlation_dominant_component_share": correlation.get("dominant_component_share"),
            "covariance_components_for_80pct": covariance.get("components_for_80pct"),
            "covariance_components_for_90pct": covariance.get("components_for_90pct"),
            "covariance_components_for_95pct": covariance.get("components_for_95pct"),
            "correlation_components_for_80pct": correlation.get("components_for_80pct"),
            "correlation_components_for_90pct": correlation.get("components_for_90pct"),
            "correlation_components_for_95pct": correlation.get("components_for_95pct"),
            "risk_cluster_count": clusters.get("cluster_count"),
        },
        "risk_clusters": cluster_rows,
        "structural_stability": {
            "rolling": rolling.get("items", []),
            "rolling_availability_reasons": rolling.get("availability_reasons", []),
            "subspace": subspace.get("items", []),
            "subspace_availability_reasons": subspace.get("availability_reasons", []),
        },
    }


def _mapping(value: object) -> Mapping[str, Any]:
    return cast(Mapping[str, Any], value) if isinstance(value, Mapping) else {}


def _dict_rows(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    values = cast(list[object], value)
    return tuple(cast(Mapping[str, Any], item) for item in values if isinstance(item, Mapping))


__all__ = ["UNIVERSE_STRUCTURE_CARD_TITLES", "universe_structure_view"]

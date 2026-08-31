from portfell.dash_app.structure_presenters import (
    UNIVERSE_STRUCTURE_CARD_TITLES,
    universe_structure_view,
)


def test_universe_structure_cards_and_fields_are_presentation_only() -> None:
    document = {
        "listing_count": 3,
        "covariance_pca": {
            "explained_variance": [0.6, 0.3, 0.1],
            "effective_rank": 2.2,
            "dominant_component_share": 0.6,
            "components_for_80pct": 2,
            "components_for_90pct": 2,
            "components_for_95pct": 3,
            "availability_reasons": [],
        },
        "correlation_pca": {
            "explained_variance": [0.5, 0.3, 0.2],
            "effective_rank": 2.8,
            "dominant_component_share": 0.5,
            "components_for_80pct": 2,
            "components_for_90pct": 3,
            "components_for_95pct": 3,
            "availability_reasons": [],
        },
        "signal_components": {"signal_component_count": 2},
        "risk_clusters": {
            "cluster_count": 2,
            "memberships": [
                {
                    "isin": "IE1",
                    "exchange": "X",
                    "code": "A",
                    "cluster_id": "Cluster 1",
                }
            ],
        },
        "rolling_structure": {
            "items": [
                {
                    "date_end": "2025-01-31",
                    "covariance_effective_rank": 2.0,
                }
            ],
            "availability_reasons": [],
        },
        "subspace_stability": {"items": [], "availability_reasons": ["pending"]},
        "cluster_bootstrap_stability": {
            "clusters": [
                {
                    "cluster_id": "Cluster 1",
                    "mean_co_cluster_probability": 0.9,
                    "minimum_co_cluster_probability": 0.8,
                    "availability_reasons": [],
                }
            ]
        },
    }
    view = universe_structure_view(document)
    assert tuple(view["cards"]) == UNIVERSE_STRUCTURE_CARD_TITLES
    assert view["structural_diversification"]["covariance_effective_rank"] == 2.2
    assert view["structural_diversification"]["signal_component_count"] == 2
    assert view["risk_clusters"][0]["mean_co_cluster_probability"] == 0.9
    assert view["structural_stability"]["subspace_availability_reasons"] == ["pending"]


def test_missing_sections_remain_unavailable_not_recomputed() -> None:
    view = universe_structure_view({"listing_count": 2})
    assert view["pca_spectrum"]["covariance"]["explained_variance"] == []
    assert view["structural_diversification"]["covariance_effective_rank"] is None
    assert view["risk_clusters"] == []

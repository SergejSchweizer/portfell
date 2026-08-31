from portfell.dash_app.candidate_structure_presenters import (
    CANDIDATE_STRUCTURE_CARD_TITLES,
    candidate_structure_view,
)


def _document() -> dict[str, object]:
    return {
        "items": [
            {
                "candidate_id": "c1",
                "method": "equal_weight",
                "effective_pca_risk_drivers": 2.4,
                "largest_pca_risk_share": 0.45,
                "components_for_80pct_risk": 3,
                "components_for_90pct_risk": 4,
                "components_for_95pct_risk": 5,
                "largest_cluster_gross_abs_risk_share": 0.61,
                "availability_reasons": [],
                "pca_risk_contributions": [
                    {"component_id": "Component 1", "percent_portfolio_variance": 0.45}
                ],
                "cluster_risk_contributions": [
                    {
                        "cluster_id": "Cluster 1",
                        "signed_percent_variance": -0.10,
                        "gross_abs_risk_share": 0.30,
                    }
                ],
            },
            {
                "candidate_id": "c2",
                "method": "minimum_variance",
                "effective_pca_risk_drivers": None,
                "availability_reasons": ["candidate_unavailable"],
                "pca_risk_contributions": [],
                "cluster_risk_contributions": [],
            },
        ]
    }


def test_candidate_cards_and_default_winner_are_presentation_only() -> None:
    view = candidate_structure_view(_document(), persisted_winning_candidate_id="c1")
    assert tuple(view["cards"]) == CANDIDATE_STRUCTURE_CARD_TITLES
    assert view["candidate_selector"]["selected_candidate_id"] == "c1"
    assert view["candidate_structural_risk"][0]["largest_cluster_gross_abs_risk_share"] == 0.61
    assert view["pca_risk_contribution"] == [
        {"component_id": "Component 1", "percent_portfolio_variance": 0.45}
    ]


def test_signed_negative_cluster_contribution_is_preserved() -> None:
    view = candidate_structure_view(_document(), selected_candidate_id="c1")
    assert view["cluster_risk_contribution"][0]["signed_percent_variance"] == -0.10
    assert view["cluster_risk_contribution"][0]["gross_abs_risk_share"] == 0.30


def test_selector_falls_back_to_first_persisted_candidate_and_keeps_unavailable_rows() -> None:
    view = candidate_structure_view(
        _document(), persisted_winning_candidate_id="missing", selected_candidate_id="missing"
    )
    assert view["candidate_selector"]["options"] == ["c1", "c2"]
    assert view["candidate_selector"]["selected_candidate_id"] == "c1"
    assert view["candidate_structural_risk"][1]["availability_reasons"] == ["candidate_unavailable"]


def test_presenter_does_not_derive_missing_cluster_summary() -> None:
    document = _document()
    items = document["items"]
    assert isinstance(items, list)
    first = items[0]
    assert isinstance(first, dict)
    first.pop("largest_cluster_gross_abs_risk_share")
    view = candidate_structure_view(document, selected_candidate_id="c1")
    assert view["candidate_structural_risk"][0]["largest_cluster_gross_abs_risk_share"] is None

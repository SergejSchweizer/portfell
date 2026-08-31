"""Presentation-only adapters for persisted candidate structural-risk evidence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from portfell.table_io import JsonRow

CANDIDATE_STRUCTURE_CARD_TITLES = (
    "Candidate Structural Risk",
    "PCA Risk Contribution",
    "Cluster Risk Contribution",
)


def candidate_structure_view(
    document: Mapping[str, Any],
    *,
    persisted_winning_candidate_id: str | None = None,
    selected_candidate_id: str | None = None,
) -> JsonRow:
    """Format/select persisted candidate-structure rows without analytical recomputation."""

    items = _dict_rows(document.get("items"))
    candidate_ids = tuple(
        str(item.get("candidate_id", "")) for item in items if item.get("candidate_id")
    )
    selected = _resolve_selected_candidate(
        candidate_ids,
        persisted_winning_candidate_id=persisted_winning_candidate_id,
        selected_candidate_id=selected_candidate_id,
    )
    by_id = {str(item.get("candidate_id", "")): item for item in items}
    selected_row = _mapping(by_id.get(selected or ""))
    table_rows = [
        {
            "candidate_id": item.get("candidate_id"),
            "method": item.get("method"),
            "effective_pca_risk_drivers": item.get("effective_pca_risk_drivers"),
            "largest_pca_risk_share": item.get("largest_pca_risk_share"),
            "components_for_80pct_risk": item.get("components_for_80pct_risk"),
            "components_for_90pct_risk": item.get("components_for_90pct_risk"),
            "components_for_95pct_risk": item.get("components_for_95pct_risk"),
            # This summary MUST be persisted by the analytical artifact. The Dash
            # adapter deliberately does not derive max() from cluster rows.
            "largest_cluster_gross_abs_risk_share": item.get(
                "largest_cluster_gross_abs_risk_share"
            ),
            "availability_reasons": item.get("availability_reasons", []),
        }
        for item in items
    ]
    return {
        "cards": list(CANDIDATE_STRUCTURE_CARD_TITLES),
        "candidate_selector": {
            "options": list(candidate_ids),
            "selected_candidate_id": selected,
            "persisted_winning_candidate_id": persisted_winning_candidate_id,
        },
        "candidate_structural_risk": table_rows,
        "pca_risk_contribution": [
            {
                "component_id": row.get("component_id"),
                "percent_portfolio_variance": row.get("percent_portfolio_variance"),
            }
            for row in _dict_rows(selected_row.get("pca_risk_contributions"))
        ],
        "cluster_risk_contribution": [
            {
                "cluster_id": row.get("cluster_id"),
                "signed_percent_variance": row.get("signed_percent_variance"),
                "gross_abs_risk_share": row.get("gross_abs_risk_share"),
            }
            for row in _dict_rows(selected_row.get("cluster_risk_contributions"))
        ],
        "selected_candidate_availability_reasons": selected_row.get("availability_reasons", []),
    }


def _resolve_selected_candidate(
    candidate_ids: tuple[str, ...],
    *,
    persisted_winning_candidate_id: str | None,
    selected_candidate_id: str | None,
) -> str | None:
    if selected_candidate_id in candidate_ids:
        return selected_candidate_id
    if persisted_winning_candidate_id in candidate_ids:
        return persisted_winning_candidate_id
    return candidate_ids[0] if candidate_ids else None


def _mapping(value: object) -> Mapping[str, Any]:
    return cast(Mapping[str, Any], value) if isinstance(value, Mapping) else {}


def _dict_rows(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    values = cast(list[object], value)
    return tuple(cast(Mapping[str, Any], item) for item in values if isinstance(item, Mapping))


__all__ = ["CANDIDATE_STRUCTURE_CARD_TITLES", "candidate_structure_view"]

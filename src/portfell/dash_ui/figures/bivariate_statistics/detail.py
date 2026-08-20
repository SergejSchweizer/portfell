"""Bivariate detail and pair-history figures."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from portfell.dash_ui.figures.bivariate_statistics.models import PairHistoryPoint

DETAIL_TITLES: dict[str, str] = {
    "covariance": "Covariance",
    "pearson": "Pearson",
    "spearman": "Spearman",
    "downside": "Downside",
    "tail_dependence": "Tail Dependence",
    "co_exceedance": "Co-exceedance",
    "rolling_correlation": "Rolling-Correlation",
    "drawdown_overlap": "Drawdown Overlap",
    "tail_risk_scatter": "Tail-Risk Scatter",
}


def detail_matrix_figure(
    *, view_id: str, labels: Sequence[str], matrix: Sequence[Sequence[float | None]]
) -> dict[str, object]:
    """Render a deterministic authorized matrix; no pair statistic is computed here."""

    if view_id not in DETAIL_TITLES:
        raise ValueError(f"unknown Bivariate view: {view_id}")
    if len(matrix) != len(labels) or any(len(row) != len(labels) for row in matrix):
        raise ValueError("matrix shape must match labels")
    return {
        "data": [
            {
                "type": "heatmap",
                "x": list(labels),
                "y": list(labels),
                "z": [list(row) for row in matrix],
                "hovertemplate": "%{x} / %{y}<br>value=%{z}<extra></extra>",
            }
        ],
        "layout": {
            "title": DETAIL_TITLES[view_id],
            "xaxis": {"title": "Listing"},
            "yaxis": {"title": "Listing"},
            "uirevision": f"bivariate-detail-{view_id}-v1",
        },
    }


def pair_history_figure(rows: Iterable[PairHistoryPoint]) -> dict[str, object]:
    """Render exact pairwise shared-history evidence and preserve unavailable pairs."""

    ordered = tuple(sorted(rows, key=lambda row: row.pair_id))
    available = [row for row in ordered if row.shared_observations is not None]
    unavailable = [row.pair_id for row in ordered if row.shared_observations is None]
    return {
        "data": [
            {
                "type": "histogram",
                "name": "Shared observations",
                "x": [row.shared_observations for row in available],
                "text": [row.pair_id for row in available],
                "hovertemplate": "shared observations=%{x}<extra></extra>",
            }
        ],
        "layout": {
            "title": "Pairwise Shared-History Distribution",
            "xaxis": {"title": "Shared observations"},
            "yaxis": {"title": "Pair count"},
            "meta": {"pair_count": len(ordered), "unavailable_pair_ids": unavailable},
            "uirevision": "bivariate-pair-history-v1",
        },
    }

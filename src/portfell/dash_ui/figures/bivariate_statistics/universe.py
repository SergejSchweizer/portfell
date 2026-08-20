"""Bivariate Return / Diversification Universe figure."""

from __future__ import annotations

from collections.abc import Iterable

from portfell.dash_ui.figures.bivariate_statistics.models import BivariateUniversePoint

METRIC_LABELS: dict[str, str] = {
    "median_pearson": "Median Pearson correlation",
    "median_spearman": "Median Spearman correlation",
    "median_downside": "Median downside correlation",
    "median_lower_tail": "Median lower-tail dependence",
    "median_co_exceedance": "Median co-exceedance",
    "median_drawdown_overlap": "Median drawdown overlap",
}


def diversification_figure(
    points: Iterable[BivariateUniversePoint], *, metric_id: str = "median_pearson"
) -> dict[str, object]:
    """Build one Plotly-compatible scatter from server-produced medians."""

    if metric_id not in METRIC_LABELS:
        raise ValueError(f"unknown dependence metric: {metric_id}")
    ordered = tuple(sorted(points, key=lambda point: point.listing_id))
    available = [point for point in ordered if point.metric(metric_id) is not None]
    unavailable = [point.listing_id for point in ordered if point.metric(metric_id) is None]
    return {
        "data": [
            {
                "type": "scattergl",
                "mode": "markers",
                "name": METRIC_LABELS[metric_id],
                "x": [point.metric(metric_id) for point in available],
                "y": [point.annualized_geometric_return for point in available],
                "text": [point.listing_id for point in available],
                "customdata": [
                    [
                        point.usable_pair_count,
                        point.median_pearson,
                        point.median_spearman,
                        point.median_downside,
                        point.median_lower_tail,
                        point.median_co_exceedance,
                        point.median_drawdown_overlap,
                    ]
                    for point in available
                ],
                "hovertemplate": "%{text}<br>dependence=%{x}<br>return=%{y}<extra></extra>",
            }
        ],
        "layout": {
            "title": "Bivariate Return / Diversification Universe",
            "xaxis": {"title": METRIC_LABELS[metric_id]},
            "yaxis": {"title": "Annualized geometric return (% p.a.)"},
            "meta": {"unavailable_listing_ids": unavailable},
            "uirevision": f"bivariate-diversification-{metric_id}-v1",
        },
    }

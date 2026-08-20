"""Univariate listing-history coverage figure."""

from __future__ import annotations

from collections.abc import Iterable

from portfell.dash_ui.figures.univariate_statistics.models import ListingHistory


def listing_history_figure(rows: Iterable[ListingHistory]) -> dict[str, object]:
    """Render server-provided observation counts without treating unavailable as zero."""

    ordered = tuple(sorted(rows, key=lambda row: row.listing_id))
    available = [row for row in ordered if row.observation_count is not None]
    unavailable = [row.listing_id for row in ordered if row.observation_count is None]
    return {
        "data": [
            {
                "type": "bar",
                "name": "Observed history",
                "x": [row.listing_id for row in available],
                "y": [row.observation_count for row in available],
                "customdata": [[row.first_date, row.last_date] for row in available],
                "hovertemplate": "%{x}<br>observations=%{y}<br>%{customdata[0]} → %{customdata[1]}<extra></extra>",
            }
        ],
        "layout": {
            "title": "Univariate Listing History Coverage",
            "xaxis": {"title": "Listing identity"},
            "yaxis": {"title": "Observations"},
            "meta": {"unavailable_listing_ids": unavailable},
            "uirevision": "univariate-listing-history-v1",
        },
    }

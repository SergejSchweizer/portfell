"""Walk-forward and aligned-history evidence figures."""

from __future__ import annotations

from collections.abc import Iterable

from portfell.dash_ui.figures.multivariate_statistics.models import WalkForwardView


def walk_forward_history_figure(rows: Iterable[WalkForwardView]) -> dict[str, object]:
    """Render exact persisted train/test ranges without deriving calendars from raw series."""

    ordered = tuple(sorted(rows, key=lambda row: row.split_id))
    traces: list[dict[str, object]] = []
    traces.append(
        {
            "type": "bar",
            "name": "Training observations",
            "x": [row.split_id for row in ordered],
            "y": [row.training_observations for row in ordered],
            "customdata": [[row.training_first, row.training_last] for row in ordered],
            "hovertemplate": "%{x}<br>training=%{y}<br>%{customdata[0]} → %{customdata[1]}<extra></extra>",
        }
    )
    traces.append(
        {
            "type": "bar",
            "name": "Test observations",
            "x": [row.split_id for row in ordered],
            "y": [row.test_observations for row in ordered],
            "customdata": [[row.test_first, row.test_last] for row in ordered],
            "hovertemplate": "%{x}<br>test=%{y}<br>%{customdata[0]} → %{customdata[1]}<extra></extra>",
        }
    )
    return {
        "data": traces,
        "layout": {
            "title": "Walk-Forward Training / Test Coverage",
            "barmode": "group",
            "xaxis": {"title": "Walk-forward split"},
            "yaxis": {"title": "Observations"},
            "uirevision": "multivariate-walk-forward-history-v1",
        },
    }

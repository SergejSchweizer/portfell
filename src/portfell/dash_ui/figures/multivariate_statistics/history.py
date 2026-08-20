"""Walk-forward and persisted Multivariate history evidence figures."""

from __future__ import annotations

from collections.abc import Iterable

from portfell.dash_ui.figures.multivariate_statistics.models import (
    PersistedHistoryRangeView,
    WalkForwardView,
)


def _history_range_figure(
    rows: Iterable[PersistedHistoryRangeView],
    *,
    title: str,
    revision: str,
) -> dict[str, object]:
    ordered = tuple(sorted(rows, key=lambda row: row.evidence_id))
    available = [row for row in ordered if row.observation_count is not None]
    unavailable = [
        {"evidence_id": row.evidence_id, "status": row.status, "reason": row.reason}
        for row in ordered
        if row.observation_count is None
    ]
    return {
        "data": [
            {
                "type": "bar",
                "name": "Persisted observations",
                "x": [row.evidence_id for row in available],
                "y": [row.observation_count for row in available],
                "customdata": [[row.first_date, row.last_date] for row in available],
                "hovertemplate": (
                    "%{x}<br>observations=%{y}<br>"
                    "%{customdata[0]} → %{customdata[1]}<extra></extra>"
                ),
            }
        ],
        "layout": {
            "title": title,
            "xaxis": {"title": "Persisted evidence"},
            "yaxis": {"title": "Observations"},
            "meta": {"unavailable": unavailable},
            "uirevision": revision,
        },
    }


def risk_model_history_figure(
    rows: Iterable[PersistedHistoryRangeView],
) -> dict[str, object]:
    """Render aligned risk-model training-history evidence from persisted snapshots."""

    return _history_range_figure(
        rows,
        title="Aligned Risk-Model History",
        revision="multivariate-risk-model-history-v1",
    )


def reduction_history_figure(
    rows: Iterable[PersistedHistoryRangeView],
) -> dict[str, object]:
    """Render before/after optimizer-universe history evidence."""

    return _history_range_figure(
        rows,
        title="Multivariate Reduction History",
        revision="multivariate-reduction-history-v1",
    )


def final_refit_history_figure(
    rows: Iterable[PersistedHistoryRangeView],
) -> dict[str, object]:
    """Render exact final-refit common-history evidence."""

    return _history_range_figure(
        rows,
        title="Final Portfolio Refit History",
        revision="multivariate-final-refit-history-v1",
    )


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
            "hovertemplate": (
                "%{x}<br>training=%{y}<br>"
                "%{customdata[0]} → %{customdata[1]}<extra></extra>"
            ),
        }
    )
    traces.append(
        {
            "type": "bar",
            "name": "Test observations",
            "x": [row.split_id for row in ordered],
            "y": [row.test_observations for row in ordered],
            "customdata": [[row.test_first, row.test_last] for row in ordered],
            "hovertemplate": (
                "%{x}<br>test=%{y}<br>"
                "%{customdata[0]} → %{customdata[1]}<extra></extra>"
            ),
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

"""Shared Plotly figure grammar for the Portfell Dash application."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import plotly.graph_objects as go

PORTFELL_CATEGORICAL_PALETTE = (
    "#2f80ed",
    "#5b8def",
    "#7a6ff0",
    "#3b9c9c",
    "#8a94a6",
    "#5f6b7a",
)

PORTFELL_FIGURE_LAYOUT: dict[str, Any] = {
    "font": {
        "family": 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        "color": "#172033",
    },
    "paper_bgcolor": "#ffffff",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "margin": {"l": 56, "r": 24, "t": 32, "b": 48},
    "hovermode": "closest",
    "hoverlabel": {"bgcolor": "#ffffff", "bordercolor": "#e3e8ef", "font": {"color": "#172033"}},
    "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1.0},
    "colorway": list(PORTFELL_CATEGORICAL_PALETTE),
    "xaxis": {
        "gridcolor": "#e3e8ef",
        "zerolinecolor": "#e3e8ef",
        "linecolor": "#e3e8ef",
        "automargin": True,
        "showline": True,
    },
    "yaxis": {
        "gridcolor": "#e3e8ef",
        "zerolinecolor": "#e3e8ef",
        "linecolor": "#e3e8ef",
        "automargin": True,
        "showline": True,
    },
}


def apply_portfell_template(
    figure: go.Figure, *, x_title: str | None = None, y_title: str | None = None
) -> go.Figure:
    """Apply the deterministic shared layout without changing financial values."""
    figure.update_layout(**PORTFELL_FIGURE_LAYOUT)
    if x_title is not None:
        figure.update_xaxes(title_text=x_title)
    if y_title is not None:
        figure.update_yaxes(title_text=y_title)
    return figure


def figure_from_rows(
    rows: list[Mapping[str, object]], *, x: str, y: str, name: str, x_title: str, y_title: str
) -> go.Figure:
    """Build one presentation-only scatter from already-computed backend values."""
    figure = go.Figure(
        data=[
            go.Scatter(
                x=[row.get(x) for row in rows],
                y=[row.get(y) for row in rows],
                mode="markers",
                name=name,
            )
        ]
    )
    return apply_portfell_template(figure, x_title=x_title, y_title=y_title)


__all__ = [
    "PORTFELL_CATEGORICAL_PALETTE",
    "PORTFELL_FIGURE_LAYOUT",
    "apply_portfell_template",
    "figure_from_rows",
]

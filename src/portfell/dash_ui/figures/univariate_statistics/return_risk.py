"""Professional Univariate Return / Risk Universe figure."""

from __future__ import annotations

from collections.abc import Iterable

from portfell.dash_ui.figures.univariate_statistics.models import UnivariatePoint, UniversePointState


def _pareto_frontier(points: Iterable[UnivariatePoint]) -> tuple[UnivariatePoint, ...]:
    eligible = sorted(
        (point for point in points if point.state is not UniversePointState.DATA_QUALITY_EXCLUDED),
        key=lambda point: (point.annualized_volatility, -point.annualized_geometric_return, point.listing_id),
    )
    frontier: list[UnivariatePoint] = []
    best_return = float("-inf")
    for point in eligible:
        if point.annualized_geometric_return > best_return:
            frontier.append(point)
            best_return = point.annualized_geometric_return
    return tuple(frontier)


def return_risk_figure(points: Iterable[UnivariatePoint], *, show_rejected: bool = True) -> dict[str, object]:
    """Build deterministic Plotly-compatible evidence from server-produced metrics."""

    ordered = tuple(sorted(points, key=lambda point: point.listing_id))
    traces: list[dict[str, object]] = []
    for state in UniversePointState:
        if state is UniversePointState.REJECTED_BY_SELECTION and not show_rejected:
            continue
        group = [point for point in ordered if point.state is state]
        if not group:
            continue
        traces.append(
            {
                "type": "scattergl",
                "mode": "markers",
                "name": state.value,
                "x": [point.annualized_volatility for point in group],
                "y": [point.annualized_geometric_return for point in group],
                "text": [point.listing_id for point in group],
                "customdata": [
                    [
                        point.sharpe,
                        point.sortino,
                        point.expected_shortfall,
                        point.maximum_drawdown,
                        point.distribution_frequency,
                        point.annual_dividend_yield,
                        point.observation_count,
                    ]
                    for point in group
                ],
                "hovertemplate": "%{text}<br>Volatility=%{x}<br>Return=%{y}<extra></extra>",
            }
        )
    frontier = _pareto_frontier(ordered)
    if frontier:
        traces.append(
            {
                "type": "scatter",
                "mode": "lines+markers",
                "name": "Pareto frontier",
                "x": [point.annualized_volatility for point in frontier],
                "y": [point.annualized_geometric_return for point in frontier],
                "text": [point.listing_id for point in frontier],
                "hovertemplate": "%{text}<extra></extra>",
            }
        )
    return {
        "data": traces,
        "layout": {
            "title": "Univariate Return / Risk Universe",
            "xaxis": {"title": "Annualized volatility (% p.a.)"},
            "yaxis": {"title": "Annualized geometric return (% p.a.)"},
            "legend": {"title": {"text": "Universe state"}},
            "uirevision": "univariate-return-risk-v1",
        },
    }

"""Portfolio Candidate OOS Return / Risk figure."""

from __future__ import annotations

from collections.abc import Iterable

from portfell.dash_ui.figures.multivariate_statistics.models import PortfolioCandidatePoint


def candidate_return_risk_figure(points: Iterable[PortfolioCandidatePoint]) -> dict[str, object]:
    """Render persisted OOS candidate evidence; unavailable points remain explicit metadata."""

    ordered = tuple(sorted(points, key=lambda point: point.configuration_id))
    available = [
        point
        for point in ordered
        if point.annualized_oos_return is not None and point.oos_annualized_volatility is not None
    ]
    unavailable = [
        point.configuration_id
        for point in ordered
        if point.annualized_oos_return is None or point.oos_annualized_volatility is None
    ]
    return {
        "data": [
            {
                "type": "scattergl",
                "mode": "markers",
                "name": "Candidates",
                "x": [point.oos_annualized_volatility for point in available],
                "y": [point.annualized_oos_return for point in available],
                "text": [point.configuration_id for point in available],
                "customdata": [
                    [point.method, point.risk_model, point.objective_value, point.winner]
                    for point in available
                ],
                "hovertemplate": "%{text}<br>OOS volatility=%{x}<br>OOS return=%{y}<br>method=%{customdata[0]}<br>risk=%{customdata[1]}<extra></extra>",
            }
        ],
        "layout": {
            "title": "Portfolio Candidate OOS Return / Risk",
            "xaxis": {"title": "OOS annualized volatility (% p.a.)"},
            "yaxis": {"title": "OOS annualized return (% p.a.)"},
            "meta": {"unavailable_configuration_ids": unavailable},
            "uirevision": "multivariate-candidate-return-risk-v1",
        },
    }

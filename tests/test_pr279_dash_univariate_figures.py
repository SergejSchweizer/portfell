from __future__ import annotations

from portfell.dash_ui.figures.univariate_statistics.history import listing_history_figure
from portfell.dash_ui.figures.univariate_statistics.models import (
    ListingHistory,
    UnivariatePoint,
    UniversePointState,
)
from portfell.dash_ui.figures.univariate_statistics.return_risk import return_risk_figure


def _point(
    isin: str,
    exchange: str,
    code: str,
    volatility: float,
    annual_return: float,
    state: UniversePointState = UniversePointState.SELECTED,
) -> UnivariatePoint:
    return UnivariatePoint(
        isin=isin,
        exchange=exchange,
        code=code,
        annualized_volatility=volatility,
        annualized_geometric_return=annual_return,
        sharpe=1.0,
        sortino=1.2,
        expected_shortfall=-0.03,
        maximum_drawdown=-0.1,
        distribution_frequency="quarterly",
        annual_dividend_yield=0.02,
        observation_count=252,
        state=state,
    )


def test_pr279_return_risk_figure_preserves_full_listing_identity_and_order() -> None:
    points = (
        _point("DUPLICATE", "XETRA", "AAA", 0.12, 0.08),
        _point("DUPLICATE", "LSE", "BBB", 0.10, 0.07),
    )
    forward = return_risk_figure(points)
    reverse = return_risk_figure(reversed(points))
    assert forward == reverse
    marker_text = [text for trace in forward["data"] for text in trace.get("text", [])]
    assert "DUPLICATE|XETRA|AAA" in marker_text
    assert "DUPLICATE|LSE|BBB" in marker_text
    assert forward["layout"]["title"] == "Univariate Return / Risk Universe"


def test_pr279_equal_tie_frontier_is_deterministic() -> None:
    points = (
        _point("B", "X", "B", 0.10, 0.08),
        _point("A", "X", "A", 0.10, 0.08),
        _point("C", "X", "C", 0.12, 0.09),
    )
    figure = return_risk_figure(points)
    frontier = next(trace for trace in figure["data"] if trace["name"] == "Pareto frontier")
    assert frontier["text"] == ["A|X|A", "C|X|C"]


def test_pr279_history_summary_ignores_unavailable_instead_of_inventing_zero() -> None:
    rows = (
        ListingHistory("A", "X", "A", "2020-01-01", "2024-01-01", 100),
        ListingHistory("B", "X", "B", "2021-01-01", "2024-01-01", 200),
        ListingHistory("C", "X", "C", None, None, None),
        ListingHistory("D", "X", "D", "2022-01-01", "2024-01-01", 300),
    )
    figure = listing_history_figure(rows)
    meta = figure["layout"]["meta"]
    assert meta["history_summary"] == {
        "minimum_observations": 100,
        "median_observations": 200.0,
        "maximum_observations": 300,
    }
    assert meta["unavailable_listing_ids"] == ["C|X|C"]
    assert figure["data"][0]["y"] == [100, 200, 300]


def test_pr279_large_fixture_keeps_stable_listing_order() -> None:
    points = tuple(
        _point(f"ISIN-{index:04d}", "XETRA", f"C{index:04d}", 0.1 + index / 10000, 0.05)
        for index in range(500)
    )
    figure = return_risk_figure(reversed(points))
    selected = next(trace for trace in figure["data"] if trace["name"] == "selected")
    assert selected["text"][0] == "ISIN-0000|XETRA|C0000"
    assert selected["text"][-1] == "ISIN-0499|XETRA|C0499"

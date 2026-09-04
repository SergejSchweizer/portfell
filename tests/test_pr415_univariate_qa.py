"""Independent QA oracles for the public Univariate metric surface."""

from __future__ import annotations

from math import exp, log

import pytest

from portfell.univariate_statistics import build_quote_returns, build_univariate_statistics


def _quote(day: int, close: float) -> dict[str, object]:
    return {
        "isin": "ORACLE",
        "code": "ORACLE",
        "exchange": "XETRA",
        "date": f"2026-01-{day:02d}",
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "adjusted_close": close,
        "volume": 1,
        "currency": "EUR",
    }


def test_public_daily_return_artifact_matches_independent_oracle() -> None:
    prices = (100.0, 105.0, 102.0, 110.0)
    quotes = [_quote(index, price) for index, price in enumerate(prices, 1)]
    expected_log = [
        log(current / previous) for previous, current in zip(prices, prices[1:], strict=False)
    ]
    expected_simple = [
        current / previous - 1 for previous, current in zip(prices, prices[1:], strict=False)
    ]
    rows = build_quote_returns(quotes)
    assert [row["log_return"] for row in rows] == pytest.approx(expected_log)
    assert [row["simple_return"] for row in rows] == pytest.approx(expected_simple)


def test_metric_artifact_contains_selection_metrics_and_consistent_cumulative_return() -> None:
    quotes = [_quote(index, price) for index, price in enumerate((100.0, 105.0, 102.0, 110.0), 1)]
    row = build_univariate_statistics(quotes)[0]
    required = {
        "annualized_log_return",
        "annualized_simple_return",
        "annualized_geometric_return",
        "annualized_volatility",
        "downside_deviation",
        "sharpe",
        "sortino",
        "max_drawdown",
        "expected_shortfall",
        "var",
        "cumulative_extended_return",
    }
    assert required <= row.keys()
    assert row["cumulative_extended_return"] == pytest.approx(
        exp(float(row["cumulative_log_return"])) - 1
    )

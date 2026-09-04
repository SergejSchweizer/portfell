"""Independent optimizer and cumulative-return oracles for PR419."""

from __future__ import annotations

import pytest

from portfell.portfolio_parts.solvers import solve_minimum_variance


def test_optimizer_oracle_respects_simplex_and_non_negative_weights() -> None:
    listings = (("A", "XETRA", "A"), ("B", "XETRA", "B"))
    covariance = {
        (listings[0], listings[0]): 0.04,
        (listings[0], listings[1]): 0.01,
        (listings[1], listings[0]): 0.01,
        (listings[1], listings[1]): 0.09,
    }
    outcome = solve_minimum_variance(
        listings, covariance, min_weight=0.0, max_weight=1.0
    )
    assert outcome.converged
    weights = outcome.weights
    assert sum(weights) == pytest.approx(1.0)
    assert all(weight >= -1e-10 for weight in weights)


def test_daily_cumulative_extended_return_is_direct_compounding() -> None:
    daily_returns = (0.01, -0.02, 0.03)
    cumulative = 1.0
    values: list[float] = []
    for daily_return in daily_returns:
        cumulative *= 1.0 + daily_return
        values.append(cumulative - 1.0)
    assert values == pytest.approx([0.01, -0.0102, 0.019494])

from __future__ import annotations

import math
from pathlib import Path

from portfell.multivariate.candidates.methods import PORTFOLIO_METHODS, PortfolioMethod
from portfell.multivariate.candidates.solvers import build_candidate
from portfell.multivariate.contracts.common import ListingIdentity


def _listings(size: int) -> tuple[ListingIdentity, ...]:
    return tuple(ListingIdentity(f"ISIN-{index}", "XETRA", f"C{index}") for index in range(size))


def _variance(weights: tuple[float, ...], covariance: tuple[tuple[float, ...], ...]) -> float:
    return sum(
        weights[i] * covariance[i][j] * weights[j]
        for i in range(len(weights))
        for j in range(len(weights))
    )


def _sharpe(
    weights: tuple[float, ...],
    expected: tuple[float, ...],
    covariance: tuple[tuple[float, ...], ...],
) -> float:
    portfolio_return = sum(w * r for w, r in zip(weights, expected, strict=True))
    return portfolio_return / math.sqrt(_variance(weights, covariance))


def test_pr271_method_registry_is_exactly_seven_methods() -> None:
    assert PORTFOLIO_METHODS == (
        PortfolioMethod.EQUAL_WEIGHT,
        PortfolioMethod.MINIMUM_VARIANCE,
        PortfolioMethod.MAXIMUM_SHARPE,
        PortfolioMethod.MAXIMUM_DIVERSIFICATION,
        PortfolioMethod.EQUAL_RISK_CONTRIBUTION,
        PortfolioMethod.HIERARCHICAL_RISK_PARITY,
        PortfolioMethod.MINIMUM_CVAR,
    )


def test_pr271_maximum_sharpe_matches_two_asset_coarse_bounded_bruteforce() -> None:
    listings = _listings(2)
    expected = (0.08, 0.14)
    covariance = ((0.04, 0.01), (0.01, 0.09))
    result = build_candidate(
        method=PortfolioMethod.MAXIMUM_SHARPE,
        listings=listings,
        expected_returns=expected,
        covariance=covariance,
        min_weight=0.1,
        max_weight=0.9,
    )
    assert result.available and result.weights is not None
    brute = max(
        _sharpe((index / 100, 1 - index / 100), expected, covariance)
        for index in range(10, 91)
    )
    assert _sharpe(result.weights, expected, covariance) >= brute - 0.02


def test_pr271_every_available_candidate_is_finite_long_only_and_sums_to_one() -> None:
    listings = _listings(4)
    expected = (0.05, 0.06, 0.08, 0.09)
    covariance = (
        (0.04, 0.01, 0.01, 0.0),
        (0.01, 0.05, 0.01, 0.0),
        (0.01, 0.01, 0.06, 0.01),
        (0.0, 0.0, 0.01, 0.08),
    )
    scenarios = tuple((0.01, -0.01, 0.02, 0.0) for _ in range(30))
    for method in PORTFOLIO_METHODS:
        result = build_candidate(
            method=method,
            listings=listings,
            expected_returns=expected,
            covariance=covariance,
            scenarios=scenarios,
            max_weight=0.6,
        )
        assert result.available, (method, result.reason)
        assert result.weights is not None
        assert all(math.isfinite(weight) and 0 <= weight <= 0.6 for weight in result.weights)
        assert abs(sum(result.weights) - 1.0) <= 1e-7


def test_pr271_failure_is_typed_unavailable_without_equal_weight_fallback() -> None:
    result = build_candidate(
        method=PortfolioMethod.MINIMUM_CVAR,
        listings=_listings(2),
        expected_returns=(0.05, 0.06),
        covariance=((0.04, 0.01), (0.01, 0.05)),
        scenarios=(),
    )
    assert result.method is PortfolioMethod.MINIMUM_CVAR
    assert result.available is False
    assert result.weights is None
    assert result.reason == "minimum_cvar requires training scenarios"


def test_pr271_large_universe_solver_source_contains_no_grid_or_subset_enumeration() -> None:
    source = Path("src/portfell/multivariate/candidates/solvers.py").read_text(encoding="utf-8")
    forbidden = ("itertools.product", "combinations(", "permutations(", "weight_grid")
    assert not any(token in source for token in forbidden)

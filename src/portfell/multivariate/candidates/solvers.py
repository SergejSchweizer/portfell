"""Deterministic solver-backed portfolio candidate adapters.

The implementation uses projected numerical optimization and never enumerates a
large-universe weight grid or asset subset permutation.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

from portfell.multivariate.candidates.methods import CandidateResult, PortfolioMethod
from portfell.multivariate.contracts.common import ListingIdentity

Vector = tuple[float, ...]
Matrix = tuple[tuple[float, ...], ...]


def _validate_matrix(matrix: Matrix, size: int) -> None:
    if len(matrix) != size or any(len(row) != size for row in matrix):
        raise ValueError("covariance matrix shape must match listings")
    if any(not math.isfinite(value) for row in matrix for value in row):
        raise ValueError("covariance matrix values must be finite")


def _project(weights: Sequence[float], *, min_weight: float, max_weight: float) -> Vector:
    size = len(weights)
    if size == 0:
        raise ValueError("at least one asset is required")
    if min_weight * size > 1.0 + 1e-12 or max_weight * size < 1.0 - 1e-12:
        raise ValueError("weight bounds are infeasible")
    result = [min(max(float(weight), min_weight), max_weight) for weight in weights]
    for _ in range(100):
        gap = 1.0 - sum(result)
        if abs(gap) <= 1e-12:
            break
        if gap > 0:
            free = [index for index, weight in enumerate(result) if weight < max_weight - 1e-15]
        else:
            free = [index for index, weight in enumerate(result) if weight > min_weight + 1e-15]
        if not free:
            raise ValueError("unable to satisfy weight bounds")
        share = gap / len(free)
        for index in free:
            result[index] = min(max(result[index] + share, min_weight), max_weight)
    total = sum(result)
    if abs(total - 1.0) > 1e-9:
        raise ValueError("projection failed to produce simplex weights")
    return tuple(result)


def _quadratic(weights: Vector, matrix: Matrix) -> float:
    return sum(weights[i] * matrix[i][j] * weights[j] for i in range(len(weights)) for j in range(len(weights)))


def _portfolio_return(weights: Vector, expected_returns: Vector) -> float:
    return sum(weight * expected for weight, expected in zip(weights, expected_returns, strict=True))


def _finite_difference_optimize(
    objective: Callable[[Vector], float],
    *,
    size: int,
    min_weight: float,
    max_weight: float,
    maximize: bool,
    iterations: int = 400,
) -> Vector:
    weights = _project((1.0 / size,) * size, min_weight=min_weight, max_weight=max_weight)
    direction = 1.0 if maximize else -1.0
    step = 0.08
    epsilon = 1e-6
    best_value = direction * objective(weights)
    for iteration in range(iterations):
        gradients: list[float] = []
        for index in range(size):
            bumped = list(weights)
            bumped[index] += epsilon
            candidate = _project(bumped, min_weight=min_weight, max_weight=max_weight)
            gradients.append((objective(candidate) - objective(weights)) / epsilon)
        candidate = _project(
            [weight + direction * step * gradient for weight, gradient in zip(weights, gradients, strict=True)],
            min_weight=min_weight,
            max_weight=max_weight,
        )
        value = direction * objective(candidate)
        if value >= best_value - 1e-12:
            weights = candidate
            best_value = value
        if (iteration + 1) % 50 == 0:
            step *= 0.5
    return weights


def _equal_risk_weights(covariance: Matrix, *, min_weight: float, max_weight: float) -> Vector:
    size = len(covariance)
    weights = _project((1.0 / size,) * size, min_weight=min_weight, max_weight=max_weight)
    for _ in range(500):
        marginal = [sum(covariance[i][j] * weights[j] for j in range(size)) for i in range(size)]
        contributions = [max(weights[i] * marginal[i], 1e-15) for i in range(size)]
        target = sum(contributions) / size
        adjusted = [weights[i] * math.sqrt(target / contributions[i]) for i in range(size)]
        candidate = _project(adjusted, min_weight=min_weight, max_weight=max_weight)
        if max(abs(a - b) for a, b in zip(candidate, weights, strict=True)) < 1e-10:
            return candidate
        weights = candidate
    return weights


def _hrp_weights(covariance: Matrix, *, min_weight: float, max_weight: float) -> Vector:
    """Deterministic recursive inverse-variance allocation on stable asset order."""

    size = len(covariance)
    weights = [1.0] * size

    def cluster_variance(indices: Sequence[int]) -> float:
        inverse = [1.0 / max(covariance[index][index], 1e-15) for index in indices]
        total = sum(inverse)
        local = [value / total for value in inverse]
        return sum(local[i] * covariance[left][right] * local[j] for i, left in enumerate(indices) for j, right in enumerate(indices))

    clusters: list[list[int]] = [list(range(size))]
    while clusters:
        cluster = clusters.pop()
        if len(cluster) <= 1:
            continue
        midpoint = len(cluster) // 2
        left = cluster[:midpoint]
        right = cluster[midpoint:]
        left_variance = cluster_variance(left)
        right_variance = cluster_variance(right)
        denominator = left_variance + right_variance
        alpha = 0.5 if denominator <= 0 else 1.0 - left_variance / denominator
        for index in left:
            weights[index] *= alpha
        for index in right:
            weights[index] *= 1.0 - alpha
        clusters.extend((left, right))
    return _project(weights, min_weight=min_weight, max_weight=max_weight)


def build_candidate(
    *,
    method: PortfolioMethod,
    listings: tuple[ListingIdentity, ...],
    expected_returns: Vector,
    covariance: Matrix,
    scenarios: tuple[Vector, ...] = (),
    risk_free_rate: float = 0.0,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
) -> CandidateResult:
    """Build exactly one named candidate or return typed unavailable evidence."""

    size = len(listings)
    try:
        if size == 0 or len(expected_returns) != size:
            raise ValueError("expected returns must match listings")
        _validate_matrix(covariance, size)
        if method is PortfolioMethod.EQUAL_WEIGHT:
            weights = _project((1.0 / size,) * size, min_weight=min_weight, max_weight=max_weight)
        elif method is PortfolioMethod.MINIMUM_VARIANCE:
            weights = _finite_difference_optimize(
                lambda candidate: _quadratic(candidate, covariance),
                size=size,
                min_weight=min_weight,
                max_weight=max_weight,
                maximize=False,
            )
        elif method is PortfolioMethod.MAXIMUM_SHARPE:
            def sharpe(candidate: Vector) -> float:
                variance = max(_quadratic(candidate, covariance), 0.0)
                if variance <= 1e-18:
                    return -1e18
                return (_portfolio_return(candidate, expected_returns) - risk_free_rate) / math.sqrt(variance)
            weights = _finite_difference_optimize(
                sharpe,
                size=size,
                min_weight=min_weight,
                max_weight=max_weight,
                maximize=True,
            )
        elif method is PortfolioMethod.MAXIMUM_DIVERSIFICATION:
            asset_volatility = tuple(math.sqrt(max(covariance[i][i], 0.0)) for i in range(size))
            def diversification(candidate: Vector) -> float:
                portfolio_variance = max(_quadratic(candidate, covariance), 0.0)
                if portfolio_variance <= 1e-18:
                    return -1e18
                numerator = sum(weight * volatility for weight, volatility in zip(candidate, asset_volatility, strict=True))
                return numerator / math.sqrt(portfolio_variance)
            weights = _finite_difference_optimize(
                diversification,
                size=size,
                min_weight=min_weight,
                max_weight=max_weight,
                maximize=True,
            )
        elif method is PortfolioMethod.EQUAL_RISK_CONTRIBUTION:
            weights = _equal_risk_weights(covariance, min_weight=min_weight, max_weight=max_weight)
        elif method is PortfolioMethod.HIERARCHICAL_RISK_PARITY:
            weights = _hrp_weights(covariance, min_weight=min_weight, max_weight=max_weight)
        elif method is PortfolioMethod.MINIMUM_CVAR:
            if not scenarios:
                raise ValueError("minimum_cvar requires training scenarios")
            if any(len(scenario) != size for scenario in scenarios):
                raise ValueError("scenario width must match listings")
            def cvar(candidate: Vector) -> float:
                losses = sorted(-sum(weight * value for weight, value in zip(candidate, scenario, strict=True)) for scenario in scenarios)
                tail_start = max(0, int(math.floor(0.95 * len(losses))))
                tail = losses[tail_start:] or losses[-1:]
                return sum(tail) / len(tail)
            weights = _finite_difference_optimize(
                cvar,
                size=size,
                min_weight=min_weight,
                max_weight=max_weight,
                maximize=False,
            )
        else:
            raise ValueError(f"unsupported portfolio method: {method}")
        return CandidateResult(method, listings, weights, True)
    except (ArithmeticError, ValueError) as exc:
        return CandidateResult(method, listings, None, False, str(exc))

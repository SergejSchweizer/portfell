"""Deterministic non-dominated sorting for Multivariate universe selection."""

from __future__ import annotations

from dataclasses import dataclass

from portfell.multivariate.contracts.common import ListingIdentity
from portfell.multivariate.selector.eligibility import SelectorMetrics


@dataclass(frozen=True, slots=True)
class ParetoMember:
    listing: ListingIdentity
    rank: int


@dataclass(frozen=True, slots=True)
class ParetoResult:
    selected: tuple[ParetoMember, ...]
    dominated: tuple[ParetoMember, ...]


def _dominates(left: SelectorMetrics, right: SelectorMetrics) -> bool:
    """Return True when left is no worse on all six metrics and better on at least one."""

    assert left.annualized_geometric_return is not None
    assert left.sharpe is not None
    assert left.sortino is not None
    assert left.annualized_volatility is not None
    assert left.expected_shortfall is not None
    assert left.maximum_drawdown is not None
    assert right.annualized_geometric_return is not None
    assert right.sharpe is not None
    assert right.sortino is not None
    assert right.annualized_volatility is not None
    assert right.expected_shortfall is not None
    assert right.maximum_drawdown is not None

    left_values = (
        left.annualized_geometric_return,
        left.sharpe,
        left.sortino,
        -left.annualized_volatility,
        -left.expected_shortfall,
        -abs(left.maximum_drawdown),
    )
    right_values = (
        right.annualized_geometric_return,
        right.sharpe,
        right.sortino,
        -right.annualized_volatility,
        -right.expected_shortfall,
        -abs(right.maximum_drawdown),
    )
    return all(a >= b for a, b in zip(left_values, right_values, strict=True)) and any(
        a > b for a, b in zip(left_values, right_values, strict=True)
    )


def pareto_ranks(rows: tuple[SelectorMetrics, ...]) -> tuple[ParetoMember, ...]:
    """Assign deterministic fronts using only frozen metrics."""

    remaining = list(sorted(rows, key=lambda row: row.listing))
    ranked: list[ParetoMember] = []
    rank = 1
    while remaining:
        front = [
            candidate
            for candidate in remaining
            if not any(_dominates(other, candidate) for other in remaining if other is not candidate)
        ]
        if not front:
            raise RuntimeError("Pareto sorting produced an empty front")
        for candidate in front:
            ranked.append(ParetoMember(candidate.listing, rank))
        front_ids = {candidate.listing for candidate in front}
        remaining = [candidate for candidate in remaining if candidate.listing not in front_ids]
        rank += 1
    return tuple(sorted(ranked, key=lambda member: (member.rank, member.listing)))


def select_pareto(
    rows: tuple[SelectorMetrics, ...], *, minimum_size: int = 1
) -> ParetoResult:
    """Keep rank 1, extending whole ranks only until the minimum feasible size is met."""

    if minimum_size < 1:
        raise ValueError("minimum_size must be positive")
    ranked = pareto_ranks(rows)
    if not ranked:
        return ParetoResult((), ())
    cutoff = 1
    while sum(member.rank <= cutoff for member in ranked) < minimum_size and cutoff < max(
        member.rank for member in ranked
    ):
        cutoff += 1
    selected = tuple(member for member in ranked if member.rank <= cutoff)
    dominated = tuple(member for member in ranked if member.rank > cutoff)
    return ParetoResult(selected, dominated)

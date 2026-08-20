"""Composition-only selector pipeline; child algorithms remain authoritative."""

from __future__ import annotations

from dataclasses import dataclass

from portfell.multivariate.contracts.common import ListingIdentity
from portfell.multivariate.selector.eligibility import EligibilityResult, SelectorMetrics, apply_eligibility
from portfell.multivariate.selector.pareto import ParetoResult, select_pareto
from portfell.multivariate.selector.redundancy import (
    RedundancyCandidate,
    RedundancyResult,
    reduce_redundancy,
)


@dataclass(frozen=True, slots=True)
class SelectorPipelineResult:
    eligibility: EligibilityResult
    pareto: ParetoResult
    redundancy: RedundancyResult

    @property
    def selected(self) -> tuple[ListingIdentity, ...]:
        return self.redundancy.selected


def select_optimizer_universe(
    rows: tuple[SelectorMetrics, ...],
    *,
    correlations: dict[tuple[ListingIdentity, ListingIdentity], float],
    allowed_distribution_frequencies: tuple[str, ...] = (),
    minimum_size: int = 1,
    maximum_size: int = 250,
) -> SelectorPipelineResult:
    """Compose eligibility -> Pareto -> redundancy without changing child rules."""

    eligibility = apply_eligibility(
        rows,
        allowed_distribution_frequencies=allowed_distribution_frequencies,
    )
    pareto = select_pareto(eligibility.eligible, minimum_size=minimum_size)
    by_listing = {row.listing: row for row in eligibility.eligible}
    ranks = {member.listing: member.rank for member in pareto.selected}
    candidates = tuple(
        RedundancyCandidate(
            listing=member.listing,
            pareto_rank=member.rank,
            sortino=float(by_listing[member.listing].sortino),
            annualized_geometric_return=float(by_listing[member.listing].annualized_geometric_return),
            expected_shortfall=float(by_listing[member.listing].expected_shortfall),
            annualized_volatility=float(by_listing[member.listing].annualized_volatility),
        )
        for member in pareto.selected
        if member.listing in ranks
    )
    redundancy = reduce_redundancy(
        candidates,
        correlations=correlations,
        maximum_size=maximum_size,
    )
    return SelectorPipelineResult(eligibility, pareto, redundancy)
